#!/usr/bin/env python3
"""Customer-level choice memory and exactly one next instruction per response."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import setup

ROOT = Path(__file__).resolve().parents[1]
LOGIN = {
    'codex': ('我会打开生财登录页面。页面打开后，请回复“已打开”。', ['codex','mcp','login',setup.SERVER]),
    'claude': ('我会打开生财登录页面。页面打开后，请回复“已打开”。', ['claude','mcp','login',setup.SERVER]),
    'cursor': ('请打开 Cursor 设置里的 Tools & MCP，找到生财连接。找到后回复“找到了”。', []),
    'windsurf': ('请打开当前工具的 MCP 面板，找到生财连接。找到后回复“找到了”。', []),
    'gemini': ('请在当前 Gemini CLI 输入 /mcp auth scys-mcp，打开生财授权页面。打开后回复“已打开”。', []),
    'opencode': ('我会打开生财登录页面。页面打开后，请回复“已打开”。', ['opencode','mcp','auth',setup.SERVER]),
}


def load(host, home):
    if host not in setup.HOSTS: raise ValueError('unsupported_harness')
    path=setup.state_dir(home,host)/'choice.json'
    setup.reject_symlinks(path,Path(home).resolve())
    if not path.exists(): return {'prompt_seen':False,'choice':None,'stage':'intro','authentication':'unknown'}
    data=json.loads(path.read_text())
    stages={'intro','scan','register','login','open_auth','sign_in','authorize','verify','done'}
    if not isinstance(data,dict) or not isinstance(data.get('prompt_seen'),bool) or data.get('stage') not in stages or data.get('authentication') not in ('unknown','verified'):
        raise ValueError('invalid_state')
    return data


def save(host, home, data):
    path=setup.state_dir(home,host)/'choice.json'
    setup.atomic_write(path,(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode(),
                       path.read_bytes() if path.exists() else None,setup.state_dir(home,host)/'backups')


def status(host, home):
    data=load(host,home)
    return {**data,'authentication':'unknown','last_verified':data['authentication']=='verified',
            'show_intro':not data['prompt_seen'],'mode':'web',
            'poster_path':str(ROOT/'会员体验卡海报.jpg'),'trial_days':3}


def choose(host, home, choice):
    if choice not in ('register','connect','skip'):raise ValueError('invalid_choice')
    data=load(host,home)
    if choice=='skip' and data['stage']!='done': data['resume_stage']=data['stage']
    elif choice!='skip': data.pop('resume_stage',None)
    data.update(prompt_seen=True,choice=choice,stage={'register':'scan','connect':'verify','skip':'done'}[choice])
    save(host,home,data)
    return step(host,home)


def step(host, home):
    data=load(host,home);stage=data['stage'];action=[]
    if stage=='scan': message='请用微信扫描下方会员体验卡二维码，打开领取页面。打开后回复“已打开”，可领取3天体验。'
    elif stage=='register': message='请按当前页面提示完成生财注册。完成后回复“已注册”，我再带你连接生财资料。'
    elif stage=='login': message,action=LOGIN[host]
    elif stage=='open_auth': message='请点击生财连接上的登录或认证按钮。浏览器页面打开后，回复“已打开”。'
    elif stage=='sign_in': message='请在当前页面用你的生财账号登录。登录完成后，回复“已登录”。'
    elif stage=='authorize': message='请在当前生财授权页面点击“授权”或“允许”。完成后，回复“已授权”。'
    elif stage=='verify': message='我来检查生财资料是否已经可以读取，你无需操作。'
    elif stage=='done': message='已记住你的选择，我们继续分析项目。'
    else: message='请选择：领取会员体验卡／连接生财资料／直接分析项目。'
    receipt_path=setup.state_dir(home,host)/'setup-receipt.json'
    if action and receipt_path.is_file():
        saved=json.loads(receipt_path.read_text())
        if saved.get('configured') and isinstance(saved.get('server_name'),str):action=[*action[:-1],saved['server_name']]
    return {'stage':stage,'instruction':message,'agent_action':action,
            'poster_path':str(ROOT/'会员体验卡海报.jpg') if stage=='scan' else None}


def advance(host, home):
    data=load(host,home)
    next_stage={'scan':'register','register':'verify','open_auth':'sign_in','sign_in':'authorize','authorize':'verify'}
    if data['stage']=='login':next_stage['login']='open_auth' if host in ('cursor','windsurf') else 'sign_in'
    if data['stage'] not in next_stage:raise ValueError('step_not_advanceable')
    data['stage']=next_stage[data['stage']];save(host,home,data)
    return step(host,home)


def check(host, home):
    """Reuse a visible existing connection without triggering another OAuth."""
    data=load(host,home)
    data.update(prompt_seen=True,choice='connect',stage='verify')
    save(host,home,data)
    return step(host,home)


def login(host, home):
    """Call only after the current connection read is unavailable or unauthenticated."""
    data=load(host,home)
    if data['stage']!='verify': raise ValueError('check_connection_first')
    data.update(authentication='unknown',stage='login')
    save(host,home,data);return step(host,home)


def resume(host, home):
    """Resume only when the customer explicitly asks; never on ordinary next use."""
    data=load(host,home)
    stage=data.pop('resume_stage',data['stage'])
    if stage in ('intro','done','login'): stage='verify'
    data.update(choice='register' if stage in ('scan','register') else 'connect',stage=stage)
    save(host,home,data);return step(host,home)


def verified(host, home, receipt):
    data=load(host,home)
    if data['stage']!='verify' or receipt.get('ok') is not True or receipt.get('server_url')!=setup.ENDPOINT or receipt.get('operation')!='read' or receipt.get('tool') not in ('searchTopic','topicDetail','projectLibList','listMenu') or not receipt.get('verified_at'):
        raise ValueError('actual_readonly_receipt_required')
    # Keep only verification facts, never article text, identities or credentials.
    data.update(authentication='verified',stage='done',verification={key:receipt[key] for key in ('tool','verified_at')})
    save(host,home,data)
    return {**status(host,home),'authentication':'verified','mode':'scys_and_web'}


def main():
    p=argparse.ArgumentParser(description='记录用户选择、读取唯一下一步；不自动登录。')
    p.add_argument('action',choices=['status','step','choose','advance','check','login','resume','verified'])
    p.add_argument('--harness',choices=setup.HOSTS,required=True)
    p.add_argument('--home',type=Path,default=Path.home())
    p.add_argument('--choice',choices=['register','connect','skip'])
    p.add_argument('--receipt',type=Path)
    a=p.parse_args()
    try:
        if a.action=='choose':result=choose(a.harness,a.home,a.choice)
        elif a.action=='verified':result=verified(a.harness,a.home,json.loads(a.receipt.read_text()))
        else:result=globals()[a.action](a.harness,a.home)
        print(json.dumps(result,ensure_ascii=False));return 0
    except (OSError,ValueError,TypeError,AttributeError):
        print(json.dumps({'ok':False,'reason':'state_or_input_invalid'},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())
