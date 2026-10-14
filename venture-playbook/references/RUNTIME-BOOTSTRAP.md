# 首次准备环境：AI执行，客户不用选系统或复制命令

这一步只服务本Skill。能用现有Python就不下载；确实没有合格环境，才在用户目录准备专用Python。Mac和Windows共用scripts/bootstrap.py、setup.py与一个发布包，下面两小段只是无Python时调用本机工具的入口，不复制安装业务。

## 先确认在哪台电脑执行，再探测

1. 先识别当前AI宿主和实际执行端。Mac观察uname -s（Darwin），Windows观察OS=Windows_NT及处理器架构；bootstrap.py再用platform.system核对，并在回执明确scope=execution_host。不能凭用户说“我用Windows”就把云端Linux服务器当成本机；没有本机执行通道时不安装到云端充数。
2. 用命令定位已安装的真实解释器：Mac的python3及宿主提供的运行时；Windows的py -0p、Get-Command python/python3及宿主运行时。WindowsApps商店别名不是可用Python，不用它触发商店。逐个用绝对路径执行 `-I -X utf8 -c "import sys,ssl,tomllib,json,pathlib; assert sys.version_info>=(3,11); print(sys.executable)"`。已有兼容Python或缓存回执指向的专用Python自检成功，直接跳到共同安装；访问被拒绝不能当作缺失。每次探测最多30秒。
3. 需要补装时读取assets/runtime-policy.json：固定uv0.13.0和Python3.12.14，uv使用清华PyPI镜像中的官方wheel，SHA256与PyPI官方元数据一致；Python使用npmmirror镜像，交给固定uv按内置元数据校验。版本、镜像和摘要随包固定。未知架构、目录符号链接、写权限或执行权限失败时停止对应步骤，保留原配置；不下载浮动最新版、不使用随机镜像、不提权。UV程序下载、Python下载、配置、本人OAuth是不同阶段。

## 有Python：同一份共同安装

将P、Skill目录、宿主和当前项目temp回执路径解析为本机绝对路径；用参数数组调用，不能把客户路径直接拼成未引用的命令：

`P -I -X utf8 <Skill>/scripts/bootstrap.py --harness H --report <当前项目>/temp/bootstrap-receipt.json`

只有P确实在该用户专用runtime/python目录且由缺失流程准备，才加 `--managed`；已有系统/宿主Python不改PATH。共同脚本再次校验系统、Python与素材，再调用原setup.ensure，全局安装Skill并补齐公共MCP连接。成功回执必须ready=true、setup.configured=true，配置文件、全局Skill及manifest读回一致后才进入S2。它不会发起OAuth，也不更改首次选择。

## 缺Python：固定入口

入口只由AI在本机执行：Mac `/bin/bash --noprofile --norc`；Windows `powershell.exe -NoProfile -NonInteractive -Command`（不是运行下载的.ps1文件）。先将VP_SKILL/VP_HARNESS/VP_REPORT赋为已确认的绝对路径和宿主；VP_USER_HOME默认本机用户目录，隔离测试可指定独立测试目录，不重设HOME或CODEX_HOME。把整段标准输出与错误重定向到当前项目temp/runtime-bootstrap.log；工具设置总超时240秒，超时先终止并读回阶段，不并发重试。下面代码原样使用，不能省掉摘要比较。

### Mac入口

