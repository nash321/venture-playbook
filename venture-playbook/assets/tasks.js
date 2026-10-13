/* Venture Playbook: trusted offline UI. No network, eval, third-party runtime or input HTML. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const payloadEl = $('vp-data');
  if (!payloadEl) return;
  const statuses = {todo:'待开始', doing:'进行中', done:'已完成', blocked:'受阻'};
  const priorities = {high:'优先', normal:'正常', low:'稍后'};
  const fields = ['id','title','phase','day','due','owner','priority','status','estimate','cost','inputs','action','tool','deliverable','acceptance','on_failure','notes'];
  const icons = {
    edit:'M12 20h9 M16.5 3.5a2.12 2.12 0 0 1 3 3L9 17l-4 1 1-4Z',
    trash:'M3 6h18 M9 6V4h6v2 M5 6l1 14h12l1-14 M10 10v6 M14 10v6',
    close:'M6 6l12 12 M18 6L6 18',
    up:'m6 14 6-6 6 6', down:'m6 10 6 6 6-6'
  };
  const clone = (v) => JSON.parse(JSON.stringify(v));
  const safeJSON = (v) => JSON.stringify(v).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');
  function el(tag, attrs={}, text=null) {
    const node=document.createElement(tag);
    for (const [k,v] of Object.entries(attrs)) {
      if(k==='class') node.className=v;
      else if(k==='checked') {node.checked=v;if(v) node.setAttribute('checked','');}
      else node.setAttribute(k,String(v));
    }
    if(text!==null) node.textContent=String(text);
    return node;
  }
  function icon(name) {
    const s=document.createElementNS('http://www.w3.org/2000/svg','svg');
    for (const [k,v] of Object.entries({viewBox:'0 0 24 24',width:17,height:17,fill:'none',stroke:'currentColor','stroke-width':'1.65','stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true'})) s.setAttribute(k,String(v));
    const p=document.createElementNS(s.namespaceURI,'path');p.setAttribute('d',icons[name]);s.append(p);return s;
  }
  function textField(value, name, required=false, limit=16000) {
    if (value===undefined || value===null) value='';
    if(typeof value!=='string') throw new Error(`${name}必须是文字。`);
    if(value.length>limit) throw new Error(`${name}太长，请缩短后重试。`);
    if(required && !value.trim()) throw new Error(`请填写${name}。`);
    return value;
  }
  function validTasks(raw) {
    if(!Array.isArray(raw) || raw.length>1000) throw new Error('待办须为数组，单份报告不超过1000项。');
    const tasks=raw.map((v)=>{
      if(!v || typeof v!=='object' || Array.isArray(v)) throw new Error('待办记录格式不正确。');
      const t={};
      for(const k of fields) t[k]=textField(v[k],k,k==='id'||k==='title',k==='title'?240:16000);
      if(!/^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/.test(t.id)) throw new Error('任务编号须由字母、数字、连字符或下划线组成。');
      t.phase=t.phase.trim() || '未分阶段';
      t.status=t.status || 'todo';t.priority=t.priority || 'normal';
      if(!Object.hasOwn(statuses,t.status) || !Object.hasOwn(priorities,t.priority)) throw new Error('任务状态或优先级无效。');
      if(t.due && (!/^\d{4}-\d{2}-\d{2}$/.test(t.due) || !Number.isFinite(Date.parse(t.due+'T00:00:00Z')) || new Date(t.due+'T00:00:00Z').toISOString().slice(0,10)!==t.due)) throw new Error('截止日期无效。');
      if(v.depends_on!==undefined && !Array.isArray(v.depends_on)) throw new Error('前置任务必须是编号数组。');
      t.depends_on=(v.depends_on||[]).map(x=>textField(x,'前置任务',true,80));
      if(new Set(t.depends_on).size!==t.depends_on.length) throw new Error('前置任务编号重复。');
      return t;
    });
    const ids=new Set(tasks.map(t=>t.id));
    if(ids.size!==tasks.length) throw new Error('待办编号重复，未覆盖当前数据。');
    const graph=new Map(tasks.map(t=>[t.id,t.depends_on]));
    for(const t of tasks) for(const dep of t.depends_on) if(!ids.has(dep)) throw new Error(`任务 ${t.id} 引用了不存在的前置任务 ${dep}。`);
    const active=new Set(),visited=new Set();
    function visit(id) {
      if(active.has(id)) throw new Error('任务依赖出现循环，请解除后再保存。');
      if(visited.has(id)) return;
      active.add(id);for(const dep of graph.get(id)) visit(dep);active.delete(id);visited.add(id);
    }
    for(const id of ids) visit(id);
    for(const t of tasks) if(t.status==='done' && t.depends_on.some(id=>tasks.find(v=>v.id===id).status!=='done')) throw new Error('已完成任务不能依赖未完成任务。');
    if(new Blob([JSON.stringify(tasks)]).size>2000000) throw new Error('待办数据过大，请拆分项目；需保持备份可恢复。');
    return tasks;
  }
  let base;
  try {
    base=JSON.parse(payloadEl.textContent);
    if(base.schema_version!==1 || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(base.report_id)) throw new Error('报告版本或编号不受支持。');
    base.tasks=validTasks(base.tasks);
  } catch(e) {
    $('storage-message').textContent='交互数据未通过检查。正文仍可阅读；请用原始资料重新生成报告。';
    $('storage-bar').classList.add('warning');return;
  }
  const key='venture-playbook:tasks:v1:'+base.report_id+':'+base.revision;
  let state={schema_version:1,report_id:base.report_id,base_revision:base.revision,tasks:clone(base.tasks),selected_state:base.selected_state||'',updated_at:''};
  let storageOK=false,history=[],toastTimer,editId=null,lastFocus=null,askResolve=null,editorTimer,editorSaved=false,editorComposing=false;
  const banner=(message)=>{const n=$('local-banner');n.textContent=message;n.hidden=false;};
  try {
    const saved=localStorage.getItem(key);
    if(saved) {
      const previous=JSON.parse(saved);
      if(previous.schema_version!==1 || previous.report_id!==base.report_id) throw new Error('进度版本不匹配');
      if(previous.base_revision===base.revision) {
        state={...state,tasks:validTasks(previous.tasks),selected_state:textField(previous.selected_state,'当前阶段'),updated_at:textField(previous.updated_at,'更新时间')};
      } else banner('检测到另一修订版的本地进度。本页先保留文件中的待办，旧进度不会自动覆盖；需要迁移时请使用备份导入。');
    }
    const probe=key+':probe';localStorage.setItem(probe,'ok');storageOK=localStorage.getItem(probe)==='ok';localStorage.removeItem(probe);
  } catch(e) {banner('本地存储不可用或旧进度无法读取。当前修改仍可使用，请点击“保存完整报告”或“备份待办”留存。');}
  function updateStorageLabel(saved=false) {
    const bar=$('storage-bar'),msg=$('storage-message');
    bar.classList.toggle('warning',!storageOK);
    msg.textContent=storageOK?(saved?'已自动保存到本浏览器 · 文件本身尚未改写':'浏览器自动保存 · 移动或分享前请保存完整报告'):'仅本次打开有效 · 请保存完整报告或备份待办';
  }
  function persist() {
    state.updated_at=new Date().toISOString();
    try {const raw=JSON.stringify(state);localStorage.setItem(key,raw);storageOK=localStorage.getItem(key)===raw;} catch(e) {storageOK=false;}
    updateStorageLabel(true);
  }
  function snapshot() {history.push(clone(state));if(history.length>20) history.shift();$('undo').disabled=false;}
  function commit(tasks,message) {
    const checked=validTasks(tasks);snapshot();state.tasks=checked;persist();render();notify(message,true);
  }
  function notify(message,undo=false) {
    clearTimeout(toastTimer);$('toast-text').textContent=message;$('toast-undo').hidden=!undo;$('toast').hidden=false;
    toastTimer=setTimeout(()=>{$('toast').hidden=true;},6500);
  }
  function undo() {
    if(!history.length) return;
    state=history.pop();persist();render();showState();$('undo').disabled=!history.length;notify('已撤销上一步。');
  }
  function unfinished(t) {return t.depends_on.filter(id=>state.tasks.find(v=>v.id===id)?.status!=='done');}
  function changeStatus(id,status) {
    const task=state.tasks.find(t=>t.id===id);if(!task) return;
    if(status==='done' && unfinished(task).length) {notify('先完成前置任务：'+unfinished(task).join('、')+'，或编辑依赖关系。');render();return;}
    // Do not allow a completed dependent to keep a false dependency state.
    if(task.status==='done' && status!=='done') {
      const dependents=state.tasks.filter(t=>t.status==='done' && t.depends_on.includes(id));
      if(dependents.length) {notify('已有完成任务依赖本项，请先调整后续任务状态。');render();return;}
    }
    const next=clone(state.tasks);next.find(t=>t.id===id).status=status;commit(next,'任务状态已更新。');
  }
  function button(label,name,fn) {const n=el('button',{type:'button',class:'icon-button',title:label,'aria-label':label});n.append(icon(name));n.addEventListener('click',fn);return n;}
  function manualOrder() {
    return $('sort-filter').value==='original' && ['search','phase-filter','status-filter'].every(id=>!$(id).value.trim());
  }
  function moveTask(id,direction) {
    if(!manualOrder()) {notify('请清除筛选，并切回“我的顺序”后调整。');return;}
    const from=state.tasks.findIndex(t=>t.id===id),to=from+direction;
    if(from<0 || to<0 || to>=state.tasks.length) return;
    const next=clone(state.tasks);[next[from],next[to]]=[next[to],next[from]];
    commit(next,direction<0?'任务已上移。':'任务已下移。');
    const row=document.querySelector(`[data-task-id="${id}"]`);
    const preferred=row.querySelector(`[data-move="${direction}"]`);
    (preferred.disabled?row.querySelector('[data-move]:not(:disabled)'):preferred)?.focus();
  }
  function renderTask(t,interactive=true) {
    const row=el('article',{class:'task-row'+(t.status==='done'?' is-done':''),'data-task-id':t.id});
    const main=el('div',{class:'task-main'});
    const ck=el('input',{type:'checkbox',class:'task-check','aria-label':'完成：'+t.title,checked:t.status==='done'});
    if(interactive) ck.addEventListener('change',()=>changeStatus(t.id,ck.checked?'done':'todo'));
    else ck.disabled=true;
    const middle=el('div');middle.append(el('h4',{class:'task-title'},t.title));
    const meta=el('div',{class:'task-meta'});
    meta.append(el('span',{class:'phase'},t.phase),el('span',{},t.day||'时间待定'));
    if(t.due) meta.append(el('span',{},'截止 '+t.due));
    if(t.estimate) meta.append(el('span',{},t.estimate));
    if(t.owner) meta.append(el('span',{},t.owner));
    meta.append(el('span',{class:'priority-'+t.priority},priorities[t.priority]));
    if(interactive) {
      const sel=el('select',{class:'task-status','aria-label':'状态：'+t.title});
      for(const [k,v] of Object.entries(statuses)) sel.append(el('option',{value:k},v));
      sel.value=t.status;sel.addEventListener('change',()=>changeStatus(t.id,sel.value));meta.append(sel);
    } else meta.append(el('span',{},statuses[t.status]));
    middle.append(meta);const actions=el('div',{class:'task-buttons js-only'});
    if(interactive) {
      const index=state.tasks.findIndex(v=>v.id===t.id);
      const up=button('上移：'+t.title,'up',()=>moveTask(t.id,-1)),down=button('下移：'+t.title,'down',()=>moveTask(t.id,1));
      up.dataset.move='-1';down.dataset.move='1';
      up.disabled=!manualOrder() || index===0;down.disabled=!manualOrder() || index===state.tasks.length-1;
      actions.append(up,down,button('编辑：'+t.title,'edit',()=>openEditor(t.id)),button('删除：'+t.title,'trash',()=>deleteTask(t.id)));
    }
    main.append(ck,middle,actions);row.append(main);
    const details=el('details',{class:'task-details'});details.append(el('summary',{},'怎么做、做完检查什么'));
    const grid=el('div',{class:'task-detail-grid'});
    const labels={action:'怎么做',inputs:'先准备',tool:'工具与入口',deliverable:'交付什么',acceptance:'怎样算做完',on_failure:'失败怎么办',cost:'费用边界',notes:'我的备注'};
    for(const [k,label] of Object.entries(labels)) if(t[k]) {const n=el('div',{class:k==='action'||k==='notes'?'wide':''});n.append(el('span',{class:'mini-label'},label),el('p',{},t[k]));grid.append(n);}
    const dep=el('div',{class:'wide'});dep.append(el('span',{class:'mini-label'},'任务编号与先后顺序'),el('p',{},t.id+' · 前置：'+(t.depends_on.join('、')||'无')));grid.append(dep);details.append(grid);row.append(details);return row;
  }
  function options(select,values,first) {
    const old=select.value;select.replaceChildren(el('option',{value:''},first));for(const v of values) select.append(el('option',{value:v},v));select.value=values.includes(old)?old:'';
  }
  function updateExampleNote() {
    const note=$('action-example-note');if(!note) return;
    const id=note.dataset.exampleTaskId,present=state.tasks.some(t=>t.id===id);
    note.textContent='这是本报告补充的说明示例，不是作者经历或已执行结果。'+(present?
      '对应行动：'+id+'；完整输入、产物与停止条件仍在清单中。':
      '原对应行动 '+id+' 已从当前计划删除；示例保留供理解原计划，不代表需要恢复执行。');
  }
  function render() {
    options($('phase-filter'),[...new Set(state.tasks.map(t=>t.phase))],'所有阶段');
    const q=$('search').value.trim().toLocaleLowerCase(),phase=$('phase-filter').value,status=$('status-filter').value,sort=$('sort-filter').value;
    let visible=state.tasks.filter(t=>(!phase||t.phase===phase)&&(!status||t.status===status)&&(!q||[t.title,t.action,t.inputs,t.owner,t.notes,t.deliverable].join(' ').toLocaleLowerCase().includes(q)));
    if(sort==='due') visible=visible.slice().sort((a,b)=>(a.due||'9999').localeCompare(b.due||'9999'));
    if(sort==='priority') {const rank={high:0,normal:1,low:2};visible=visible.slice().sort((a,b)=>rank[a.priority]-rank[b.priority]);}
    $('task-list').replaceChildren(...visible.map(t=>renderTask(t)));
    $('tasks-empty').hidden=visible.length!==0;
    $('task-count').textContent=`显示 ${visible.length} 项 · 全部 ${state.tasks.length} 项`;
    $('order-hint').textContent=manualOrder()?'用每项右侧的上下箭头调整顺序，可以撤销。':'调整顺序：先清除筛选，再切回“我的顺序”。';
    $('undo').disabled=!history.length;
    const dl=$('phase-options');dl.replaceChildren(...[...new Set(state.tasks.map(t=>t.phase))].map(v=>el('option',{value:v})));
    updateExampleNote();
  }
  function newId() {return 'u-'+(globalThis.crypto?.randomUUID?crypto.randomUUID().replaceAll('-',''):Date.now().toString(36)+Math.random().toString(36).slice(2));}
  function openEditor(id=null) {
    if(typeof $('task-dialog').showModal!=='function') {notify('当前浏览器不支持编辑弹窗，请使用较新的Chrome、Edge、Firefox或Safari。');return;}
    clearTimeout(editorTimer);editorSaved=false;editorComposing=false;
    editId=id;lastFocus=document.activeElement;const t=state.tasks.find(v=>v.id===id)||{id:newId(),title:'',phase:'准备',day:'',due:'',owner:'我',priority:'normal',status:'todo',depends_on:[]};
    const form=$('task-form');form.reset();$('form-error').textContent='';$('editor-save-status').textContent='有效修改会自动保存；新增行动请填齐必填项。';$('editor-title').textContent=id?'编辑行动':'新增行动';$('editing-id').textContent='任务编号：'+t.id;
    for(const k of fields) if(k!=='id' && form.elements.namedItem(k)) form.elements.namedItem(k).value=t[k]||'';
    form.elements.namedItem('depends_on').value=t.depends_on.join(', ');form.dataset.newId=t.id;
    $('task-dialog').showModal();form.elements.namedItem('title').focus();
  }
  function closeEditor() {clearTimeout(editorTimer);$('task-dialog').close();editorSaved=false;const focus=lastFocus?.isConnected?lastFocus:document.querySelector(`[data-task-id="${editId}"] button[aria-label^="编辑"]`)||$('add-task');focus.focus();}
  function saveEditor(close=false) {
    clearTimeout(editorTimer);
    if(editorComposing || !$('task-dialog').open)return false;
    const form=$('task-form');const t={id:editId||form.dataset.newId};
    for(const k of fields) if(k!=='id') t[k]=String(form.elements.namedItem(k)?.value||'').trim();
    t.depends_on=String(form.elements.namedItem('depends_on').value).split(/[,，\n]/).map(x=>x.trim()).filter(Boolean);
    const next=clone(state.tasks),idx=next.findIndex(v=>v.id===t.id);
    if(idx<0) next.push(t);else next[idx]=t;
    try {
      for(const [name,label] of [['title','行动名称'],['action','具体步骤'],['deliverable','交付物'],['acceptance','验收标准'],['on_failure','失败分支']]) if(!t[name])throw new Error('请填写'+label+'。');
      const checked=validTasks(next);
      for(const item of checked) if(item.status==='done' && item.depends_on.some(id=>checked.find(v=>v.id===id).status!=='done')) throw new Error('已完成任务不能依赖未完成任务，请检查状态。');
      if(JSON.stringify(checked)!==JSON.stringify(state.tasks)) {
        if(!editorSaved){snapshot();editorSaved=true;}
        if(!editId){for(const id of ['search','phase-filter','status-filter']) $(id).value='';$('sort-filter').value='original';}
        editId=t.id;state.tasks=checked;persist();render();
      }
      $('editor-save-status').textContent=editorSaved?(storageOK?'已自动保存到本浏览器；可撤销本次编辑。':'仅本次打开有效；请保存完整报告或备份待办。'):'没有新的修改；有效修改会自动保存。';
      $('form-error').textContent='';if(close)closeEditor();return true;
    } catch(err) {$('form-error').textContent='未自动保存：'+err.message;$('editor-save-status').textContent='本次输入未保存；请修正提示或撤销本次编辑。';return false;}
  }
  function cancelEditor() {clearTimeout(editorTimer);if(editorSaved)undo();closeEditor();}
  const editorForm=$('task-form');
  editorForm.addEventListener('input',e=>{if(e.isComposing || editorComposing)return;clearTimeout(editorTimer);editorTimer=setTimeout(()=>saveEditor(),350);});
  editorForm.addEventListener('change',()=>saveEditor());
  editorForm.addEventListener('focusout',()=>saveEditor());
  editorForm.addEventListener('compositionstart',()=>{editorComposing=true;clearTimeout(editorTimer);});
  editorForm.addEventListener('compositionend',()=>{editorComposing=false;clearTimeout(editorTimer);editorTimer=setTimeout(()=>saveEditor(),350);});
  editorForm.addEventListener('submit',e=>{e.preventDefault();saveEditor(true);});
  $('task-dialog').addEventListener('cancel',e=>{e.preventDefault();cancelEditor();});
  addEventListener('pagehide',()=>saveEditor());
  document.addEventListener('visibilitychange',()=>{if(document.hidden)saveEditor();});
  function ask(title,message,confirmLabel='确认') {
    if(typeof $('confirm-dialog').showModal!=='function') return Promise.resolve(false);
    $('confirm-title').textContent=title;$('confirm-message').textContent=message;$('confirm-yes').textContent=confirmLabel;
    $('confirm-dialog').showModal();$('confirm-no').focus();return new Promise(resolve=>{askResolve=resolve;});
  }
  function answer(yes) {$('confirm-dialog').close();if(askResolve){askResolve(yes);askResolve=null;}}
  async function deleteTask(id) {
    const t=state.tasks.find(v=>v.id===id);if(!t) return;
    const dependent=state.tasks.find(v=>v.depends_on.includes(id));
    if(dependent){notify(`“${dependent.title}”依赖这项任务，请先编辑它的前置条件。`);return;}
    if(await ask('删除这项行动？',t.title+'。删除后可以撤销。','删除')) commit(state.tasks.filter(v=>v.id!==id),'任务已删除。');
  }
  function filename(s) {return String(s).replace(/[\\/:*?"<>|\x00-\x1f]/g,'-').slice(0,120)||'venture-playbook';}
  function download(content,type,name) {
    const blob=new Blob([content],{type}),href=URL.createObjectURL(blob),a=el('a',{href,download:filename(name)});
    document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(href),10000);
  }
  function exportTasks() {download(JSON.stringify(state,null,2),'application/json;charset=utf-8',base.report_id+'-tasks.json');notify('已发起待办备份下载。请保留该文件以便恢复或换设备。');}
  function exportCSV() {
    const keys=['id','title','phase','day','due','owner','status','priority','estimate','action','deliverable','acceptance','on_failure','notes','depends_on'];
    const cell=v=>{let s=Array.isArray(v)?v.join(' | '):String(v||'');if(/^[\s\uFEFF]*[=+\-@]/.test(s)) s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
    const rows=[keys,...state.tasks.map(t=>keys.map(k=>t[k]))];download('\uFEFF'+rows.map(r=>r.map(cell).join(',')).join('\r\n'),'text/csv;charset=utf-8',base.report_id+'-tasks.csv');notify('已导出全部待办，不受当前筛选条件影响。');
  }
  async function importTasks(file) {
    if(!file) return;
    try {
      if(file.size>2097152) throw new Error('备份文件超过2MB，请检查文件是否选对。');
      const value=JSON.parse(await file.text());
      if(value.schema_version!==1 || value.report_id!==base.report_id) throw new Error('这不是本项目的待办备份。未修改任何任务。');
      const tasks=validTasks(value.tasks);
      if(await ask('导入待办备份？','将以备份中的待办替换当前清单。建议先备份当前版本；导入后仍可撤销。','导入')) {commit(tasks,'待办已导入。');if(typeof value.selected_state==='string') {state.selected_state=value.selected_state;showState();persist();}}
    } catch(err) {notify('导入失败：'+err.message);}
    finally {$('import-file').value='';}
  }
  function exportHTML() {
    const doc=document.documentElement.cloneNode(true);
    doc.querySelector('#poster-dialog')?.remove();
    doc.classList.remove('enhanced');
    const next={...base,tasks:clone(state.tasks),selected_state:state.selected_state,revision:base.revision+'-saved-'+Date.now().toString(36)};
    doc.querySelector('#vp-data').textContent=safeJSON(next);
    doc.querySelector('#task-list').replaceChildren(...state.tasks.map(t=>renderTask(t,false)));
    for(const n of doc.querySelectorAll('dialog')) n.removeAttribute('open');
    doc.querySelector('#task-form').removeAttribute('data-new-id');
    doc.querySelector('#form-error').textContent='';
    for(const id of ['local-banner','toast','tasks-empty']) doc.querySelector('#'+id)?.setAttribute('hidden','');
    for(const n of doc.querySelectorAll('input:not([type="checkbox"]):not([type="file"]),textarea')) {n.removeAttribute('value');if(n.tagName==='TEXTAREA')n.textContent='';}
    for(const n of doc.querySelectorAll('.filters option')) n.removeAttribute('selected');
    doc.querySelector('#storage-message').textContent='浏览器本地保存 · 换设备前请保存完整报告';
    doc.querySelector('#storage-bar').classList.remove('warning');
    download('<!doctype html>\n'+doc.outerHTML,'text/html;charset=utf-8',base.report_id+'-saved.html');
    notify('已发起完整HTML下载，包含当前待办修改。下载后请打开新文件确认。');
  }
  function showState() {
    const states=base.states||[],pick=$('state-select');if(!pick) return;
    const s=states.find(v=>v.id===state.selected_state);
    pick.value=s?s.id:'';
    $('state-action').textContent=s?s.action:'先核对下方证据条件，再手动选择当前状态。完成待办不代表已经成交。';
    $('state-evidence').textContent=s?'需要的证据：'+s.evidence:'转移概率没有足够样本时保持未知。';
  }
  $('add-task').addEventListener('click',()=>openEditor());
  $('editor-close').addEventListener('click',()=>saveEditor(true));$('editor-cancel').addEventListener('click',cancelEditor);
  $('confirm-yes').addEventListener('click',()=>answer(true));$('confirm-no').addEventListener('click',()=>answer(false));
  $('confirm-dialog').addEventListener('cancel',e=>{e.preventDefault();answer(false);});
  $('undo').addEventListener('click',undo);$('toast-undo').addEventListener('click',undo);
  $('backup-tasks').addEventListener('click',exportTasks);$('export-csv').addEventListener('click',exportCSV);
  $('import-tasks').addEventListener('click',()=>$('import-file').click());$('import-file').addEventListener('change',e=>importTasks(e.target.files[0]));
  for(const n of document.querySelectorAll('[data-save-html]')) n.addEventListener('click',exportHTML);
  $('search').addEventListener('input',render);for(const id of ['phase-filter','status-filter','sort-filter']) $(id).addEventListener('change',render);
  $('reset-filters').addEventListener('click',()=>{for(const id of ['search','phase-filter','status-filter']) $(id).value='';$('sort-filter').value='original';render();});
  const expanded=[];
  function preparePrint(){$('task-list').replaceChildren(...state.tasks.map(t=>renderTask(t)));expanded.length=0;for(const d of document.querySelectorAll('details')) {expanded.push([d,d.open]);d.open=true;}for(const row of $('task-list').children)row.hidden=false;}
  function finishPrint(){for(const [d,open] of expanded) d.open=open;render();}
  window.addEventListener('beforeprint',preparePrint);window.addEventListener('afterprint',finishPrint);
  $('print-report').addEventListener('click',()=>window.print());
  $('state-select')?.addEventListener('change',e=>{state.selected_state=e.target.value;persist();showState();});
  if('IntersectionObserver' in window) {
    const observer=new IntersectionObserver(entries=>{for(const item of entries)if(item.isIntersecting)for(const n of document.querySelectorAll('.nav-links a'))n.classList.toggle('active',n.getAttribute('href')==='#'+item.target.id);},{rootMargin:'-10% 0px -68% 0px'});
    for(const section of document.querySelectorAll('main>section[id]'))observer.observe(section);
  }
  $('copy-connect')?.addEventListener('click',async()=>{
    const command=$('connect-command');
    let copied=false;
    try{await navigator.clipboard.writeText(command.textContent);copied=true;}catch{
      const range=document.createRange(),selection=getSelection();range.selectNodeContents(command);selection.removeAllRanges();selection.addRange(range);
      try{copied=document.execCommand('copy');}catch{}
      if(copied)selection.removeAllRanges();
    }
    notify(copied?'已复制。客服确认体验已开通后，请回到 AI 对话粘贴并发送。':'客服确认体验已开通后，请复制选中的指令，回到 AI 对话发送。');
  });
  const poster=$('referral-poster'),posterButtons=document.querySelectorAll('.referral-poster-link');
  if(poster && posterButtons.length && typeof HTMLDialogElement!=='undefined') {
    let preview=$('poster-dialog');
    if(!preview) {
      preview=el('dialog',{id:'poster-dialog',class:'poster-dialog','aria-label':'体验卡海报大图'});
      const toggle=el('button',{type:'button',class:'poster-zoom-toggle','aria-label':'再次点击海报，恢复原位'});
      toggle.append(el('img',{alt:poster.alt}),el('span',{},'再次点击海报恢复原位 · Esc 也可关闭'));
      preview.append(toggle);document.body.append(preview);
    }
    let posterView;
    preview.addEventListener('close',()=>{if(posterView)window.scrollTo({...posterView,behavior:'instant'});});
    preview.querySelector('button').addEventListener('click',()=>preview.close());
    preview.addEventListener('click',e=>{if(e.target===preview)preview.close();});
    for(const button of posterButtons)button.addEventListener('click',()=>{posterView={left:scrollX,top:scrollY};preview.querySelector('img').src=button.querySelector('img').src;preview.showModal();});
  }
  document.documentElement.classList.add('enhanced');render();updateStorageLabel();showState();
})();
