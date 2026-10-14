# 生财拆解 Skill · Venture Playbook

把创业文章、项目链接和经营复盘整理成有来源的研究报告与可编辑行动清单。完整使用规则见 [SKILL.md](venture-playbook/SKILL.md)。

## 客户安装和更新

客户只使用 [Gitee 正式发布页](https://gitee.com/cursorsome/venture-playbook/releases/tag/venture-playbook-v9.1.17) 的 9.1.17 安装包。下载、解压后，把整个 `venture-playbook` 文件夹交给 Agent，说“安装并使用 venture-playbook”；安装步骤见 [客户说明](venture-playbook/README.md)。首次使用无需 GitHub 账号或 GitHub 凭据。之后每次调用从公开 Gitee 仓库匿名检查正式标签，有更高版本才按清单逐文件校验、更新。

缺少运行环境时，固定从清华 PyPI 镜像取得 uv、从 npmmirror 取得 Python；不会改为 GitHub 下载。镜像和 Gitee 仍需客户网络可达。生财资料连接为可选功能，登录和授权由客户本人按宿主官方流程完成。

代码、测试和原创文档采用 [Apache-2.0](LICENSE)；会员体验卡海报、二维码、第三方标识及引用材料不在该授权内，见 [NOTICE](NOTICE)。

## 维护和验收

Gitee 是客户分发和自动更新源；[GitHub 仓库](https://github.com/nash321/venture-playbook)只保存维护代码并运行 Windows 云端测试，不属于客户使用链路。正式版本以 `venture-playbook-v9.1.17` 标签和发布附件为准；开发分支、源码快照和测试回执不能冒充正式安装包。

本版修复首次连接可被默认跳过的问题：所有宿主先检查生财连接，未连接则明确询问并等待选择；旧版用户选择保留。测试结果见发布说明。此前的 Windows 云端运行检查不代表本版客户电脑前台或本人 OAuth 已验收。

项目过程与测试文件保存在根目录 `temp/`，不提交。客户包只包含白名单内的 Skill 文件，不含开发规则、个人凭据、原始付费材料或客户状态。Git 标签和历史用于版本回滚，不强推或覆盖旧标签。