```bash
set -eu
[ "$(uname -s)" = Darwin ] || exit 2
VP_USER_HOME=${VP_USER_HOME:-$HOME}
VP_R="$VP_USER_HOME/.local/share/venture-playbook/runtime"
: "${VP_SKILL:?}" "${VP_HARNESS:?}" "${VP_REPORT:?}"
for VP_KEY in $(env | sed -nE 's/^((UV_|INSTALLER_|CARGO_|PYTHON)[A-Za-z0-9_]*)=.*/\1/p'); do unset "$VP_KEY"; done
case "$(uname -m)" in
  arm64|aarch64) VP_URL="https://pypi.tuna.tsinghua.edu.cn/packages/9e/d4/d42eabbd9b61a965e0a262e06bf8452744593e7a3110a5c4273c4e917729/uv-0.13.0-py3-none-macosx_11_0_arm64.whl"; VP_SHA=a5f93ae362b751737cecef0bbc0294624be68a843ff9b32d86e6862a26101630 ;;
  x86_64) VP_URL="https://pypi.tuna.tsinghua.edu.cn/packages/ff/27/2a2dde8a643337b6746a8e632b3ba8aef7c82b9bc28642bb94dd3a046ef5/uv-0.13.0-py3-none-macosx_10_12_x86_64.whl"; VP_SHA=93265932cb2efd1486d4d182211281b3f0b31637e2fc160c4c8d7b15294188d1 ;;
  *) exit 2 ;;
esac
for VP_DIR in "$VP_USER_HOME/.local" "$VP_USER_HOME/.local/share" "$VP_USER_HOME/.local/share/venture-playbook" "$VP_R"; do [ ! -L "$VP_DIR" ] || exit 2; done
mkdir -p "$VP_R/tmp" "$VP_R/uv"
export TMPDIR="$VP_R/tmp" TMP="$VP_R/tmp" TEMP="$VP_R/tmp"
export UV_PYTHON_INSTALL_DIR="$VP_R/python" UV_CACHE_DIR="$VP_R/cache" UV_PYTHON_CACHE_DIR="$VP_R/downloads"
export UV_HTTP_TIMEOUT=30 UV_HTTP_RETRIES=1 UV_NO_PROGRESS=1
export UV_PYTHON_INSTALL_MIRROR="https://registry.npmmirror.com/-/binary/python-build-standalone"
VP_U="$VP_R/uv/uv"
if [ ! -x "$VP_U" ] || [ "$("$VP_U" --version | cut -d ' ' -f 2)" != '0.13.0' ]; then
  curl -q -fLsS --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 90 --retry 1 "$VP_URL" -o "$VP_R/tmp/uv.zip"
  [ "$(shasum -a 256 "$VP_R/tmp/uv.zip" | cut -d ' ' -f 1)" = "$VP_SHA" ] || exit 3
  /usr/bin/unzip -p "$VP_R/tmp/uv.zip" uv-0.13.0.data/scripts/uv > "$VP_R/uv/uv.new"
  chmod 700 "$VP_R/uv/uv.new"
  mv "$VP_R/uv/uv.new" "$VP_U"
fi
[ "$("$VP_U" --version | cut -d ' ' -f 2)" = '0.13.0' ] || exit 3
"$VP_U" --no-config -q python install 3.12.14 --no-bin --no-registry
VP_P=$("$VP_U" --no-config --offline python find --managed-python --system --no-project 3.12.14)
"$VP_P" -I -X utf8 -c 'import sys,ssl,tomllib,json,pathlib; assert sys.version_info[:3]==(3,12,14)'
"$VP_P" -I -X utf8 "$VP_SKILL/scripts/bootstrap.py" --harness "$VP_HARNESS" --home "$VP_USER_HOME" --managed --report "$VP_REPORT"
```

### Windows入口

