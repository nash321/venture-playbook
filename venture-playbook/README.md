# 项目研判 · Venture Playbook V9

把一篇创业复盘，变成看得懂、查得到、改得动、做得下去的报告。

**先打开 `START-HERE.html`。** 客户不需要读代码，也不需要额外注册账号。示例在 `examples/demo-report.html`，可直接体验待办增删改查与保存。

## 安装与一句话调用

把整个 `venture-playbook` 文件夹放到宿主支持的Skill目录，或让Agent明确读取其中的 `SKILL.md`。不要只复制SKILL.md，前端与脚本也属于交付的一部分。

- Codex本地项目：`.agents/skills/venture-playbook/`。
- Claude Code本地项目：`.claude/skills/venture-playbook/`。
- 其他能读目录、运行Python并输出文件的Agent：显式读取 `venture-playbook/SKILL.md`。

安装路径的官方依据及已测边界见 [COMPATIBILITY.md](references/COMPATIBILITY.md)。这不是“所有平台均已实测”的声明。

复制给Agent：

> 使用 venture-playbook 分析以下项目。先按原文顺序深解，再用公开网络找真正可比的经营案例，区分作者自述和核验事实。最后生成一份精美的独立HTML，带可编辑的行动清单、时间安排、验收和失败分支；使用Skill自带脚本，不要重写前端。资料如下：……

## 需要什么

生成器需要 Python 3.10+；不需要安装pip包。完整公开研究需要宿主提供网页搜索与阅读能力。交互报告需要现代桌面或移动浏览器，页面自身没有外部字体、脚本或服务依赖。

缺网络时，仍可做“仅原文”报告，但同行与当期政策保持未核。缺Python/文件生成能力时，不能宣称生成了完整版文件。模型质量和输入完整度仍影响研究质量。

## 客户收到什么

一份 `report.html`：决策速览、原文精读、网络同类比较、生意逻辑、交互待办、状态与下一步、来源与边界。

待办支持新增、编辑、删除、勾选、状态、优先级、搜索、筛选、截止日期、备注、依赖检查和撤销。可导出JSON备份、CSV清单，或保存含当前修改的整份HTML。客户修改行动不会改写研究原文。

**重要：浏览器本地保存不会覆盖原HTML文件。** 换设备、改文件位置或清缓存前，点“保存完整报告”或“备份待办”。本地存储被限制时，页面会明确提示，不假装保存成功。

## 常用命令

以下在Skill目录执行；实际项目文件建议放在客户自己的项目目录。

```sh
python scripts/venture.py doctor
python scripts/venture.py init --title "我的项目" --out ./work/project.json
python scripts/venture.py outline ./work/source.md --out ./work/source-outline.json
python scripts/venture.py queries ./work/project.json --out ./work/search-plan.md
python scripts/venture.py build examples/project-demo.json --out ./demo.html
python scripts/venture.py check ./demo.html
python scripts/venture.py export-tasks ./work/project.json --out ./work/tasks.csv
python scripts/venture.py merge-tasks ./work/project.json --tasks ./work/project-tasks.json --out ./work/project-updated.json
```

`queries`只生成检索词，不假装搜过网页；`outline`只提取结构，不代替精读；`check`只查结构与可信脚本，不认证创业成功率。完整命令见 [DATA-CONTRACT.md](references/DATA-CONTRACT.md)。

## 修改与续用

同一项目保留report_id。客户从报告备份待办后，让Agent合入新的project.json，再重新生成。不要悄悄覆盖客户的修改。不同项目备份不能互相导入。

## 包内没有什么

没有私人账号配置、自动发信、云盘存储、小时定时器、专有站内检索、付费原文样本或登录令牌。提供的是研究与本地报告工具，不是替客户经营的无人值守机器人。

## 质量与权限

默认不保证收益、不代客户对外交易、不自动安装工具或抓取受限内容。示例主文为原创虚构材料，公开同行的来源已列入报告，不含任何用户私人报告。授权与使用边界见 [USAGE.md](USAGE.md)，版本记录见 [CHANGELOG.md](CHANGELOG.md)。

## 卖家换品牌与维护

`assets/brand.json`可改报告品牌名称、英文名、文字标记和一句介绍；不涉及客户私人配置。修改后重新编译，不要直接替换成图片字体包。设计色彩、字号和间距集中在`assets/report.css`，逻辑集中在`assets/tasks.js`。改前端后重新跑测试，不要绕过可信脚本检查。

```sh
python -m unittest discover -s tests -p "test_*.py" -v
# 可选；只在已具备Playwright与浏览器的环境中运行：
python tests/browser_smoke.py --report examples/demo-report.html --out ./qa-output
```

测试结果不是独立创业研究的真实性认证。发布前还需在你实际销售支持的Agent宿主中，用新目录完整生成一次客户报告。
