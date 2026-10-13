# 生财拆解 Skill · Venture Playbook

把创业文章、项目链接和经营复盘整理成可离线阅读的 HTML 报告，结合公开资料作比较，并提供可编辑、可调整顺序的行动清单。

这个仓库用于项目开发、版本管理和回滚。客户安装说明见 [Skill README](venture-playbook/README.md)，实际使用规则见 [SKILL.md](venture-playbook/SKILL.md)。

两个远端均为私有仓库，保存同一份开发历史与正式版本标签：

| 平台 | 仓库 | 本地远端名 |
|---|---|---|
| Gitee | [cursorsome/venture-playbook](https://gitee.com/cursorsome/venture-playbook) | `origin` |
| GitHub | [nash321/venture-playbook](https://github.com/nash321/venture-playbook) | `github` |

## 版本状态

- 正式版本：`venture-playbook-v9.1.1`，历史开发机已全局安装并验收；云端已读取对应远端标签，未替客户安装。
- 当前本机试用：9.1.5，源码分支codex/share-at-start；在9.1.2基础上增加编辑与撤销自动存浏览器、报告自动浏览器打开以及开头分享区。最新102项单元、15项分享区专项浏览器检查通过；配置和选择保留，本轮前台刷新等待Mac解锁，不冒称正式发布或网页复核通过。
- 9.1.2云端候选验收（历史）：包含待办排序与保存恢复、不接入专用判断服务的规则，以及白话导读、术语解释、动作示例和理解自检。云端复查修复示例删除说明与撤销后的阶段显示，101项单元、冻结96项旧测试及两份报告各58项浏览器检查通过；历史结果不当作本机本轮证据，真实读者测试单独记录。
- `master` 保存最新开发进度；正式版本以对应标签为准。推送代码不等于发布安装包。

本次9.1.2本地测试请拉GitHub的[`codex/9.1.2-reading-guide`](https://github.com/nash321/venture-playbook/tree/codex/9.1.2-reading-guide)分支，已包含复查修复。Gitee本轮缺认证，尚未同步此分支。

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

云端托管checkout的origin指向GitHub；原开发机origin/Gitee、github/GitHub的约定保留。本轮不改托管远端。云端测试与客户设备安装、原生OAuth、领取权益分别记录于progress.md；缺原始材料时不重新宣称原文核验通过。
