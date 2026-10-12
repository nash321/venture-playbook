#!/usr/bin/env python3
"""Offline compiler for Venture Playbook. Standard library only; no network or commercial calculations."""
from __future__ import annotations
import argparse
import base64
import csv
import hashlib
import html
import io
import json
import os
import re
import sys
import tempfile
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
VERSION = '9.1.1'
REFERRAL_URL = 'https://work.weixin.qq.com/ct/wcde937479180800d2ce8d79af05f9644fde'
STATUSES = {'todo':'待开始','doing':'进行中','done':'已完成','blocked':'受阻'}
PRIORITIES = {'high':'优先','normal':'正常','low':'稍后'}
RESEARCH = {'draft':'草稿','partial':'仍有待核内容','source_only':'仅基于提供材料','complete':'研究完成 · 不代表收益验证','demo':'演示样稿 · 非真实经营结果'}
ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$')
TASK_FIELDS = ['id','title','phase','day','due','owner','priority','status','estimate','cost','inputs','action','tool','deliverable','acceptance','on_failure','notes']
MAX_JSON = 8 * 1024 * 1024

class InputError(ValueError):
    """A recoverable input error with a clear user-facing message."""


def read_json(path: Path):
    if not path.is_file(): raise InputError(f'未找到文件：{path}')
    if path.stat().st_size > MAX_JSON: raise InputError('JSON超过8MB，请拆分项目；不要截断原文。')
    def pairs(values):
        d={}
        for k,v in values:
            if k in d: raise InputError(f'JSON有重复字段：{k}')
            d[k]=v
        return d
    try: return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=pairs)
    except (UnicodeError,json.JSONDecodeError) as exc: raise InputError(f'JSON格式或编码有误：{exc}') from exc


def atomic_write(path: Path, content: str | bytes, force=False):
    path=path.resolve()
    if path.exists() and not force: raise InputError(f'文件已存在，未覆盖：{path}。确认后增加 --force。')
    path.parent.mkdir(parents=True,exist_ok=True)
    data=content.encode('utf-8') if isinstance(content,str) else content
    fd,name=tempfile.mkstemp(prefix='.venture-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        if not force and path.exists(): raise InputError('目标在写入期间出现，未覆盖。')
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)
    return path


def esc(v): return html.escape(str(v if v is not None else ''),quote=True)
def arr(obj,key):
    value=obj.get(key,[])
    if not isinstance(value,list): raise InputError(f'{key}必须是数组。')
    return value

def string(value,label,required=False,limit=100000):
    if value is None: value=''
    if not isinstance(value,str): raise InputError(f'{label}必须是文字。')
    if len(value)>limit: raise InputError(f'{label}过长，请按自然章节拆分。')
    if required and not value.strip(): raise InputError(f'{label}不能为空。')
    return value


def safe_url(value, optional=True):
    value=string(value,'网址').strip()
    if not value and optional: return ''
    if re.search(r'[\x00-\x20\x7f]',value): raise InputError('网址包含空格或控制字符。')
    try: p=urlsplit(value)
    except ValueError as exc: raise InputError('网址无法解析。') from exc
    if p.scheme not in {'https','http'} or not p.hostname or p.username or p.password: raise InputError('来源网址必须为不含凭据的HTTP(S)地址。')
    return value


def canonical_url(value):
    p=urlsplit(safe_url(value,False))
    dropped={'gclid','fbclid','msclkid'}
    query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in dropped]
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path or '/',urlencode(query,doseq=True),''))


def validate_tasks(raw):
    if not isinstance(raw,list) or len(raw)>1000: raise InputError('待办须为数组，单份报告最多1000项。')
    tasks=[]
    for v in raw:
        if not isinstance(v,dict): raise InputError('每项待办必须为对象。')
        t={k:string(v.get(k,''),'任务.'+k,k in {'id','title'},240 if k=='title' else 16000) for k in TASK_FIELDS}
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',t['id']): raise InputError('任务ID格式不正确。')
        t['phase']=t['phase'].strip() or '未分阶段';t['priority']=t['priority'] or 'normal';t['status']=t['status'] or 'todo'
        if t['status'] not in STATUSES or t['priority'] not in PRIORITIES: raise InputError('任务状态或优先级不支持。')
        if t['due']:
            try:
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',t['due']) or date.fromisoformat(t['due']).isoformat()!=t['due']: raise ValueError()
            except ValueError as exc: raise InputError('截止日期须为真实的YYYY-MM-DD。') from exc
        deps=v.get('depends_on',[])
        if not isinstance(deps,list) or not all(isinstance(d,str) for d in deps): raise InputError('depends_on必须是任务ID数组。')
        if len(deps)!=len(set(deps)): raise InputError('重复的前置任务ID。')
        t['depends_on']=deps;tasks.append(t)
    by_id={t['id']:t for t in tasks}
    if len(by_id)!=len(tasks): raise InputError('待办ID重复。')
    for t in tasks:
        if not set(t['depends_on']).issubset(by_id): raise InputError(f"任务{t['id']}有不存在的前置任务。")
        if t['status']=='done' and any(by_id[d]['status']!='done' for d in t['depends_on']): raise InputError('已完成任务不能依赖未完成任务。')
    active=set();done=set()
    for start in by_id:
        stack=[(start,False)]
        while stack:
            node,leaving=stack.pop()
            if leaving:
                active.discard(node);done.add(node);continue
            if node in active:raise InputError('任务存在循环依赖。')
            if node in done:continue
            active.add(node);stack.append((node,True))
            stack.extend((dep,False) for dep in reversed(by_id[node]['depends_on']))
    if len(json.dumps(tasks,ensure_ascii=False).encode('utf-8'))>2000000:raise InputError('待办数据过大，请拆分项目；需保持备份可恢复。')
    return tasks


