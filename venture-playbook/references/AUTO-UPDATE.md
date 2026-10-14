# 每次调用先检查Gitee，更新成功再开始任务

固定来源：`https://gitee.com/cursorsome/venture-playbook`。只认`venture-playbook-v主版本.次版本.修订号`正式标签，按数字选最高版本，不取开发分支、测试包或预发布。维护者只在验收通过后打正式标签；标签必须包含venture-playbook/manifest.json及完整包，发布后不得移动旧标签。

## Agent执行

1. 当前宿主先识别实际Skill目录和可用Python。已有Python直接检查；缺少时只按RUNTIME-BOOTSTRAP准备最小环境，然后立即检查实际安装目录，不能先开始客户任务。
2. 执行主Skill U0命令，过程、备份和回执都在当前项目temp。每次调用检查一次；更新后重新读规则属于同次调用，不递归重复U0。不要创建定时器或常驻进程；后台是无额外确认地执行并等待结果，不是边更新边研究。
3. 更新器从Gitee取全部标签，冻结最高正式标签对应提交；按同一提交取manifest及文件，核对版本、路径和逐文件SHA256。校验完成才写入，保留回滚备份，manifest最后更新；写入失败恢复旧内容，遇到并发改动保留该改动并阻断，不能强行覆盖。
4. ready=true且status为current/local_ahead/updated才继续。updated时必须重新读取skill_path下的SKILL.md及本任务所需引用；S1及后续均使用该路径，禁止再把旧解压包安装回来。local_ahead表示本机比最高正式标签新，不降级，也不冒称该本地版已经正式发布。
5. ready=false则报告具体阻塞并停止其他任务，不偷偷继续旧版。确认网络恢复或权限补齐后可重试；不要无限循环。进程意外中止遗留更新锁时核查原进程与备份，恢复完整已校验版本后才能解除锁，不只删锁继续。

## 读取权限与凭据

固定分发仓库现为公开仓库，统一匿名读取，不需要Gitee账号、邀请码或访问令牌；不读取GITEE_ACCESS_TOKEN，也不发送客户凭据。生财OAuth与Skill下载是两件事，不因下载失败要求客户登录生财。若维护者以后关闭公开权限，更新停止并报告来源不可用，不自动索取令牌或切换来源。

自动更新只覆盖manifest管理的Skill文件，保留用户MCP配置、首次选择、登录凭据、项目材料、报告及浏览器待办。客户手改了受管理文件时停止更新，先保存修改并解决冲突。更新锁位于Skill同级目录；回滚备份在当前项目temp。SHA256证明文件完整性，来源信任基于固定Gitee仓库、HTTPS与已公开的固定来源，不宣称独立数字签名。

无本机执行或写权限的宿主无法保证自动安装，明确停止并说明需在有权限的宿主更新。宿主已缓存的Skill描述可能需要重新加载；当前调用必须直接重读更新后的文件。旧版本没有U0时不会凭空自更新，客户必须先安装一次含U0的版本。

## 失败后从哪里恢复

network_unavailable：检查当前网络后重试本次检查；source_rate_limited/source_denied_or_rate_limited：根据实际HTTP结果处理服务限制，不索要私人令牌；public_source_not_found/public_source_unavailable：维护者核对公开仓库、标签和路径；update_permission_denied：检查当前Skill目录写权限；update_busy_or_stale_lock：先确认有无正在更新的进程，确无进程时核对备份和当前文件再处理遗留锁，不能直接删锁。local_modification/rollback_conflict：保存本地改动并解决具体冲突。所有失败仍保留旧版并停止后续任务，不静默降级继续。
