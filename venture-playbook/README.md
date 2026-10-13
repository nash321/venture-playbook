# 项目研判 · Venture Playbook V9.1.8（本机试用）

把一篇创业复盘，变成看得懂、查得到、改得动、做得下去的报告。

**先打开 `START-HERE.html`。** 客户不需要读代码。可通过作者的会员体验卡领取3天体验、连接生财资料，也可以跳过，直接用全网资料分析。示例在 `examples/demo-report.html`，可体验待办增删改查与保存。

## 安装与一句话调用

把整个文件夹交给Agent，并说“安装并使用 venture-playbook”。Agent后台运行包内安装脚本，默认安装到对应宿主的**全局Skill目录**并配置生财MCP；客户不需要复制命令或操作配置。登录另行选择，不使用生财也可全网分析。手动安装须保留整个文件夹。

- 默认适配：Codex、Claude Code、Cursor、Windsurf/Devin、Gemini CLI、OpenCode。
- 安装脚本静默、离线、可重复运行，保留已有MCP与用户选择；登录时采用官方OAuth。
- 注册与登录使用引导模式，一次一个步骤；首次显示原图并提示扫码领取3天体验，跳过后不再主动提醒。

安装路径的官方依据及已测边界见 [COMPATIBILITY.md](references/COMPATIBILITY.md)。这不是“所有平台均已实测”的声明。

复制给Agent：

> 使用 venture-playbook 分析以下项目。先按原文顺序深解，再用公开网络找真正可比的经营案例，区分作者自述和核验事实。最后生成一份精美的独立HTML，带可编辑的行动清单、时间安排、验收和失败分支；使用Skill自带脚本，不要重写前端。资料如下：……

## 需要什么

生成器需要 Python 3.10+；不需要安装pip包。完整公开研究需要宿主提供网页搜索与阅读能力。交互报告需要现代桌面或移动浏览器，页面自身没有外部字体、脚本或服务依赖。

后台Codex配置使用标准库TOML解析，需要Python 3.11+；其他默认JSON配置支持Python 3.10+。不支持的自定义配置、JSONC或宿主管理策略会明确返回缺口，不覆盖客户配置。

缺网络时，仍可做“仅原文”报告，但同行与当期政策保持未核。缺Python/文件生成能力时，不能宣称生成了完整版文件。模型质量和输入完整度仍影响研究质量。

## 客户收到什么

每份报告开头、标题介绍后附作者分享入口和原始会员体验卡；用手机扫描原图二维码领取3天体验；点击海报放大，再次点击恢复，也可点“先看报告”继续阅读。桌面文字与图卡左右排列，手机上下排列，完整大图居中、不裁切；结尾不重复推广区。图片内嵌，离线及保存完整报告后仍保留。

一份 `report.html`：决策速览、原文精读、网络同类比较、生意逻辑、交互待办、状态与下一步、来源与边界。

Agent生成或更新后会自动在浏览器打开并确认页面加载，交付后保留报告页，无需客户寻找文件或询问打开方法。纯云端等无法控制本机浏览器的环境会说明限制，并提供可下载文件及打开方法。

新报告可先看白话导读；陌生术语在首次使用处解释，首项行动有填写示例，读完可用自检题回查依据。详细正文、数字口径、条件、失败与来源完整保留。自检题不代表已经通过真实读者测试。

待办支持新增、编辑、删除、勾选、状态、优先级、搜索、筛选、截止日期、备注、依赖检查和撤销。在“我的顺序”且未筛选时，可以用每项右侧的上下箭头调整位置；顺序随备份、CSV和完整HTML保存。可导出JSON备份、CSV清单，或保存含当前修改的整份HTML。客户修改行动不会改写研究原文。

编辑行动的有效修改会自动保存到当前浏览器，无需点“保存行动”；新增行动须填齐必填项。一次编辑可整体撤销，撤销结果也自动保存。关闭窗口保留有效修改，“撤销本次编辑”放弃本次修改。浏览器存储失败或输入不合法会明确提示，不冒充已保存。自动保存不改写HTML文件；移动、分享或换设备前仍需保存完整报告或备份待办。

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

包内有生财公共MCP端点、后台配置脚本和可选登录教程；没有作者或客户的登录令牌、付费原文样本、自动发信、云盘存储或定时器。客户OAuth由自己的宿主保存，选择记录独立保留。

## 质量与权限

默认后台安装本Skill并预配置生财连接；不自动下载依赖、不代客户注册付款、不保证收益、不绕权限读取。示例主文为原创虚构材料，公开同行来源已列入报告，不含用户私人报告。授权与使用边界见 [USAGE.md](USAGE.md)，版本记录见 [CHANGELOG.md](CHANGELOG.md)。

## 卖家换品牌与维护

`assets/brand.json`可改报告品牌名称、英文名、文字标记和一句介绍；不涉及客户私人配置。修改后重新编译，不要直接替换成图片字体包。设计色彩、字号和间距集中在`assets/report.css`，逻辑集中在`assets/tasks.js`。改前端后重新跑测试，不要绕过可信脚本检查。

```sh
python -m unittest discover -s tests -p "test_*.py" -v
# 可选；只在已具备Playwright与浏览器的环境中运行：
python tests/browser_smoke.py --report examples/demo-report.html --out ./qa-output
```

测试结果不是独立创业研究的真实性认证。发布前还需在你实际销售支持的Agent宿主中，用新目录完整生成一次客户报告。

扫码注册后，回到刚才使用本工具的AI对话，发送“连接生财有术”。AI会逐步带你打开登录页、登录并确认授权，再检查连接。报告中的“复制这句话”只复制指令，不会自动登录；已有生财账号可直接从连接开始。

基础功能直接使用文章、链接或项目想法生成分析和行动清单；连接生财资料是可选增强，为分析补充精华帖、风向标等相关案例和经验。宣传区清楚说明这两种用法，不能让客户以为不加入就不能用。
