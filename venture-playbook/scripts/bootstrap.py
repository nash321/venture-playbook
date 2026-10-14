#!/usr/bin/env python3
"""Shared post-bootstrap verification, user PATH and offline Skill setup; no OAuth."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import setup

ROOT=Path(__file__).resolve().parents[1]
BEGIN='# >>> venture-playbook python >>>'
END='# <<< venture-playbook python <<<'


def system_profile():
    system={'Darwin':'macos','Windows':'windows'}.get(platform.system())
    if system is None:raise ValueError('local_mac_or_windows_host_required')
    return {'system':system,'architecture':platform.machine(),'scope':'execution_host'}


def doctor():
    p=subprocess.run([sys.executable,'-I','-X','utf8',str(ROOT/'scripts/venture.py'),'doctor'],capture_output=True,text=True,encoding='utf-8',timeout=30)
    if p.returncode:raise ValueError('runtime_or_assets_check_failed')


def windows_path(home,entry,registry=None):
    if registry is None:
        import winreg as registry
        if home!=Path.home().resolve():raise ValueError('windows_path_requires_actual_user_home')
    with registry.CreateKeyEx(registry.HKEY_CURRENT_USER,'Environment',0,registry.KEY_READ|registry.KEY_WRITE) as key:
        try:old,kind=registry.QueryValueEx(key,'Path')
        except FileNotFoundError:old,kind=None,registry.REG_EXPAND_SZ
        if old is not None and (not isinstance(old,str) or kind not in (registry.REG_SZ,registry.REG_EXPAND_SZ)):raise ValueError('user_path_is_not_text')
        import ntpath
        norm=lambda s:ntpath.normcase(ntpath.normpath(s))
        if any(norm(s)==norm(entry) for s in (old or '').split(';') if s):return {'changed':False}
        new=(old or '')+(';' if old and not old.endswith(';') else '')+entry
        backup=setup.state_dir(home,'runtime')/'backups'/('path-'+hashlib.sha256(str(old).encode()).hexdigest()[:12]+'.json')
        setup.reject_symlinks(backup,home)
        data=(json.dumps({'value':old,'type':kind},ensure_ascii=False)+'\n').encode()
        setup.atomic_write(backup,data,backup.read_bytes() if backup.exists() else None,backup.parent)
        try:current,current_kind=registry.QueryValueEx(key,'Path')
        except FileNotFoundError:current,current_kind=None,kind
        if current!=old or current_kind!=kind:raise ValueError('path_concurrent_change')
        registry.SetValueEx(key,'Path',0,kind,new)
        if registry.QueryValueEx(key,'Path')!=(new,kind):raise ValueError('user_path_readback_failed')
    return {'changed':True,'kind':'registry','registry':registry,'old':old,'new':new,'type':kind,'backup':str(backup)}


def enable_path(home,python):
    home=Path(home).resolve();python=Path(python).resolve()
    private=home/'.local/share/venture-playbook/runtime/python'
    if not python.is_relative_to(private.resolve()):raise ValueError('managed_python_outside_private_directory')
    setup.reject_symlinks(private,home)
    entry=str(python.parent)
    if os.name=='nt':token=windows_path(home,entry)
    else:
        shell=Path(os.environ.get('SHELL','/bin/zsh')).name
        names={'zsh':'.zprofile','bash':'.bash_profile','sh':'.profile'}
        if shell not in names:raise ValueError('shell_path_preparation_unsupported')
        path=home/names[shell];setup.reject_symlinks(path,home)
        old=path.read_bytes() if path.exists() else None;text=(old or b'').decode('utf-8')
        quoted=shlex.quote(entry)
        block=BEGIN+'\ncase ":${PATH-}:" in\n  *:'+quoted+':*) ;;\n  *) export PATH="${PATH:+${PATH}:}"'+quoted+' ;;\nesac\n'+END+'\n'
        pattern=re.compile(r'^'+re.escape(BEGIN)+r'\n.*?^'+re.escape(END)+r'\n?',re.M|re.S)
        if text.count(BEGIN)>1 or text.count(END)!=text.count(BEGIN):raise ValueError('owned_path_block_invalid')
        if BEGIN in text and not pattern.search(text):raise ValueError('owned_path_block_invalid')
        new=(pattern.sub(lambda _:block,text) if BEGIN in text else text+('' if not text or text.endswith('\n') else '\n')+block).encode('utf-8')
        backups=setup.state_dir(home,'runtime')/'backups'
        setup.reject_symlinks(backups,home)
        changed=setup.atomic_write(path,new,old,backups)
        token={'changed':changed,'kind':'profile','path':path,'old':old,'new':new,'backups':backups}
    before=os.environ.get('PATH','');separator=';' if os.name=='nt' else ':'
    if entry not in before.split(separator):os.environ['PATH']=before+(separator if before else '')+entry
    return {**token,'entry':entry,'process_before':before,'process_after':os.environ.get('PATH','')}


def restore_path(token):
    if token.get('changed'):
        if token['kind']=='profile':
            path=token['path']
            if path.read_bytes()!=token['new']:raise ValueError('path_rollback_conflict')
            if token['old'] is None:path.unlink()
            else:setup.atomic_write(path,token['old'],token['new'],token['backups'])
        else:
            r=token['registry']
            with r.CreateKeyEx(r.HKEY_CURRENT_USER,'Environment',0,r.KEY_READ|r.KEY_WRITE) as key:
                if r.QueryValueEx(key,'Path')!=(token['new'],token['type']):raise ValueError('path_rollback_conflict')
                if token['old'] is None:r.DeleteValue(key,'Path')
                else:r.SetValueEx(key,'Path',0,token['type'],token['old'])
    if os.environ.get('PATH','')==token.get('process_after'):os.environ['PATH']=token['process_before']


def prepare(harness,home,managed=False):
    if sys.version_info<(3,11):raise ValueError('python_3_11_required')
    import ssl,tomllib
    profile=system_profile();home=Path(home).expanduser().resolve();doctor()
    token=enable_path(home,Path(sys.executable)) if managed else {'changed':False}
    try:installed=setup.ensure(harness,home,install_skill=True)
    except (OSError,ValueError):
        restore_path(token);raise
    return {'ready':True,'platform':profile,'python':str(Path(sys.executable).resolve()),'version':list(sys.version_info[:3]),
            'managed_runtime':managed,'user_path_added':token['changed'],'path_entry':token.get('entry'),
            'process_path_ready':managed,'setup':installed,'authentication':'not_attempted'}


def main():
    p=argparse.ArgumentParser(description='验证Python与资料，按需添加用户PATH，再静默安装；不登录。')
    p.add_argument('--harness',choices=setup.HOSTS,required=True);p.add_argument('--home',type=Path,default=Path.home())
    p.add_argument('--managed',action='store_true');p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    try:result=prepare(a.harness,a.home,a.managed);code=0
    except (OSError,ValueError,ImportError,subprocess.SubprocessError) as exc:
        result={'ready':False,'reason':str(exc),'authentication':'not_attempted'};code=2
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return code


if __name__=='__main__':raise SystemExit(main())
