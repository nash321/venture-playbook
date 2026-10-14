# 全局安装、官方接入与实际边界

环境由scripts/bootstrap.py验证、缺失时按RUNTIME-BOOTSTRAP准备；共同安装由scripts/setup.py默认后台完成；配置与认证分开，回执只给Agent看。

| 宿主 | 全局Skill目录 | 全局MCP配置 | 远程字段 |
|---|---|---|---|
| codex | ~/.agents/skills/venture-playbook | ~/.codex/config.toml | mcp_servers.scys-mcp.url |
| claude | ~/.claude/skills/venture-playbook | ~/.claude.json | mcpServers.scys-mcp.type=http,url |
| cursor | ~/.cursor/skills/venture-playbook | ~/.cursor/mcp.json | mcpServers.scys-mcp.url |
| windsurf | ~/.codeium/windsurf/skills/venture-playbook | 当前Devin/Windsurf文档为~/.config/devin/mcp_config.json | mcpServers.scys-mcp.serverUrl |
| gemini | ~/.gemini/skills/venture-playbook | ~/.gemini/settings.json | mcpServers.scys-mcp.httpUrl |
| opencode | ~/.config/opencode/skills/venture-playbook | ~/.config/opencode/opencode.json | mcp.scys-mcp.type=remote,url |

依据2026-10-13实际读取的官方资料。Windsurf文档已转向Devin Desktop；旧版仍用其他路径时，不把当前路径当旧版实测。Windows的Devin配置使用%APPDATA%/devin/mcp_config.json。脚本遵从已支持的CODEX_HOME和XDG配置位置；自定义CLAUDE_CONFIG_DIR返回缺口，交由实际客户端原生机制处理。

## Mac与Windows共用一套代码

生成器、安装器、引导脚本及HTML模板共用同一份；目录通过Python路径库和本机用户目录解析，不把Mac绝对路径带到Windows。Agent先定位已安装的兼容Python，统一以 `python -X utf8` 方式执行，再按当前命令行引用带空格的路径。安装回执与用户状态明确采用UTF-8读写，避免依赖系统默认编码。

报告可直接在本机浏览器阅读，不需要Python；生成或安装需满足下文Python版本。自动打开优先当前宿主的真实浏览器工具，也可使用本机默认浏览器，不要求安装Ego Lite。发出打开动作后仍须回读页面，不能只凭启动命令称前台已显示。

Mac浏览器的本地待办不会跟随原HTML自动转移到Windows；迁移前保存完整报告或备份待办，再在新电脑打开副本或导入。基础分析不要求登录生财；要在新电脑连接生财，需要按新电脑宿主检查连接并完成本人授权，不复制Mac凭据。

Windows已在真实Windows云端系统执行专用Python下载、用户PATH写入、Codex配置、重复安装、报告生成，以及原生file浏览器59项检查和两次进程关闭重开后的编辑/撤销恢复；另有编码和注册表故障模拟。该证据不包含客户电脑前台、Codex实际加载及本人OAuth，不能记为客户真机完整验收。Mac仍有本机真实验收。

## 对外支持按证据说明

| 场景 | 可以说明什么 | 不能据此说明什么 |
|---|---|---|
| Mac隔离目录安装、缺环境补装及离线复用 | 已真实执行本机脚本并回读配置 | 所有Mac型号、所有客户端均已验收 |
| Mac浏览器打开、修改、撤销与重开恢复 | 已有真实浏览器结果 | 所有Windows浏览器或真实手机均已验证 |
| Windows编码/注册表模拟 | 已验证模拟分支 | Windows客户电脑完整使用已通过 |
| Windows云端系统验收 | 仅按该次运行的安装、生成与浏览器结果说明 | 客户电脑前台显示、客户端加载或本人OAuth已通过 |
| 六类客户端配置生成 | 配置与安装目录规则已实现 | 六类客户端各自实际加载、授权或读取资料均成功 |