```powershell
$ErrorActionPreference='Stop'
if ($env:OS -ne 'Windows_NT') { throw 'local_windows_host_required' }
if (!$VP_USER_HOME) { $VP_USER_HOME=[Environment]::GetFolderPath('UserProfile') }
if (!$VP_SKILL -or !$VP_HARNESS -or !$VP_REPORT) { throw 'bootstrap_arguments_required' }
Get-ChildItem Env: | Where-Object { $_.Name -match '^(UV_|INSTALLER_|CARGO_|PYTHON)' } | ForEach-Object { Remove-Item -LiteralPath ('Env:'+ $_.Name) }
$VP_R=Join-Path $VP_USER_HOME '.local/share/venture-playbook/runtime'
$VP_POLICY=Get-Content -LiteralPath (Join-Path $VP_SKILL 'assets/runtime-policy.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$VP_ARCH=$env:PROCESSOR_ARCHITEW6432
if (!$VP_ARCH) { $VP_ARCH=$env:PROCESSOR_ARCHITECTURE }
$VP_TRIPLE=switch ($VP_ARCH) { 'AMD64' {'x86_64-pc-windows-msvc'} 'ARM64' {'aarch64-pc-windows-msvc'} 'x86' {'i686-pc-windows-msvc'} default {throw 'architecture_unsupported'} }
$VP_ART=$VP_POLICY.artifacts.$VP_TRIPLE
foreach ($VP_DIR in @($VP_R,(Split-Path $VP_R),(Split-Path (Split-Path $VP_R)),(Join-Path $VP_USER_HOME '.local'))) {
  if ((Test-Path -LiteralPath $VP_DIR) -and ((Get-Item -LiteralPath $VP_DIR -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'symlink_runtime_requires_manual_check' }
}
New-Item -ItemType Directory -Force -Path "$VP_R/tmp","$VP_R/uv" | Out-Null
$env:TMP="$VP_R/tmp"; $env:TEMP="$VP_R/tmp"
$env:UV_PYTHON_INSTALL_DIR="$VP_R/python"; $env:UV_CACHE_DIR="$VP_R/cache"; $env:UV_PYTHON_CACHE_DIR="$VP_R/downloads"
$env:UV_HTTP_TIMEOUT='30'; $env:UV_HTTP_RETRIES='1'; $env:UV_NO_PROGRESS='1'
$env:UV_PYTHON_INSTALL_MIRROR=$VP_POLICY.python_mirror
$VP_U=Join-Path $VP_R 'uv/uv.exe'
$VP_HAVE_UV=(Test-Path -LiteralPath $VP_U)
if ($VP_HAVE_UV) { $VP_HAVE_UV=(((& $VP_U --version) -split ' ')[1] -eq $VP_POLICY.uv_version) -and ($LASTEXITCODE -eq 0) }
if (!$VP_HAVE_UV) {
  [Net.ServicePointManager]::SecurityProtocol=[Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
  Invoke-WebRequest -UseBasicParsing -Uri $VP_ART.url -TimeoutSec 90 -OutFile "$VP_R/tmp/uv.zip"
  if ((Get-FileHash -LiteralPath "$VP_R/tmp/uv.zip" -Algorithm SHA256).Hash.ToLowerInvariant() -ne $VP_ART.sha256) { throw 'archive_checksum_mismatch' }
  Expand-Archive -LiteralPath "$VP_R/tmp/uv.zip" -DestinationPath "$VP_R/tmp/uv-wheel" -Force
  Copy-Item -LiteralPath (Join-Path "$VP_R/tmp/uv-wheel" $VP_ART.binary_path) -Destination $VP_U -Force
}
$VP_VERSION=& $VP_U --version
if ($LASTEXITCODE -ne 0 -or ($VP_VERSION -split ' ')[1] -ne $VP_POLICY.uv_version) { throw 'uv_version_mismatch' }
& $VP_U --no-config -q python install $VP_POLICY.python_version --no-bin --no-registry
if ($LASTEXITCODE -ne 0) { throw 'python_prepare_failed' }
$VP_P=& $VP_U --no-config --offline python find --managed-python --system --no-project $VP_POLICY.python_version
if ($LASTEXITCODE -ne 0 -or !$VP_P) { throw 'python_find_failed' }
& $VP_P -I -X utf8 -c 'import sys,ssl,tomllib,json,pathlib; assert sys.version_info[:3]==(3,12,14)'
if ($LASTEXITCODE -ne 0) { throw 'python_check_failed' }
& $VP_P -I -X utf8 (Join-Path $VP_SKILL 'scripts/bootstrap.py') --harness $VP_HARNESS --home $VP_USER_HOME --managed --report $VP_REPORT
if ($LASTEXITCODE -ne 0) { throw 'setup_failed_read_receipt' }
```

