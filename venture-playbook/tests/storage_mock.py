#!/usr/bin/env python3
"""Storage integration with an explicitly mocked storage adapter.
This verifies read/write/revision/error branches, not browser file:// persistence.
Requires preinstalled Playwright and a browser; never disables browser security.
"""
import argparse
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

MOCK="""() => {
  window.__vpTestStore = Object.create(null);
  window.__vpTestQuota = false;
  Object.defineProperty(window, 'localStorage', {configurable:true,value:{
    getItem(k){return Object.prototype.hasOwnProperty.call(window.__vpTestStore,k)?window.__vpTestStore[k]:null;},
    setItem(k,v){if(window.__vpTestQuota)throw new DOMException('test quota','QuotaExceededError');window.__vpTestStore[k]=String(v);},
    removeItem(k){delete window.__vpTestStore[k];}
  }});
}"""

def run(args):
    content=args.report.read_text('utf-8');checks=[]
    def ok(name,condition):
        if not condition:raise AssertionError(name)
        checks.append({'check':name,'result':'PASS','evidence':'mock_storage_adapter'})
    with sync_playwright() as p:
        options={'headless':True,'chromium_sandbox':True}
        if args.browser:options['executable_path']=args.browser
        browser=p.chromium.launch(**options);page=browser.new_page()
        page.evaluate(MOCK);page.set_content(content);page.wait_for_selector('html.enhanced')
        ok('可用存储显示正确信息','浏览器本地保存' in page.locator('#storage-message').inner_text())
        page.locator('[data-task-id="T01"] .task-check').click()
        store=page.evaluate('window.__vpTestStore');entry=next(iter(store.values()));backup=json.loads(entry)
        ok('修改写入对应报告版本',backup['tasks'][0]['status']=='done')
        page.set_content(content);page.wait_for_selector('html.enhanced')
        ok('同版重载恢复',page.locator('[data-task-id="T01"] .task-check').is_checked())
        payload=json.loads(page.locator('#vp-data').text_content());new={**payload,'revision':'new-revision'}
        match=re.search(r'<script[^>]+id="vp-data"[^>]*>(.*?)</script>',content,re.S)
        start,end=match.span(1)
        revised=content[:start]+json.dumps(new,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')+content[end:]
        page.set_content(revised);page.wait_for_selector('html.enhanced')
        ok('新修订不被旧进度覆盖',not page.locator('[data-task-id="T01"] .task-check').is_checked())
        ok('新修订没有删除旧缓存',page.evaluate('Object.keys(window.__vpTestStore).length')==1)
        page.evaluate('window.__vpTestQuota=true');page.locator('[data-task-id="T01"] .task-check').click()
        ok('写入异常仍保留本次编辑',page.locator('[data-task-id="T01"] .task-check').is_checked())
        ok('写入异常不宣称持久化成功','仅本次打开有效' in page.locator('#storage-message').inner_text())
        page.evaluate("() => {window.__vpTestQuota=false;for(const k of Object.keys(window.__vpTestStore))window.__vpTestStore[k]='bad-json';}")
        page.set_content(content);page.wait_for_selector('html.enhanced')
        ok('损坏缓存不阻断正文与交互',page.locator('#local-banner').is_visible() and not page.locator('[data-task-id="T01"] .task-check').is_checked())
        browser.close()
    result={'checks':checks,'native_file_storage_verified':False,'mock_adapter_only':True}
    if args.out:args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--report',type=Path,default=Path(__file__).resolve().parents[1]/'examples/demo-report.html');ap.add_argument('--browser',default='');ap.add_argument('--out',type=Path)
    run(ap.parse_args())
