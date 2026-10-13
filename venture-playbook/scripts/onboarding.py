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
    data=json.loads(path.read_text(encoding='utf-8'))
    stages={'intro','scan','register','contact_service','await_activation','login','open_auth','sign_in','authorize','verify','done'}
    if not isinstance(data,dict) or not isinstance(data.get('prompt_seen'),bool) or not isinstance(data.get('stage'),str) or data.get('stage') not in stages or data.get('authentication') not in ('unknown','verified') or data.get('choice') not in (None,'register','connect','skip'):
        raise ValueError('invalid_state')
    if 'resume_stage' in data and (not isinstance(data['resume_stage'],str) or data['resume_stage'] not in stages):
        raise ValueError('invalid_state')
    if 'trial_activation' in data and data['trial_activation'] not in ('pending','confirmed'):
        raise ValueError('invalid_state')
    return data


def activation_pending(data):
    legacy_trial=data['choice']=='register' or data.get('resume_stage') in ('scan','register','contact_service','await_activation')
    return data.get('trial_activation')=='pending' or ('trial_activation' not in data and legacy_trial and data['authentication']!='verified')


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
    pending=activation_pending(data)
    if choice=='skip' and data['stage']!='done': data['resume_stage']=data['stage']
    elif choice!='skip': data.pop('resume_stage',None)
    data.update(prompt_seen=True,choice=choice,stage={'register':'scan','connect':'verify','skip':'done'}[choice])
    if choice=='register':data['trial_activation']='pending'
    elif pending:
        data['trial_activation']='pending'
        if choice=='connect':data['stage']='await_activation'
    save(host,home,data)
    return step(host,home)


def step(host, home):
    data=load(host,home);stage=data['stage'];action=[]
    if activation_pending(data) and stage in ('verify','login','open_auth','sign_in','authorize'):stage='await_activation'
    if stage=='scan': message='请用微信扫描海报二维码，添加生财客服微信。添加后回复“已加客服”。'
    elif stage in ('register','contact_service'): message='请联系刚添加的生财客服，申请“开通3天体验卡”。发出申请后回复“已联系”；等客服确认开通后，再回到这段 AI 对话继续连接。'
    elif stage=='await_activation': message='请等待客服明确确认3天体验卡已开通。确认后回到这段 AI 对话，回复“体验已开通，连接生财有术”，我再带你登录和授权。'
    elif stage=='login': message,action=LOGIN[host]
    elif stage=='open_auth': message='请点击生财连接上的登录或认证按钮。浏览器页面打开后，回复“已打开”。'
    elif stage=='sign_in': message='请在当前页面用你的生财账号登录。登录完成后，回复“已登录”。'
    elif stage=='authorize': message='请在当前生财授权页面点击“授权”或“允许”。完成后，回复“已授权”。'
    elif stage=='verify': message='我来检查生财资料是否已经可以读取，你无需操作。'
    elif stage=='done': message='已记住你的选择，我们继续分析项目。'
    else: message='请选择：领取会员体验卡／连接生财资料／直接分析项目。'
    receipt_path=setup.state_dir(home,host)/'setup-receipt.json'
    if (action or (host=='gemini' and stage=='login')) and receipt_path.is_file():
        saved=json.loads(receipt_path.read_text(encoding='utf-8'))
        if saved.get('configured') and isinstance(saved.get('server_name'),str):
            if action:action=[*action[:-1],saved['server_name']]
            else:message=message.replace('/mcp auth '+setup.SERVER,'/mcp auth '+saved['server_name'],1)
    return {'stage':stage,'instruction':message,'agent_action':action,
            'poster_path':str(ROOT/'会员体验卡海报.jpg') if stage=='scan' else None}


