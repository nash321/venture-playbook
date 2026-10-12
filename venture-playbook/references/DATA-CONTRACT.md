# 数据与命令

唯一可维护输入是UTF-8 `project.json`；示例见 `examples/project-demo.json`。脚本只是编译与检查器，**不会自行研究网页、摘要原文或估计收益**。Agent负责正确填入内容与证据。

## 顶层结构

| 字段 | 说明 |
|---|---|
| schema_version / report_id | 当前结构版本1；项目稳定英文ID，不同项目不可共用 |
| title / subtitle / generated_on | 标题、导读、研究日期 |
| research_status | draft / partial / source_only / complete / demo |
| source_mode | article（有主体文章）或idea（用户设想） |
| verdict | decision、reason、next_step；可选avoid |
| project | buyer、deliverable、revenue_model |
| evidence_boundary | 首屏证据边界，一段即可 |
| sources | 来源实体，每条有id、title、kind、url、publisher、read_status、accessed_on、supports、limitations |
| expected_source_sections | 原文预期章节ID；complete会核章节覆盖 |
| source_sections | id、title、key_point、paragraphs、source_ids、read_status；可选takeaways、unknowns |
| cases | 独立案例，见下表 |
| synthesis | shared、differences两个文字数组 |
| negative_search | status与note；没有找到就明说 |
| business | workflow节点、sections分析段，以及economic_formula/economic_note |
| milestones | horizon、title、acceptance |
| tasks | 可交互行动清单 |
| states | 可观测状态与行动，见下表 |
| limitations / markov_note | 重要缺口与状态模型边界 |
| review | source_fidelity、independence为checked/not_checked，notes记真实检查结论 |

sources.kind：user_material、official、founder、customer、media、research、demo。
来源read_status：full、partial、blocked、not_read。用户粘贴材料与原创demo可以没有URL；其他网络来源必须有真实HTTP(S)网址。不要用“某官网”替代来源。

cases必需：id、name、entity_id、relationship（direct/adjacent/counter）、match_reason、workflow、payment_evidence、transferable、risk、source_ids。要计入完整独立横评，还需independence_checked=true及read_status=full。acquisition、costs、retention可补具体内容。entity_id是经营主体，不是网页ID。

任务必需：id、title、action、deliverable、acceptance、on_failure。其他文字字段：phase、day、due（真实YYYY-MM-DD或空）、owner、priority（high/normal/low）、status（todo/doing/done/blocked）、estimate、cost、inputs、tool、notes。depends_on为已有任务ID数组。时间、费用都是文字口径，不由脚本生成商业数字。默认Agent应填清关键字段，不能靠结构最小值降低行动质量。

状态必需：id、title、evidence、action、advance、stop。可选kind=stop、probability（默认未知）、calculator_evidence（概率不是未知时必须有真实计算依据）。UI不自动更新状态证据。

## 命令

`doctor`：检查本地Python和模板，无网络测试。

`init --title 标题 --out project.json`：生成草稿骨架，不生成伪研究。

`outline source.md --out source-outline.json`：支持UTF-8文本/Markdown/HTML的标题切分，保留原文；不支持直接解析PDF/Word/图片。让宿主先读取或合法提取那些格式。

`queries project.json --out searches.md`：生成机制检索词，不实际搜索。

`dedupe sources.json --out sources-clean.json`：输入来源数组；删除明确跟踪参数、规范网址，保留有效业务参数。不自动判断跨域独立性。

`validate project.json`：检查类型、章节、来源引用、任务、依赖与完整度门槛。

`build project.json --out report.html`：嵌入本地CSS、可信JS、任务数据，生成可离线阅读页面。

`check report.html`：检查结构、目录锚点、可信脚本与CSP；不代替语义或浏览器验收。

`export-tasks project.json --out tasks.csv`：导出全部任务，防表格公式注入。

`merge-tasks project.json --tasks backup.json --out project-updated.json`：导入客户备份，保留主文；项目不匹配则拒绝。再用build生成新版报告。

所有写命令默认拒绝覆盖已有文件。明确允许时加--force，但不能把输出路径设为原始输入文件。错误会退出并说明原因，不留下半份冒充成功的文件。

## 最短生产路线

读取原文和公开证据→填project.json→validate→build→check→能测试时实测交互→给客户report.html。不要重新生成CSS/JS。生成中的事实更新改数据，展示问题改模板与测试。
