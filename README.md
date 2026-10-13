# 生财拆解 Skill · Venture Playbook

把创业文章、项目链接和经营复盘整理成可离线阅读的 HTML 报告，结合公开资料作比较，并提供可编辑、可调整顺序的行动清单。

这个仓库用于项目开发、版本管理和回滚。客户安装说明见 [Skill README](venture-playbook/README.md)，实际使用规则见 [SKILL.md](venture-playbook/SKILL.md)。

两个远端均为私有仓库，保存同一份开发历史与正式版本标签：

| 平台 | 仓库 | 本地远端名 |
|---|---|---|
| Gitee | [cursorsome/venture-playbook](https://gitee.com/cursorsome/venture-playbook) | `origin` |
| GitHub | [nash321/venture-playbook](https://github.com/nash321/venture-playbook) | `github` |

## 版本状态

- 正式版本：`venture-playbook-v9.1.1`，已在本机全局安装并验收。
- 当前开发版本：9.1.2，包含待办上移/下移与保存恢复，以及不接入专用判断服务的规则。本机验收完成；正式发布仍待本轮网页复核或明确省略。
- `master` 保存最新开发进度；正式版本以对应标签为准。推送代码不等于发布安装包。

## 目录

| 路径 | 内容 |
|---|---|
| `venture-playbook/` | 可分发 Skill 源码、参考规则、安装器、报告生成器和测试 |
| `实战验收/` | FDE 精华帖的研究报告和项目数据；经营判断仍有待核内容 |
| `agent.md`、`memory.md`、`progress.md` | 项目规则、要求和持续进度 |
| `temp/` | 本地过程文件、回执和回滚快照，不提交 |

## 维护约定

按已确认范围修改，检查差异后提交具体文件。正式版本建立标签并保留回滚快照；每次同步分别推送两个远端，再比对本地与两边的提交和标签。`master` 继续跟踪 `origin/master`。

不提交个人认证凭据、原始付费文章、运行日志或客户引导状态。安装包可由对应版本源码生成，ZIP 不直接进入代码历史。仓库默认使用私有可见性，公开分享需另行明确。

不集成或调用 Jev。验收使用宿主已有能力、脚本检查、浏览器实测和证据回读；功能测试不证明真实客户已理解报告，也不证明商业收益。