def validate_data(data):
    if not isinstance(data,dict): raise InputError('报告数据必须为JSON对象。')
    if data.get('schema_version')!=1: raise InputError('schema_version应为1。')
    for key in ['project','business','synthesis','negative_search','review']:
        if not isinstance(data.get(key,{}),dict): raise InputError(key+'必须为对象。')
    if 'revision' in data: string(data['revision'],'revision',True,200)
    if not ID.fullmatch(string(data.get('report_id'),'report_id',True,100)): raise InputError('report_id只能使用字母、数字、连字符与下划线。')
    for k in ['title','subtitle']: string(data.get(k),k,True)
    if data.get('research_status') not in RESEARCH: raise InputError('research_status不支持。')
    if data.get('source_mode','article') not in {'article','idea'}: raise InputError('source_mode应为article或idea。')
    verdict=data.get('verdict',{})
    if not isinstance(verdict,dict) or not all(isinstance(verdict.get(k),str) and verdict[k].strip() for k in ['decision','reason','next_step']): raise InputError('请填写结论、理由和唯一下一步。')
    source_ids=set()
    for s in arr(data,'sources'):
        if not isinstance(s,dict) or not ID.fullmatch(string(s.get('id'),'来源ID',True,100)): raise InputError('来源需要有效ID。')
        if s['id'] in source_ids: raise InputError('来源ID重复。')
        source_ids.add(s['id']);string(s.get('title'),'来源标题',True);safe_url(s.get('url',''))
        if s.get('kind') not in {'user_material','official','founder','customer','media','research','demo'}: raise InputError('来源kind不支持。')
        if s.get('read_status') not in {'full','partial','blocked','not_read'}: raise InputError('来源read_status不支持。')
        if not s.get('url') and s.get('kind') not in {'user_material','demo'}: raise InputError('网络来源需要真实网址；不能凭空填已核。')
    sections=arr(data,'source_sections');cases=arr(data,'cases')
    unique_sections=set();direct=set()
    def refs(item):
        values=item.get('source_ids',[])
        if not isinstance(values,list) or not all(isinstance(v,str) and v in source_ids for v in values): raise InputError('source_ids引用了不存在的来源。')
    for s in sections:
        if not isinstance(s,dict): raise InputError('原文章节须为对象。')
        sid=string(s.get('id'),'章节id',True)
        if not ID.fullmatch(sid) or sid in unique_sections: raise InputError('章节ID重复或无效。')
        unique_sections.add(sid);string(s.get('title'),'章节标题',True);string(s.get('key_point'),'章节重点',True);refs(s)
        if s.get('read_status') not in {'full','partial','blocked','not_read'}:raise InputError('章节read_status不支持。')
        ps=arr(s,'paragraphs')
        if not ps or not all(isinstance(p,str) and p.strip() for p in ps): raise InputError('每节必须有实质解读，不能只有标题。')
        for k in ['takeaways','unknowns']:
            if not all(isinstance(v,str) for v in arr(s,k)): raise InputError(f'{k}应为文字数组。')
    case_ids=set()
    for c in cases:
        if not isinstance(c,dict): raise InputError('同类案例须为对象。')
        cid=string(c.get('id'),'案例ID',True)
        if not ID.fullmatch(cid) or cid in case_ids: raise InputError('案例ID重复或无效。')
        case_ids.add(cid)
        for k in ['name','entity_id','match_reason','workflow','payment_evidence','transferable','risk']: string(c.get(k),'案例.'+k,True)
        refs(c)
        if c.get('read_status') not in {'full','partial','blocked','not_read'}:raise InputError('案例read_status不支持。')
        if c.get('relationship') not in {'direct','adjacent','counter'}: raise InputError('案例relationship应为direct/adjacent/counter。')
        if c.get('relationship')=='direct' and c.get('independence_checked') is True and c.get('read_status')=='full':
            if not c.get('source_ids'):raise InputError('已读独立案例必须列明依据来源。')
            if not any(s['id'] in c['source_ids'] and s.get('url') and s.get('read_status')=='full' for s in data['sources']):raise InputError('已读案例必须有实际全文读取的网络来源。')
            direct.add(c['entity_id'])
    data['tasks']=validate_tasks(arr(data,'tasks'))
    for t in data['tasks']:
        for k in ['action','deliverable','acceptance','on_failure']: string(t.get(k),'任务.'+k,True)
    state_ids=set()
    for s in arr(data,'states'):
        if not isinstance(s,dict): raise InputError('状态须为对象。')
        for k in ['id','title','evidence','action','advance','stop']: string(s.get(k),'状态.'+k,True)
        if not ID.fullmatch(s['id']) or s['id'] in state_ids: raise InputError('状态ID重复或无效。')
        state_ids.add(s['id'])
        p=s.get('probability','未知')
        if not isinstance(p,str): raise InputError('概率需文字口径，不接收程序生成概率。')
        if p not in {'未知','unknown','UNKNOWN','未估计'} and not s.get('calculator_evidence'): raise InputError('已知概率须附原始样本与可靠计算器证据。')
    for m in arr(data,'milestones'):
        if not isinstance(m,dict) or not all(isinstance(m.get(k),str) and m[k].strip() for k in ['horizon','title','acceptance']): raise InputError('里程碑必须有时间窗、目标与通过标准。')
    biz=data.get('business',{})
    if not isinstance(biz,dict): raise InputError('business必须为对象。')
    for s in arr(biz,'sections'):
        if not isinstance(s,dict):raise InputError('商业分析小节须为对象。')
        string(s.get('title'),'商业标题',True);string(s.get('text'),'商业正文',True);refs(s)
    for step in arr(biz,'workflow'):
        if not isinstance(step,dict):raise InputError('工作流步骤须为对象。')
        string(step.get('title'),'步骤标题',True);string(step.get('detail',''),'步骤说明')
    for key in ['shared','differences']:
        if not all(isinstance(v,str) for v in arr(data.get('synthesis',{}),key)):raise InputError('综合比较须为文字数组。')
    if not all(isinstance(v,str) for v in arr(data,'limitations')):raise InputError('limitations须为文字数组。')
    selected=data.get('selected_state','')
    if not isinstance(selected,str) or (selected and selected not in state_ids):raise InputError('选中的状态不存在。')
    if data['research_status']=='complete':
        if data.get('source_mode','article')=='article' and not sections: raise InputError('主文未解读，不能标研究完成。')
        expected=arr(data,'expected_source_sections')
        if not all(isinstance(v,str) for v in expected): raise InputError('expected_source_sections必须为章节ID数组。')
        if data.get('source_mode','article')=='article' and not expected:raise InputError('完整原文研究需列明预期章节，避免漏章。')
        required=set(expected)
        if required and not required.issubset(unique_sections): raise InputError('承诺的原文章节未全部解读。')
        if any(s.get('read_status')!='full' for s in sections): raise InputError('原文尚未读全，不能标研究完成。')
        if len(direct)<3: raise InputError('完整横评至少需要3个已核独立的同机制经营主体。')
        if not data['tasks'] or not arr(data,'states') or not arr(biz,'sections'): raise InputError('完整报告不能缺行动、状态决策或商业解释。')
        review=data.get('review',{})
        if not isinstance(review,dict) or review.get('source_fidelity')!='checked' or review.get('independence')!='checked' or not review.get('notes'): raise InputError('需记录真实的原文忠实性与案例独立性复核，脚本不能代替。')
        if data.get('negative_search',{}).get('status') not in {'found','searched_not_found'}: raise InputError('需记录反例搜索及结果，不得编造失败案例。')
    return data


