#!/usr/bin/env python3
"""Real-browser optional QA. Requires already installed Playwright + browser.
Default opens a local HTML. --markup tests trusted generated markup without navigation;
it does not verify native file:// storage. No browser security flags are disabled.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import tempfile
from playwright.sync_api import sync_playwright


def run(args):
    source=args.report.resolve();content=source.read_text('utf-8')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    results=[];errors=[];requests=[]
    def passed(name,condition=True):
        if not condition:raise AssertionError(name)
        results.append({'check':name,'result':'PASS'})
    with sync_playwright() as p:
        launch={'headless':True,'chromium_sandbox':True}
        if args.browser:launch['executable_path']=args.browser
        browser=p.chromium.launch(**launch)
        ctx=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
        page.on('request',lambda r:requests.append(r.url))
        if args.markup:page.set_content(content,wait_until='load')
        else:page.goto(source.as_uri(),wait_until='load')
        page.wait_for_selector('html.enhanced')
        rows=page.locator('#task-list .task-row')
        count=rows.count()
        passed('真实DOM加载并增强',count>0 and page.locator('h1').inner_text()!='')
        passed('桌面没有页面级横向溢出',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        passed('没有外部网络请求',not requests)
        if args.markup:passed('存储受限时明确提示而不假保存','仅本次打开有效' in page.locator('#storage-message').inner_text())
        page.screenshot(path=str(out/'desktop-cover.png'))
        original_source=page.locator('#source').inner_text()
        # The shipped demo deliberately provides dependencies T02 -> T01.
        t1=page.locator('[data-task-id="T01"]');t2=page.locator('[data-task-id="T02"]')
        t2.locator('input.task-check').click()
        passed('前置未完成时阻止勾选',not t2.locator('input.task-check').is_checked())
        t1.locator('input.task-check').click();t2.locator('input.task-check').click()
        passed('完成前置后可正常勾选',t2.locator('input.task-check').is_checked())
        t1.locator('input.task-check').click()
        passed('有已完成后续项时不能伪撤销前置',t1.locator('input.task-check').is_checked())
        page.locator('#add-task').click();form=page.locator('#task-form')
        vals={'title':'我的独立测试行动','phase':'自定义试验','day':'D4 下午','due':'2026-10-20','owner':'测试者','estimate':'建议30分钟','cost':'费用待核','action':'打开合成资料并记录问题','inputs':'合成资料','tool':'普通浏览器','deliverable':'一份问题清单','acceptance':'每个问题可回查到输入','on_failure':'缺资料则停止补齐','notes':'测试备注'}
        for k,value in vals.items():form.locator('[name="'+k+'"]').fill(value)
        form.locator('[name="priority"]').select_option('high')
        new_id=form.get_attribute('data-new-id')
        form.locator('button[type="submit"]').click()
        passed('新增任务和全部字段保存',rows.count()==count+1)
        new=page.locator('[data-task-id="'+new_id+'"]')
        new.locator('button[aria-label^="编辑"]').click()
        form.locator('[name="title"]').fill('已编辑的独立行动')
        form.locator('[name="notes"]').fill('</script><img src=x onerror="window.untrustedExecuted=true">')
        form.locator('button[type="submit"]').click()
        passed('编辑不执行输入HTML',new.locator('h4').inner_text()=='已编辑的独立行动' and page.evaluate('window.untrustedExecuted!==true'))
        passed('用户改行动不会改研究原文',page.locator('#source').inner_text()==original_source)
        page.locator('#search').fill('独立行动');passed('关键词查询',rows.count()==1)
        page.locator('#search').fill('不会找到的随机词');passed('空结果反馈',page.locator('#tasks-empty').is_visible())
        page.locator('#reset-filters').click();page.locator('#status-filter').select_option('done')
        passed('状态筛选',all('is-done' in r.get_attribute('class') for r in rows.all()) and rows.count()>0)
        page.locator('#reset-filters').click();page.locator('#phase-filter').select_option('自定义试验');passed('阶段筛选',rows.count()==1)
        page.locator('#reset-filters').click();page.locator('#sort-filter').select_option('due')
        passed('按真实截止日期排序',rows.first.get_attribute('data-task-id')==new_id)
        page.locator('#sort-filter').select_option('original')
        t1.locator('button[aria-label^="删除"]').click()
        passed('被依赖任务不能直接删除',not page.locator('#confirm-dialog').is_visible() and t1.count()==1)
        new.locator('button[aria-label^="删除"]').click();page.locator('#confirm-no').click()
        passed('删除取消保留原任务',new.count()==1)
        new.locator('button[aria-label^="删除"]').click();page.locator('#confirm-yes').click()
        passed('确认删除',rows.count()==count)
        page.locator('#undo').click();passed('删除可撤销',page.locator('[data-task-id="'+new_id+'"]').count()==1)
        page.locator('#add-task').click()
        for k in ['title','action','deliverable','acceptance','on_failure']:form.locator('[name="'+k+'"]').fill('校验测试')
        form.locator('[name="depends_on"]').fill('missing-id')
        form.locator('button[type="submit"]').click()
        passed('无效依赖阻止保存','不存在' in page.locator('#form-error').inner_text())
        page.locator('#editor-cancel').click()
        page.locator('#state-select').select_option('S1')
        passed('状态选择会显示对应下一步',page.locator('#state-action').inner_text()!='')
        with page.expect_download() as dl:page.locator('#backup-tasks').click()
        backup_path=out/'backup.json';dl.value.save_as(backup_path)
        backup=json.loads(backup_path.read_text('utf-8'))
        passed('真实JSON下载保留当前任务与状态',backup['selected_state']=='S1' and any(t['id']==new_id for t in backup['tasks']))
        with page.expect_download() as dl:page.locator('#export-csv').click()
        csv_path=out/'tasks.csv';dl.value.save_as(csv_path)
        passed('真实CSV下载含已编辑内容','已编辑的独立行动' in csv_path.read_text('utf-8-sig'))
        with page.expect_download() as dl:page.locator('[data-save-html]').first.click()
        html_path=out/'saved-report.html';dl.value.save_as(html_path)
        saved=html_path.read_text('utf-8')
        passed('真实完整HTML下载保留正文和数据','已编辑的独立行动' in saved and '<!doctype html>' in saved.lower())
        # Re-open the downloaded bytes in another real browser document.
        restored=ctx.new_page();restored.set_content(saved,wait_until='load');restored.wait_for_selector('html.enhanced')
        passed('导出的完整HTML可重新执行交互',restored.locator('#task-list .task-row').count()==count+1)
        passed('导出的勾选与备注真正保留',restored.locator('[data-task-id="T01"] input.task-check').is_checked() and restored.locator('[data-task-id="'+new_id+'"] .task-details').text_content().find('onerror')>=0)
        restored.close()
        # Wrong-project and malformed imports cannot replace existing work.
        before=rows.count();wrong={**backup,'report_id':'another-project'}
        page.locator('#import-file').set_input_files({'name':'wrong.json','mimeType':'application/json','buffer':json.dumps(wrong).encode()})
        passed('其他项目备份被拒绝',rows.count()==before and not page.locator('#confirm-dialog').is_visible())
        page.locator('#import-file').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':b'not json'})
        page.wait_for_function("document.getElementById('toast-text').textContent.includes('导入失败')")
        passed('损坏备份不破坏当前清单',rows.count()==before)
        new.locator('button[aria-label^="删除"]').click();page.locator('#confirm-yes').click()
        page.locator('#import-file').set_input_files(str(backup_path));page.locator('#confirm-yes').click()
        passed('JSON备份恢复增删改与状态',rows.count()==count+1 and page.locator('#state-select').input_value()=='S1')
        page.locator('#search').fill('独立行动')
        page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
        passed('打印包含所有任务而非仅筛选结果',rows.count()==count+1)
        page.evaluate("window.dispatchEvent(new Event('afterprint'))")
        passed('打印后回到原筛选',rows.count()==1)
        page.locator('#reset-filters').click()
        page.locator('#actions').evaluate("el=>el.scrollIntoView({block:'start',behavior:'instant'})")
        page.screenshot(path=str(out/'desktop-actions.png'))
        page.locator('#add-task').click();page.screenshot(path=str(out/'desktop-editor.png'));page.locator('#editor-cancel').click()
        page.locator('#cases').evaluate("el=>el.scrollIntoView({block:'start',behavior:'instant'})")
        page.screenshot(path=str(out/'desktop-comparison.png'))
        # Mobile real layout and editing, no browser spoofing or security changes.
        mobile=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True)
        mp=mobile.new_page();mp.on('pageerror',lambda e:errors.append(str(e)));mp.set_content(content,wait_until='load');mp.wait_for_selector('html.enhanced')
        passed('手机没有页面级横向溢出',mp.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        mp.screenshot(path=str(out/'mobile-cover.png'))
        mp.locator('#actions').evaluate("el=>el.scrollIntoView({block:'start',behavior:'instant'})")
        mp.screenshot(path=str(out/'mobile-actions.png'))
        mp.locator('#add-task').click();mp.locator('#task-form [name="title"]').fill('手机编辑可用')
        passed('手机编辑弹窗可见且接受输入',mp.locator('#task-dialog').is_visible() and mp.locator('#task-form [name="title"]').input_value()=='手机编辑可用')
        mp.screenshot(path=str(out/'mobile-editor.png'));mp.locator('#editor-cancel').click()
        # No JavaScript: full research and static tasks remain readable.
        static_ctx=browser.new_context(java_script_enabled=False)
        sp=static_ctx.new_page();sp.set_content(saved,wait_until='load')
        passed('禁用脚本仍能读正文与全部已修改待办',sp.locator('#source').inner_text()==original_source and sp.locator('#task-list .task-row').count()==count+1)
        passed('禁用脚本保留勾选记录',sp.locator('[data-task-id="T01"] input.task-check').is_checked())
        passed('没有相关浏览器错误',not errors)
        passed('没有运行期外部请求',not requests)
        browser.close()
    result={'engine':'sandboxed Chromium','loading_mode':'trusted markup via set_content' if args.markup else 'file URL','viewports':['1440x1000','390x844'],'checks':results,'errors':errors,'native_file_storage_tested':not args.markup,'cross_harness_installation_tested':False}
    (out/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='可选浏览器回归，不自动安装Playwright或浏览器。')
    parser.add_argument('--report',type=Path,default=Path(__file__).resolve().parents[1]/'examples/demo-report.html')
    parser.add_argument('--out',type=Path,default=Path(tempfile.gettempdir())/'venture-playbook-qa')
    parser.add_argument('--browser',default='')
    parser.add_argument('--markup',action='store_true',help='只验证自有HTML真实渲染，不验证file://原生存储')
    run(parser.parse_args())