从固定国内镜像下载uv的官方wheel，只解压使用其中已校验的独立uv程序，不需要先安装Python或pip。下载解压uv只写runtime目录；Python通过uv管理，使用--no-bin和--no-registry，不创建外部入口、不登记系统Python。随后共同脚本才按用户授权添加Python到用户PATH：Mac按当前登录shell更新.zprofile/.bash_profile/.profile；Windows只更新当前用户Environment的Path，保留原类型与原内容。每次写入前备份、比较及写后回读，失败按实际写入撤回；有其他程序同时修改时保留其内容并报告冲突。不了解的shell不乱改配置。

只追加一次，不把专用Python插到原PATH前面或替换原默认Python。当前任务始终用Python绝对路径，马上可用。已运行的终端或AI应用未必收到新PATH；下一次启动的进程会读取新设置，必要时再提示重开应用，不能用“已保存PATH”冒称所有旧进程已刷新。

## 再次使用与失败处理

- 优先从当前项目bootstrap回执或用户runtime目录定位既有专用Python，实际自检通过后直接调用共同脚本并加--managed；不再下载uv或Python。即使没有回执，uv已存在时可按相同目录变量离线python find后自检。不能仅凭文件名或过去成功记录认定环境有效。
- 首次补装需要网络；uv与Python下载均走上述固定国内镜像，不自动回退GitHub或随机代理；镜像不可用时明确停止对应下载。已有Python的配置与全局安装离线可用。网络失败最多按原地址做一次有界重试；失败、超时、摘要不同、权限拒绝记录真实阶段/退出码和日志，配置未执行就保持原样。摘要不同的文件不能执行，不能关闭TLS检查、修改PowerShell执行策略或尝试管理员安装。
- 企业证书问题只在已确认可信系统证书可用时受控启用UV_SYSTEM_CERTS；不能把未知证书问题变成忽略验证。系统阻止程序执行或客户目录写入时，给一个针对实际拦截的必要动作；工具权限仍由实际宿主控制，不能承诺所有电脑完全无提示。
- setup失败时共同脚本撤回其本次PATH修改；专用下载缓存留在runtime，不误删原Python或客户设置。回滚所需文件在用户级state/runtime/backups，安装器原有回滚仍负责配置与Skill。
- 回执ready=false或缺失，不能进入“已准备好”。允许继续读取用户材料，不能冒称已生成HTML；解决环境问题后从失败节点恢复。登录仍走原S2/G1，本轮安装不改变客服开通与本人OAuth流程。

## 官方来源与证据范围

uv固定版本及SHA256来自[PyPI官方0.13.0元数据](https://pypi.org/pypi/uv/0.13.0/json)，实际wheel下载使用[清华PyPI镜像](https://mirrors.tuna.tsinghua.edu.cn/help/pypi/)；文件摘要必须与官方记录逐项一致。Python镜像为[npmmirror二进制镜像](https://registry.npmmirror.com/-/binary/python-build-standalone/)，使用uv原生[UV_PYTHON_INSTALL_MIRROR](https://docs.astral.sh/uv/reference/environment/#uv_python_install_mirror)覆盖Python下载来源，版本及校验仍由固定uv管理，不是只修改pip源。Python由Astral python-build-standalone提供，不冒称python.org系统安装包。镜像下载成功与文件校验不保证所有地区和企业网络都可访问。

本机验收必须记录复用环境、空目录真实补装、再次离线复用、中文和空格目录、PATH及失败回滚。Windows单元模拟只能说明对应规则经过模拟检查，未在Windows真机执行就明确保留该缺口。
