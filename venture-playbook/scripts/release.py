#!/usr/bin/env python3
"""Build a clean customer archive using an explicit allowlist. Offline, stdlib only."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ALLOW={
'SKILL.md','README.md','START-HERE.html','USAGE.md','CHANGELOG.md','RELEASE-NOTES.md','LICENSE','NOTICE',
'agents/openai.yaml','assets/brand.json','assets/report.css','assets/tasks.js',
'assets/referral-card.html','assets/referral-footer.html','assets/runtime-policy.json',
'scripts/venture.py','scripts/release.py',
'scripts/setup.py','scripts/onboarding.py','scripts/bootstrap.py','scripts/update.py','会员体验卡海报.jpg',
'references/SOURCE-READING.md','references/WEB-RESEARCH.md','references/BUSINESS-REVIEW.md',
'references/ACTION-PLAN.md','references/HTML-UX.md','references/UPDATE-AND-RECOVERY.md',
'references/DATA-CONTRACT.md','references/COMPATIBILITY.md','references/ONBOARDING.md',
'references/READABILITY.md','references/RUNTIME-BOOTSTRAP.md','references/AUTO-UPDATE.md',
'examples/README.md','examples/source-demo.md','examples/project-demo.json','examples/demo-report.html',
'tests/test_venture.py','tests/browser_smoke.py','tests/storage_mock.py','tests/test_onboarding.py','tests/test_bootstrap.py','tests/test_update.py'
}

def main():
    p=argparse.ArgumentParser(description='按发布白名单打包，拒绝隐私残留，不上传或安装。')
    p.add_argument('--out',type=Path,required=True);p.add_argument('--force',action='store_true');a=p.parse_args()
    out=a.out.resolve()
    if out.exists() and not a.force:raise ValueError('目标已存在；确认后使用--force。')
    files={};findings=[]
    for name in sorted(ALLOW):
        path=ROOT/name
        if not path.is_file() or path.is_symlink():raise ValueError('缺少正式文件或包含符号链接：'+name)
        data=path.read_bytes();files[name]=data
        if name=='会员体验卡海报.jpg':
            if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):raise ValueError('会员体验卡不是完整JPEG')
            continue
        text=data.decode('utf-8')
        if name!='scripts/release.py':
            for rx in [r'/mnt/data/',r'https://(?:docs|drive|mail)\.google\.com/',r'BEGIN (?:RSA |EC )?PRIVATE KEY',r'(?i)(?:sk-|ghp_)[A-Za-z0-9]{20,}',r'FREQ=HOURLY']:
                if re.search(rx,text):findings.append(name+'：检测到不应分发的配置或凭据模式')
            for email in re.findall(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',text):
                if not email.endswith(('@example.com','@example.invalid')):findings.append(name+'：包含非示例邮箱')
    if findings:raise ValueError('\n'.join(findings))
    manifest={'name':'venture-playbook','version':'9.1.16','edition':'portable-customer','sha256':{n:hashlib.sha256(b).hexdigest() for n,b in files.items()},'note':'指纹验证文件完整性，不认证研究真实性、OAuth或跨宿主实装。'}
    files['manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    out.parent.mkdir(parents=True,exist_ok=True)
    mode='w' if a.force else 'x'
    with zipfile.ZipFile(out,mode,zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo('venture-playbook/'+name,date_time=(2026,10,13,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,data)
    with zipfile.ZipFile(out) as z:
        bad=z.testzip()
        if bad:raise ValueError('压缩包校验失败：'+bad)
    print(json.dumps({'archive':str(out),'privacy_patterns_found':False,'allowlist_only':True,'zip_integrity':'PASS','sha256':hashlib.sha256(out.read_bytes()).hexdigest()},ensure_ascii=False,indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,UnicodeError,zipfile.BadZipFile) as exc:print('未打包：'+str(exc),file=sys.stderr);raise SystemExit(2)
