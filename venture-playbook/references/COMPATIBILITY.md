# 安装、兼容与真实边界

本包使用Agent Skills目录约定：文件夹名venture-playbook，入口SKILL.md包含name与description，详细说明按需读取，脚本与assets随包。无模型SDK、服务密钥或私有插件依赖。

## 本地安装

Codex：将整个目录放进项目的 `.agents/skills/venture-playbook`，或用户的 `~/.agents/skills/venture-playbook`。

Claude Code：项目的 `.claude/skills/venture-playbook`，或用户的 `~/.claude/skills/venture-playbook`。

其他宿主：使用其文档规定的Skill目录；没有自动发现时，明确要求Agent读取本目录SKILL.md。不要假设所有产品接受相同安装路径。只复制提示词不等于安装了工具与模板。

完整能力要求：读文件、生成文件、Python 3.10+、公开搜索/阅读；浏览器用于实际验收。Python核心没有第三方包。研究依赖宿主模型与搜索，报告自身不调用模型。

## 缺能力时怎样表现

没有搜索：source_only，原文能做，当前市场与同行不伪造。

有搜索但原文受限：请求用户提供有权使用的正文，或先输出明确缺口的partial。

没有Python/文件权限：不能用本编译器生成完整版，先说明能力缺口。不假称交付可下载文件。

只有文件预览：可能只能读静态正文；用浏览器打开HTML启用工作台。不要求安装额外扩展。

本地存储禁用：仍可编辑，使用保存HTML/备份导出，不谎称已持久化。

## 测试口径

随包本地单元测试检查确定性逻辑，浏览器测试检查真实渲染与交互。它们不证明任何模型一定遵守研究规则，也不代表所有宿主的真实安装都已完成。发布实测范围和限制见RELEASE-NOTES.md。

## 官方技术参考（2026-10-12读取）

- Agent Skills结构与渐进加载：https://agentskills.io/specification
- Codex技能位置：https://developers.openai.com/codex/skills/
- Claude Code技能位置：https://code.claude.com/docs/en/skills
- 浏览器本地存储与file:行为：https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage
- 原生dialog：https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog

仅引用公开技术说明，不随包复制其文档正文。具体安装行为会随宿主版本变化，客户环境需单独验收。