在未完成实际设备/客户端验收的范围提供安装协助；客户真实连接必须在其当前宿主做一次本人权限内的只读调用。首次售卖不把自动适配文案写成任何电脑无提示、一次成功的保证。

## 默认配置与可选认证

公共端点：https://mcp.scys.com/shengcai-web/mcp；连接名scys-mcp。端点来自scys.com/mcp实际加载的官方公开配置源，工作文件保留核对记录。官方上手指南使用本人账号OAuth，内容以本人权限为限。

OpenCode会对未认证连接自动发起OAuth，脚本先保存enabled=false的已安装配置；客户选择连接时启用。脚本本身不联网、不启动宿主或浏览器、不重载、不发起OAuth。其他宿主可能有原生启动提示/信任界面，不能保证宿主完全不提示，不能修改信任记录来消除提示。

会员体验卡是作者指定分享入口，3天体验由作者指定；扫码添加客服后需申请开通；客服确认体验已开通后，再回AI进行MCP登录与授权。

## 能力与缺口

报告生成需Python3.10+；Codex默认配置另需Python3.11+标准库TOML解析。其他JSON配置无第三方包。完整同类研究需要宿主真实公开搜索与阅读工具。

默认Python过低或命令不存在时，先定位本机已安装的兼容解释器，后续用其绝对路径运行setup/onboarding/venture，不修改系统默认版本。无兼容解释器时自动按 [RUNTIME-BOOTSTRAP.md](RUNTIME-BOOTSTRAP.md) 通过固定国内镜像准备专用Python，并只添加其目录到用户PATH；Mac按登录shell配置，Windows写当前用户Path，保留原内容。两种系统共用安装核心，客户无需选择系统或粘贴命令。网络、权限和工具能力确实阻止自动准备时，保留材料与配置，只给解决该卡点的一步；不能宣称已安装或生成报告。共同准备流程统一要求Python3.11+，报告生成器原有3.10+能力保留。

已有同端点连接保留原名称与配置，不覆盖凭据。损坏配置、同名不同端点、符号链接、自定义Claude目录或OpenCode JSONC等情况返回明确缺口，保留原文件；不能为追求安静而假称成功。手动给已解压Skill目录时仍先运行全局安装脚本。

ChatGPT网页、Claude Cowork/云端、WorkBuddy等使用平台特定插件/连接器或信任机制，不能把本地目录脚本当作其已安装证明。按平台官方入口逐步引导，暂不由本脚本直接静默安装。不替换作者分享入口。

没有搜索：source_only。受限原文：客户有权材料或明确缺口。没有文件/代码权限：不能冒称生成HTML。用户状态无法写入时说明本环境不能持久保留，不把聊天记忆当永久记录。

## 官方依据

- [生财上手指南](https://scys.com/onepage/mcpHelp)、[生财接入管理](https://scys.com/mcp)
- [Codex技能](https://learn.chatgpt.com/docs/build-skills)、[Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Claude Code技能](https://code.claude.com/docs/en/skills)、[Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Cursor技能](https://cursor.com/docs/skills)、[Cursor MCP](https://cursor.com/docs/mcp)
- [Windsurf/Devin技能](https://docs.devin.ai/desktop/cascade/skills)、[MCP](https://docs.devin.ai/desktop/cascade/mcp)
- [Gemini技能](https://geminicli.com/docs/cli/skills/)、[MCP](https://geminicli.com/docs/tools/mcp-server/)
- [OpenCode技能](https://opencode.ai/docs/skills/)、[配置](https://opencode.ai/docs/config/)、[MCP](https://opencode.ai/docs/mcp-servers/)

## 验收层次

隔离用户目录中的真实文件写入与回读证明脚本行为，不证明各宿主真实加载或OAuth成功。模拟回执仅验证本地状态。实际宿主加载后完成真实只读调用，才能说明该宿主的生财连接可用；发布说明保留具体覆盖范围。