def advance(host, home):
    data=load(host,home)
    if data['stage']=='await_activation' or (activation_pending(data) and data['stage'] in ('verify','login','open_auth','sign_in','authorize')):
        raise ValueError('activation_confirmation_required')
    next_stage={'scan':'contact_service','register':'await_activation','contact_service':'await_activation','open_auth':'sign_in','sign_in':'authorize','authorize':'verify'}
    if data['stage']=='login':next_stage['login']='open_auth' if host in ('cursor','windsurf') else 'sign_in'
    if data['stage'] not in next_stage:raise ValueError('step_not_advanceable')
    data['stage']=next_stage[data['stage']];save(host,home,data)
    return step(host,home)


def check(host, home):
    """Reuse a visible existing connection without triggering another OAuth."""
    data=load(host,home)
    pending=activation_pending(data)
    data.update(prompt_seen=True,choice='connect',stage='await_activation' if pending else 'verify')
    if pending:data['trial_activation']='pending'
    save(host,home,data)
    return step(host,home)


def login(host, home):
    """Call only after the current connection read is unavailable or unauthenticated."""
    data=load(host,home)
    if activation_pending(data):raise ValueError('activation_confirmation_required')
    if data['stage']!='verify': raise ValueError('check_connection_first')
    data.update(authentication='unknown',stage='login')
    save(host,home,data);return step(host,home)


def resume(host, home):
    """Resume only when the customer explicitly asks; never on ordinary next use."""
    data=load(host,home)
    pending=activation_pending(data)
    stage=data.pop('resume_stage',data['stage'])
    if stage in ('intro','done','login'): stage='verify'
    if pending:
        data['trial_activation']='pending'
        if stage in ('verify','login','open_auth','sign_in','authorize'):stage='await_activation'
    data.update(choice='register' if stage in ('scan','register','contact_service','await_activation') else 'connect',stage=stage)
    save(host,home,data);return step(host,home)


def activated(host, home, confirmed=False):
    """Customer reports the service agent confirmed activation; this is not OAuth proof."""
    if confirmed is not True:raise ValueError('activation_confirmation_required')
    data=load(host,home)
    data.pop('resume_stage',None)
    data.update(prompt_seen=True,choice='connect',stage='verify',trial_activation='confirmed')
    save(host,home,data);return step(host,home)


def verified(host, home, receipt):
    data=load(host,home)
    if activation_pending(data):raise ValueError('activation_confirmation_required')
    if data['stage']!='verify' or receipt.get('ok') is not True or receipt.get('server_url')!=setup.ENDPOINT or receipt.get('operation')!='read' or receipt.get('tool') not in ('searchTopic','topicDetail','projectLibList','listMenu') or not receipt.get('verified_at'):
        raise ValueError('actual_readonly_receipt_required')
    # Keep only verification facts, never article text, identities or credentials.
    data.update(authentication='verified',stage='done',verification={key:receipt[key] for key in ('tool','verified_at')})
    save(host,home,data)
    return {**status(host,home),'authentication':'verified','mode':'scys_and_web'}


def main():
    p=argparse.ArgumentParser(description='记录用户选择、读取唯一下一步；不自动登录。')
    p.add_argument('action',choices=['status','step','choose','advance','check','login','resume','activated','verified'])
    p.add_argument('--harness',choices=setup.HOSTS,required=True)
    p.add_argument('--home',type=Path,default=Path.home())
    p.add_argument('--choice',choices=['register','connect','skip'])
    p.add_argument('--receipt',type=Path)
    p.add_argument('--confirmed',action='store_true')
    a=p.parse_args()
    try:
        if a.action=='choose':result=choose(a.harness,a.home,a.choice)
        elif a.action=='activated':result=activated(a.harness,a.home,a.confirmed)
        elif a.action=='verified':result=verified(a.harness,a.home,json.loads(a.receipt.read_text(encoding='utf-8')))
        else:result=globals()[a.action](a.harness,a.home)
        print(json.dumps(result,ensure_ascii=False));return 0
    except (OSError,ValueError,TypeError,AttributeError):
        print(json.dumps({'ok':False,'reason':'state_or_input_invalid'},ensure_ascii=False));return 2


if __name__=='__main__':raise SystemExit(main())