def p(value,cls=''): return f'<p{(" class="+chr(34)+cls+chr(34)) if cls else ""}>{esc(value)}</p>'
def ul(values): return '<ul>'+''.join('<li>'+esc(v)+'</li>' for v in values)+'</ul>' if values else ''
def refs_html(ids): return '<div class="source-ref">依据：'+''.join(f'<a href="#ref-{esc(v)}">{esc(v)}</a>' for v in ids)+'</div>' if ids else ''
def badge(text,kind=''): return f'<span class="flag {kind}">{esc(text)}</span>'
def section_head(number,title,note): return f'<div class="section-heading"><div><p class="section-number">{esc(number)}</p><h2>{esc(title)}</h2>{p(note,"section-note")}</div></div>'


def render_task(t):
    checked=' checked' if t['status']=='done' else ''
    info=''.join('<span>'+esc(v)+'</span>' for v in [t['phase'],t['day'] or '时间待定',t['estimate'],t['owner'],PRIORITIES[t['priority']],STATUSES[t['status']]] if v)
    labels={'action':'怎么做','inputs':'先准备','tool':'工具与入口','deliverable':'交付什么','acceptance':'怎样算做完','on_failure':'失败怎么办','cost':'费用边界','notes':'我的备注'}
    body=''.join(f'<div class="{"wide" if k in {"action","notes"} else ""}"><span class="mini-label">{v}</span>{p(t[k])}</div>' for k,v in labels.items() if t[k])
    body+=f'<div class="wide"><span class="mini-label">任务编号与依赖</span>{p(t["id"]+" · 前置："+("、".join(t["depends_on"]) or "无"))}</div>'
    return f'<article class="task-row{" is-done" if checked else ""}" data-task-id="{esc(t["id"])}"><div class="task-main"><input type="checkbox" class="task-check" aria-label="完成：{esc(t["title"])}" disabled{checked}><div><h4 class="task-title">{esc(t["title"])}</h4><div class="task-meta">{info}</div></div></div><details class="task-details"><summary>步骤、产物与验收</summary><div class="task-detail-grid">{body}</div></details></article>'


def dialogs():
    opts=lambda values:''.join(f'<option value="{k}">{v}</option>' for k,v in values.items())
    field=lambda name,label,control,full=False:f'<label class="field{" full" if full else ""}"><span>{label}</span>{control}</label>'
    def inp(name,typ='text',req=False,extra=''): return f'<input name="{name}" type="{typ}" {"required" if req else ""} {extra}>'
    def area(name,rows=2,req=False): return f'<textarea name="{name}" rows="{rows}" {"required" if req else ""}></textarea>'
    fields=''.join([
        field('title','行动名称 *',inp('title',req=True,extra='maxlength="240"'),True),
        field('phase','阶段',inp('phase',extra='list="phase-options" maxlength="80"')),
        field('day','计划时间窗',inp('day',extra='placeholder="例如 D3 上午 / 下周一"')),
        field('due','截止日期',inp('due','date')),field('owner','负责人',inp('owner')),
        field('status','当前状态','<select name="status">'+opts(STATUSES)+'</select>'),
        field('priority','优先级','<select name="priority">'+opts(PRIORITIES)+'</select>'),
        field('estimate','预计耗时',inp('estimate',extra='placeholder="例如 30分钟；按实际情况调整"')),
        field('cost','预算或费用边界',inp('cost',extra='placeholder="未知则填写待核，不编造数字"')),
        field('action','具体怎么做 *',area('action',3,True),True),
        field('inputs','输入材料',area('inputs')),field('tool','工具与入口',area('tool')),
        field('deliverable','交付什么 *',area('deliverable',2,True)),field('acceptance','怎样算做完 *',area('acceptance',2,True)),
        field('on_failure','失败或受阻时怎么办 *',area('on_failure',2,True),True),
        field('depends_on','前置任务编号',inp('depends_on',extra='placeholder="多个编号用逗号隔开"'),True),
        field('notes','我的备注',area('notes',3),True)
    ])
    return '<dialog id="task-dialog" class="dialog" aria-labelledby="editor-title"><form id="task-form"><header class="dialog-head"><h2 id="editor-title">编辑行动</h2><button type="button" class="btn quiet small" id="editor-close" aria-label="关闭编辑">关闭</button></header><div class="dialog-body"><p id="editing-id" class="small-copy"></p><div class="fields">'+fields+'</div><datalist id="phase-options"></datalist><p id="form-error" class="form-error" role="alert"></p></div><footer class="dialog-footer"><span class="small-copy">只改行动，不改研究原文。</span><div class="btn-group"><button type="button" class="btn" id="editor-cancel">取消</button><button type="submit" class="btn primary">保存行动</button></div></footer></form></dialog><dialog id="confirm-dialog" class="dialog" aria-labelledby="confirm-title"><header class="dialog-head"><h2 id="confirm-title">确认操作</h2></header><div class="dialog-body"><p id="confirm-message"></p></div><footer class="dialog-footer"><div class="btn-group"><button type="button" class="btn" id="confirm-no">取消</button><button type="button" class="btn danger" id="confirm-yes">确认</button></div></footer></dialog><div id="toast" class="toast" role="status" aria-live="polite" hidden><span id="toast-text"></span><button id="toast-undo" type="button" hidden>撤销</button></div>'


def poster_uri():
    return 'data:image/jpeg;base64,'+base64.b64encode((ROOT/'会员体验卡海报.jpg').read_bytes()).decode('ascii')


def referral_card():
    return '<section id="referral" class="referral-card" aria-labelledby="referral-title"><h2 id="referral-title">让AI陪你拆解更多赚钱项目</h2><p>想看看真实项目怎么起步、获客和交付？扫描下方会员体验卡二维码，领取生财有术<strong>3天体验</strong>。</p><a id="referral-link" href="'+REFERRAL_URL+'" target="_blank" rel="noopener noreferrer" aria-label="打开作者的生财有术分享入口"><img id="referral-poster" src="'+poster_uri()+'" alt="生财有术会员体验卡，扫描原图二维码领取3天体验" loading="lazy"></a><p class="small-copy">注册后可连接生财资料，让AI读取你有权访问的文章，结合全网信息分析项目并制定行动计划。暂不加入，也可以继续用全网资料研究。</p><p class="small-copy">这是作者的分享入口，作者可能获得推荐奖励；实际体验和阅读权益以生财账号为准。</p></section>'


def render(data):
    d=validate_data(data)
    css=(ROOT/'assets/report.css').read_text('utf-8');js=(ROOT/'assets/tasks.js').read_text('utf-8')
    brand=read_json(ROOT/'assets/brand.json')
    if not isinstance(brand,dict):raise InputError('brand.json必须为对象。')
    for key in ['name','english_name','mark','tagline']:string(brand.get(key),'品牌.'+key,True,240)
    rid=d['report_id'];revision=d.get('revision') or hashlib.sha256(json.dumps(d,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:16]
    state_data={'schema_version':1,'report_id':rid,'revision':revision,'tasks':d['tasks'],'selected_state':d.get('selected_state',''),'states':[{k:s.get(k,'') for k in ['id','title','evidence','action']} for s in d.get('states',[])]}
    payload=json.dumps(state_data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    h=lambda s:base64.b64encode(hashlib.sha256(s.encode('utf-8')).digest()).decode('ascii')
    csp=f"default-src 'none'; script-src 'sha256-{h(js)}'; style-src 'sha256-{h(css)}'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'"
    nav=[('overview','01','决策速览'),('source','02','原文精读'),('cases','03','同类比较'),('business','04','生意逻辑'),('actions','05','行动工作台'),('states','06','状态与下一步'),('sources','07','来源与边界')]
    doc=['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><meta name="report-id" content="'+esc(rid)+'"><meta name="research-status" content="'+esc(d['research_status'])+'"><meta http-equiv="Content-Security-Policy" content="'+esc(csp)+'"><title>'+esc(d['title'])+' · '+esc(brand['name'])+'</title><style id="vp-style">'+css+'</style></head><body>']
    doc.append('<a class="skip-link" href="#overview">跳到报告正文</a><aside class="sidebar"><a class="brand" href="#overview"><span class="brand-mark" aria-hidden="true">'+esc(brand['mark'])+'</span>'+esc(brand['name'])+'</a><div class="brand-sub">'+esc(brand['english_name'])+'</div><p class="nav-caption">报告导航</p><nav class="nav-links" aria-label="报告目录">'+''.join(f'<a href="#{i}"><span>{n}</span>{label}</a>' for i,n,label in nav)+'</nav><div class="sidebar-foot"><p>'+esc(brand['tagline'])+'</p><p>本地文件 · 无账户 · 无追踪</p></div></aside><div class="shell"><div class="topbar"><span>'+esc(d.get('generated_on','日期未填写'))+' · '+esc(d.get('edition','研究与执行版'))+'</span><a href="#sources">查看研究边界</a></div><main>')
    doc.append('<header class="hero"><h1>'+esc(d['title'])+'</h1>'+p(d['subtitle'],'subtitle')+'<div class="hero-actions"><a class="btn primary" href="#actions">进入行动工作台 <span aria-hidden="true">↗</span></a><button type="button" class="btn js-only inline" data-save-html>保存完整报告</button><button type="button" id="print-report" class="btn quiet js-only inline">打印</button></div><div class="hero-context"><span>'+esc(RESEARCH[d['research_status']])+'</span><span>原文、公开证据与建议分别标记</span><span>待办可编辑，可离线保留</span></div></header>')
    verdict=d['verdict'];project=d.get('project',{})
    doc.append('<section id="overview"><div class="decision"><div class="decision-main"><div class="decision-label">现在的判断</div><h3>'+esc(verdict['decision'])+'</h3>'+p(verdict['reason'])+'</div><div class="decision-side"><div><div class="decision-label">唯一下一步</div>'+p(verdict['next_step'])+'</div><div><div class="decision-label">暂时不要做</div>'+p(verdict.get('avoid','先不要放大未经验证的假设。'))+'</div></div></div><div class="facts-strip">'+''.join('<div class="fact"><span>'+label+'</span><strong>'+esc(project.get(k,'待核'))+'</strong></div>' for k,label in [('buyer','谁会付钱'),('deliverable','买到什么'),('revenue_model','如何收费')])+'</div>')
    if d.get('evidence_boundary'): doc.append('<div class="boundary">'+p(d['evidence_boundary'])+'</div>')
    doc.append('</section><section id="source" class="section">'+section_head('02','先读懂原文','沿作者的章节和因果顺序解读；旁边的建议，不冒充作者已经做过。'))
    if not d.get('source_sections'): doc.append(p('当前输入是项目想法，或主体原文尚未取得。下文不会伪造作者经历。','boundary'))
    for idx,s in enumerate(d.get('source_sections',[]),1):
        doc.append('<article class="chapter" id="chapter-'+esc(s['id'])+'"><div class="chapter-title"><span class="chapter-no">'+str(idx).zfill(2)+'</span><h3>'+esc(s['title'])+'</h3></div><div class="reading">'+p(s['key_point'],'chapter-lead')+''.join(p(v) for v in s['paragraphs'])+refs_html(s.get('source_ids',[])))
        if s.get('takeaways'): doc.append('<div class="takeaway"><div class="takeaway-label">这一步最值得借鉴</div>'+ul(s['takeaways'])+'</div>')
        if s.get('unknowns'): doc.append(p('仍需核实：'+'；'.join(s['unknowns']),'small-copy'))
        doc.append('</div></article>')
    doc.append('</section><section id="cases" class="section">'+section_head('03','把同一门生意，放在一起比较','比较付费人、交付与收费机制，不把“都用了AI”当作同类。公开报价也不等于已核实的到账。'))
    if d.get('cases'):
        doc.append('<div class="table-wrap" tabindex="0" role="region" aria-label="同类项目对照表"><table><thead><tr><th>项目与可比性</th><th>收费与交付</th><th>值得借鉴</th><th>不能直接照搬</th></tr></thead><tbody>')
        for c in d['cases']:
            relationship={'direct':'同机制','adjacent':'相邻机制','counter':'反例/替代'}[c['relationship']]
            doc.append('<tr><td><strong>'+esc(c['name'])+'</strong><br>'+esc(relationship)+'</td><td>'+esc(c['payment_evidence'])+'</td><td>'+esc(c['transferable'])+'</td><td>'+esc(c['risk'])+'</td></tr>')
        doc.append('</tbody></table></div>')
        for c in d['cases']:
            doc.append('<details class="case-detail"><summary>'+esc(c['name'])+' · '+esc(c.get('angle','展开看具体机制'))+'</summary><div class="case-body">')
            labels={'match_reason':'为什么可比','workflow':'从需求到交付','acquisition':'如何获客','costs':'成本与资源','retention':'复购与留存','payment_evidence':'付费证据到哪一步','transferable':'可以借鉴','risk':'不宜照搬'}
            for k,label in labels.items():
                if c.get(k): doc.append('<div><span class="mini-label">'+label+'</span>'+p(c[k])+'</div>')
            doc.append('<div class="span-all">'+refs_html(c.get('source_ids',[]))+'</div></div></details>')
    else: doc.append(p('本轮尚未取得可以独立核读的可比项目。公开网络研究未完成，不将搜索标题当作比较。','boundary'))
    synth=d.get('synthesis',{})
    doc.append('<div class="synthesis"><div><h4>相同规律</h4>'+ul(synth.get('shared',[]))+'</div><div><h4>决定成败的差异</h4>'+ul(synth.get('differences',[]))+'</div></div>')
    negative=d.get('negative_search',{})
    if negative.get('note'): doc.append('<div class="boundary">'+p(negative['note'])+'</div>')
    doc.append('</section><section id="business" class="section">'+section_head('04','从看懂案例，到看清生意','以下为分析与待验证方案；只补作者没讲清楚的地方，不修改原文事实。'))
    business=d.get('business',{})
    if business.get('workflow'): doc.append('<div class="flow">'+''.join('<div class="flow-step"><strong>'+esc(v['title'])+'</strong>'+p(v.get('detail',''))+'</div>' for v in business['workflow'])+'</div>')
    doc.append('<div class="analysis-grid">'+''.join('<div><h4>'+esc(s['title'])+'</h4>'+p(s['text'])+refs_html(s.get('source_ids',[]))+'</div>' for s in business.get('sections',[]))+'</div>')
    if business.get('economic_formula'): doc.append('<div class="takeaway"><div class="takeaway-label">先把账算完整</div>'+p(business['economic_formula'])+p(business.get('economic_note','缺失价格、成本或样本时保持未知；不以作者峰值收入代替自己的预期。'),'small-copy')+'</div>')
    doc.append('</section><section id="actions" class="section">'+section_head('05','把报告，变成今天能做的事','每项行动都有输入、产物、通过标准和失败分支。修改只影响你的计划，不会改写研究依据。'))
    doc.append('<div class="roadmap">'+''.join('<div class="milestone"><span>'+esc(m['horizon'])+'</span><h4>'+esc(m['title'])+'</h4>'+p(m['acceptance'])+'</div>' for m in d.get('milestones',[]))+'</div>')
    doc.append(p(d.get('schedule_note','这是建议排期，不是作者实测耗时；按自己的时间调整，不以任务打勾冒充真实收入。'),'small-copy'))
    doc.append('<p class="no-js-note">当前查看器未启用交互。正文和行动清单仍可阅读；请将HTML文件用浏览器打开后编辑。</p><div id="local-banner" class="local-banner" hidden></div><div class="board"><div class="board-top"><div><h3>我的行动清单</h3><p>先做最关键的一项，再根据结果调整。</p></div><div class="board-actions js-only"><button id="undo" type="button" class="btn small" disabled>撤销</button><button id="backup-tasks" type="button" class="btn small">备份待办</button><button id="import-tasks" type="button" class="btn small">导入</button><button id="add-task" type="button" class="btn primary small">＋ 新增行动</button></div></div><div class="filters js-only"><label class="search-filter"><span class="visually-hidden">搜索待办</span><input id="search" type="search" maxlength="240" placeholder="搜索任务、负责人或备注"></label><label><span class="visually-hidden">按状态筛选</span><select id="status-filter"><option value="">所有状态</option>'+''.join(f'<option value="{k}">{v}</option>' for k,v in STATUSES.items())+'</select></label><label><span class="visually-hidden">按阶段筛选</span><select id="phase-filter"><option value="">所有阶段</option></select></label><label class="sort-filter"><span class="visually-hidden">任务排序</span><select id="sort-filter"><option value="original">计划顺序</option><option value="priority">优先级</option><option value="due">截止日期</option></select></label></div><div class="list-context js-only"><span id="task-count">当前待办</span><button id="reset-filters" type="button" class="btn quiet small">清除筛选</button></div><div id="task-list">'+''.join(render_task(t) for t in d['tasks'])+'</div><div id="tasks-empty" class="empty" hidden><h4>没有匹配的行动</h4><p>清除筛选，或新增一项更具体的任务。</p></div><div id="storage-bar" class="storage-bar"><span id="storage-message">浏览器本地保存 · 换设备前请保存完整报告</span><div class="board-actions js-only"><button id="export-csv" type="button" class="btn quiet small">导出CSV</button><button type="button" class="btn quiet small" data-save-html>保存完整报告</button></div></div></div><input type="file" id="import-file" accept=".json,application/json" hidden>')
    doc.append('</section><section id="states" class="section">'+section_head('06','卡在哪一步，就先解决哪一步','这是受行动影响的有限状态计划。没有真实同口径样本时，转移概率保持未知。'))
    if d.get('states'):
        doc.append('<div class="takeaway"><label class="field"><span>按已有证据选择当前状态</span><select id="state-select" class="js-only"><option value="">尚未选择</option>'+''.join('<option value="'+esc(s['id'])+'">'+esc(s['id']+' · '+s['title'])+'</option>' for s in d['states'])+'</select></label><h4 class="analysis-block">下一步只做这件事</h4><p id="state-action">先核证据条件，再选择状态。完成待办不代表已经成交。</p><p id="state-evidence" class="small-copy">没有真实样本，不计算成功率。</p></div>')
    for s in d.get('states',[]):
        doc.append('<div class="state-row"><div class="state-code '+('stop' if s.get('kind')=='stop' else '')+'">'+esc(s['id'])+'</div><div><h4>'+esc(s['title'])+'</h4>'+p(s['evidence'])+'</div><div class="state-next"><span class="mini-label">下一动作</span>'+p(s['action'])+'<span class="mini-label">进入下一步 / 回退或停止</span>'+p(s['advance']+'；'+s['stop'])+p('转移概率：'+s.get('probability','未知'),'small-copy')+'</div></div>')
    doc.append(p(d.get('markov_note','状态必须覆盖重要历史条件，例如客户成熟度、上次失败与资源可用性。观察窗口未结束不算失败；多个操作步骤不等于多个独立试验。'),'small-copy'))
    doc.append('</section><section id="sources" class="section">'+section_head('07','依据在哪里，未知又在哪里','引用用于支持具体陈述。官方产品页面能证明其公开服务安排，不能独立证明经营收入。'))
    for s in d.get('sources',[]):
        link=f'<a href="{esc(safe_url(s.get("url","")))}" target="_blank" rel="noopener noreferrer">{esc(s["title"])}</a>' if s.get('url') else '<strong>'+esc(s['title'])+'</strong>'
        doc.append('<div class="source-item" id="ref-'+esc(s['id'])+'"><span class="ref-id">'+esc(s['id'])+'</span><div>'+link+p('来源：'+s.get('publisher','提供材料')+' · 阅读：'+s.get('read_status','not_read')+' · 读取日：'+s.get('accessed_on','未记录'))+p(s.get('supports',''))+p(s.get('limitations',''))+'</div></div>')
    if d.get('limitations'): doc.append('<div class="sources-note"><h4>仍需补证</h4>'+ul(d['limitations'])+'</div>')
    doc.append('</section><footer class="report-end"><span>项目研判 · Venture Playbook</span><span>'+esc(rid)+' · '+esc(d.get('generated_on',''))+'</span></footer>'+referral_card()+'</main></div>'+dialogs()+'<script id="vp-data" type="application/json">'+payload+'</script><script id="vp-runtime">'+js+'</script></body></html>')
    return ''.join(doc)


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.ids=[];self.links=[];self.errors=[];self.tags=set();self.script_id='';self.scripts={};self.metas={};self.lang='';self.styles=[];self.in_style=False;self.referral_image={};self.referral_link={}
    def handle_starttag(self,tag,attributes):
        a=dict(attributes);self.tags.add(tag)
        if a.get('id'): self.ids.append(a['id'])
        if tag=='html': self.lang=a.get('lang','')
        if tag=='meta':
            if a.get('name'):self.metas[a['name']]=a.get('content','')
            if a.get('charset'):self.metas['charset']=a['charset']
            if a.get('http-equiv')=='Content-Security-Policy':self.metas['csp']=a.get('content','')
        if tag in {'iframe','object','embed','base'}:self.errors.append('禁止嵌入外部可执行页面或base标签。')
        if any(k.lower().startswith('on') for k in a):self.errors.append('禁止HTML内联事件处理器。')
        if tag=='form' and a.get('action'):self.errors.append('报告不能向外提交表单。')
        for key in ['href','src','action']:
            value=a.get(key,'').strip()
            if re.match(r'(?i)javascript:|vbscript:',value):self.errors.append('含脚本网址。')
        if tag=='a':self.links.append(a.get('href',''))
        if tag=='a' and a.get('id')=='referral-link':self.referral_link=a
        if tag=='img' and a.get('id')=='referral-poster':self.referral_image=a
        if tag=='link':self.errors.append('页面不应依赖外部样式或字体。')
        if tag=='script':
            self.script_id=a.get('id','')
            if a.get('src') or self.script_id not in {'vp-data','vp-runtime'}:self.errors.append('存在非内置脚本。')
            self.scripts.setdefault(self.script_id,'')
        if tag=='style':self.in_style=True
        if tag=='img' and a.get('src','') and not a['src'].startswith('data:'):self.errors.append('非自包含图片。')
    def handle_data(self,data):
        if self.script_id:self.scripts[self.script_id]=self.scripts.get(self.script_id,'')+data
        if self.in_style:self.styles.append(data)
    def handle_endtag(self,tag):
        if tag=='script':self.script_id=''
        if tag=='style':self.in_style=False


def check_html(path):
    text=path.read_text('utf-8');inv=Inventory();inv.feed(text);errors=list(inv.errors)
    if path.suffix.lower()!='.html':errors.append('扩展名必须为.html。')
    if not re.match(r'\s*<!doctype html>',text,re.I):errors.append('缺少doctype。')
    if not {'html','head','body','h1','style'}.issubset(inv.tags):errors.append('页面结构不完整。')
    if inv.metas.get('charset','').lower()!='utf-8' or not inv.lang.startswith('zh') or 'viewport' not in inv.metas:errors.append('缺少中文、UTF-8或移动端声明。')
    if len(inv.ids)!=len(set(inv.ids)):errors.append('DOM编号重复。')
    if inv.referral_image.get('src')!=poster_uri():errors.append('缺少原始分享海报或图卡已被替换。')
    if inv.referral_link.get('href')!=REFERRAL_URL:errors.append('缺少作者固定分享入口或链接已被替换。')
    if not re.search(r'<section\b[^>]*id="referral"[^>]*>.*?</section>\s*</main>',text,re.S):errors.append('分享图卡必须位于正文最底部。')
    for value in inv.links:
        if value.startswith('#') and value[1:] not in inv.ids:errors.append('目录锚点无目标：'+value)
    if inv.scripts.get('vp-runtime','')!=(ROOT/'assets/tasks.js').read_text('utf-8'):errors.append('交互脚本与受信任内置版本不一致。')
    try:
        state=json.loads(inv.scripts.get('vp-data',''))
        if state.get('schema_version')!=1:raise InputError('交互数据版本无效。')
        validate_tasks(state['tasks'])
    except (ValueError,KeyError,TypeError) as exc:errors.append('交互数据无效：'+str(exc))
    if '</body>' not in text or '</html>' not in text:errors.append('缺少文档结尾。')
    for required in ['overview','source','cases','business','actions','states','sources','task-dialog','task-list','add-task','import-tasks']:
        if required not in inv.ids:errors.append('缺少区域或功能：'+required)
    if "connect-src 'none'" not in inv.metas.get('csp',''):errors.append('缺少禁止网络请求的CSP。')
    runtime=inv.scripts.get('vp-runtime','')
    needed="'sha256-"+base64.b64encode(hashlib.sha256(runtime.encode()).digest()).decode()+"'"
    if needed not in inv.metas.get('csp',''):errors.append('脚本CSP指纹不匹配。')
    css=''.join(inv.styles)
    if css!=(ROOT/'assets/report.css').read_text('utf-8'):errors.append('样式与内置版本不一致。')
    css_hash="'sha256-"+base64.b64encode(hashlib.sha256(css.encode()).digest()).decode()+"'"
    if css_hash not in inv.metas.get('csp',''):errors.append('样式CSP指纹不匹配。')
    return {'passed':not errors,'level':'local_structure_and_trusted_code','semantic_research_verified':False,'browser_verified':False,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'errors':errors}


class TextExtractor(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.skip=[];self.parts=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','head','noscript','template'}:self.skip.append(tag)
        if not self.skip and tag in {'p','div','section','article','h1','h2','h3','h4','li','br','tr'}:self.parts.append('\n')
        if not self.skip and tag in {'h1','h2','h3','h4'}:self.parts.append('#'*int(tag[1])+' ')
        if not self.skip and tag=='a':
            link=dict(attrs).get('href','')
            if link and link not in self.links:self.links.append(link)
    def handle_endtag(self,tag):
        if self.skip and self.skip[-1]==tag:self.skip.pop()
        if not self.skip and tag in {'p','div','section','article','h1','h2','h3','h4','li','tr'}:self.parts.append('\n')
    def handle_data(self,text):
        if not self.skip:self.parts.append(text)


def outline(path):
    if path.stat().st_size>MAX_JSON:raise InputError('原始材料超过8MB，请按章节拆分。')
    if path.suffix.lower() not in {'.txt','.md','.markdown','.html','.htm'}:raise InputError('outline只处理UTF-8文字或HTML；文档/图片需由宿主读取。')
    text=path.read_text('utf-8-sig');links=[]
    if path.suffix.lower() in {'.html','.htm'}:
        parser=TextExtractor();parser.feed(text);text=''.join(parser.parts);links=parser.links
    sections=[];title='开场';body=[]
    def flush():
        if body:sections.append({'id':'source-'+str(len(sections)+1),'title':title,'original_text':'\n'.join(body).strip()})
    for line in text.splitlines():
        if re.match(r'^\s*#{1,6}\s+\S|^第[一二三四五六七八九十百\d]+[章节][\s｜:：]|^[一二三四五六七八九十]+[、.．]\s*\S',line):
            flush();title=re.sub(r'^\s*#{1,6}\s+','',line).strip();body=[]
        elif line.strip():body.append(line)
    flush()
    return {'input_name':path.name,'extraction_only':True,'links_to_review':links,'warning':'仅按标题切分，不是精读结论。跨页、图片和正文外链由Agent另行核读。','sections':sections}


def csv_cell(v):
    s=' | '.join(v) if isinstance(v,list) else str(v or '')
    return "'"+s if re.match(r'^[\s\ufeff]*[=+\-@]',s) else s


def export_tasks(data):
    tasks=validate_tasks(data.get('tasks',[]));s=io.StringIO();writer=csv.writer(s)
    columns=TASK_FIELDS+['depends_on'];writer.writerow(columns)
    for t in tasks:writer.writerow([csv_cell(t.get(k,'')) for k in columns])
    return '\ufeff'+s.getvalue()


def scaffold(title):
    slug='project-'+hashlib.sha256(title.encode()).hexdigest()[:10]
    return {'schema_version':1,'report_id':slug,'title':title,'subtitle':'从原文与公开证据，走到可执行的小规模验证。','generated_on':date.today().isoformat(),'research_status':'draft','source_mode':'article','verdict':{'decision':'等待完成原文精读','reason':'当前仅初始化工作文件，没有把作者收入或搜索结果当作已验证事实。','next_step':'读取提供的主体原文，保留作者自然章节。','avoid':'不要先生成泛化商业计划或编造同行。'},'project':{'buyer':'待原文明确','deliverable':'待核','revenue_model':'待核'},'evidence_boundary':'这是一份待填充的研究工作文件，不是完成报告。','sources':[],'expected_source_sections':[],'source_sections':[],'cases':[],'synthesis':{'shared':[],'differences':[]},'negative_search':{'status':'not_started','note':'反例搜索尚未执行。'},'business':{'workflow':[],'sections':[]},'milestones':[],'tasks':[],'states':[],'limitations':['尚未读取原文与网络证据。'],'review':{'source_fidelity':'not_checked','independence':'not_checked','notes':''}}


def queries(data):
    project=data.get('project',{});buyer=project.get('buyer','目标客户');deliverable=project.get('deliverable',data.get('title','产品'));model=project.get('revenue_model','收费方式')
    terms=[f'{buyer} {deliverable} {model} 创业 复盘',f'{deliverable} 定价 交付流程 案例',f'"{deliverable}" 失败 退款 停止',f'{deliverable} alternative pricing workflow',f'{deliverable} founder retrospective lessons learned']
    return '# 公开网络研究清单\n\n以下只生成搜索词，没有发起搜索，也没有得到任何案例。用宿主的真实网页搜索执行。\n\n'+''.join('- '+x+'\n' for x in terms)+'\n先打开原始产品/创作者材料，检查经营主体独立性，再核收费人群、交付和复购。搜索摘要、转载数量、官网定价不能充当真实收益。记录找不到的反例，不虚构。\n'


def dedupe(data):
    if not isinstance(data,list):raise InputError('去重输入应为来源数组。')
    out=[];mapping={}
    for source in data:
        if not isinstance(source,dict):raise InputError('来源条目必须为对象。')
        u=canonical_url(source.get('url',''));copy=dict(source);copy['canonical_url']=u
        if u not in mapping:mapping[u]=copy;copy['duplicate_urls']=[];out.append(copy)
        else:mapping[u]['duplicate_urls'].append(source.get('url',''))
    return {'sources':out,'independence_checked':False,'note':'只去网址重复，不自动认定不同域名或不同作者是独立经营主体。'}


def main(argv=None):
    parser=argparse.ArgumentParser(description='项目研判离线工具：不联网、不发信、不计算经营收益。')
    sub=parser.add_subparsers(dest='cmd',required=True)
    sub.add_parser('doctor',help='检查本地运行条件，不安装依赖')
    init=sub.add_parser('init',help='创建研究数据骨架');init.add_argument('--title',required=True);init.add_argument('--out',required=True,type=Path)
    for name,help_text in [('build','生成独立交互HTML'),('validate','检查研究数据结构'),('check','检查HTML与内置脚本'),('outline','保留原始文字并提取章节'),('queries','生成网络检索词，不替代实际搜索'),('dedupe','规范网址并去重'),('export-tasks','导出安全的待办CSV')]:
        cmd=sub.add_parser(name,help=help_text);cmd.add_argument('input',type=Path)
        if name not in {'validate','check'}:cmd.add_argument('--out',type=Path,required=True)
    merge=sub.add_parser('merge-tasks',help='将客户修改合入项目数据');merge.add_argument('input',type=Path);merge.add_argument('--tasks',type=Path,required=True);merge.add_argument('--out',type=Path,required=True)
    for cmd in sub.choices.values():
        if any(a.dest=='out' for a in cmd._actions):cmd.add_argument('--force',action='store_true',help='显式允许覆盖输出；原始输入不自动改写')
    args=parser.parse_args(argv)
    try:
        if args.cmd=='doctor':
            print(json.dumps({'python_supported':sys.version_info>=(3,10),'python':sys.version.split()[0],'assets_present':all((ROOT/'assets'/x).is_file() for x in ['report.css','tasks.js','brand.json']),'core_dependencies':'Python standard library only','search':'由宿主提供；本脚本未测试联网','browser':'HTML交互需现代浏览器；本命令未验证实显'},ensure_ascii=False,indent=2));return 0
        if args.cmd=='init':value=scaffold(args.title);content=json.dumps(value,ensure_ascii=False,indent=2)
        elif args.cmd=='build':content=render(read_json(args.input))
        elif args.cmd=='validate':
            validate_data(read_json(args.input));print('PASS：数据结构有效。不是对研究真实性、收益或浏览器显示的认证。');return 0
        elif args.cmd=='check':
            result=check_html(args.input);print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['passed'] else 1
        elif args.cmd=='outline':content=json.dumps(outline(args.input),ensure_ascii=False,indent=2)
        elif args.cmd=='queries':content=queries(read_json(args.input))
        elif args.cmd=='dedupe':content=json.dumps(dedupe(read_json(args.input)),ensure_ascii=False,indent=2)
        elif args.cmd=='export-tasks':content=export_tasks(read_json(args.input))
        elif args.cmd=='merge-tasks':
            data=read_json(args.input);backup=read_json(args.tasks)
            if backup.get('schema_version')!=1 or backup.get('report_id')!=data.get('report_id'):raise InputError('备份不属于该项目，未合入。')
            data['tasks']=validate_tasks(backup.get('tasks'));data['selected_state']=backup.get('selected_state','');data.pop('revision',None);validate_data(data);content=json.dumps(data,ensure_ascii=False,indent=2)
        if hasattr(args,'input') and args.out.resolve()==args.input.resolve():raise InputError('输出不能覆盖原始输入；请指定新文件。')
        out=atomic_write(args.out,content,args.force);print('已写入：'+str(out));return 0
    except (InputError,OSError,UnicodeError,RecursionError,KeyError,TypeError) as exc:
        print('未完成：'+str(exc),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
