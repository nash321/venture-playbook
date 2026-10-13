"""Offline structural/security regression tests. No business calculations or network calls."""
from __future__ import annotations
import copy
import base64
import importlib.util
import json
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('venture',ROOT/'scripts/venture.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)


def fixture():return v.read_json(ROOT/'examples/project-demo.json')
def task(k='T1',**kw):
    out={'id':k,'title':'核对任务','action':'打开授权资料','deliverable':'记录','acceptance':'可回查','on_failure':'补材料','depends_on':[]}
    out.update(kw);return out


def guide():
    return {'overview':'先做一个能核对的样品，收入仍未知。',
            'terms':[{'term':'订阅','explanation':'定期付费；不等于无限产能。','section_id':'subscription'}],
            'first_action':{'task_id':'T01','example':'虚构商品任务卡；不联系真实客户。'},
            'self_check':[{'question':'有初稿是否代表成交？','answer':'不是；仍需真实付款和交付证据。','section_id':'delivery'}]}


class InputTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_demo_valid(self):self.assertEqual(v.validate_data(fixture())['research_status'],'demo')
    def test_scaffold_valid(self):self.assertEqual(v.validate_data(v.scaffold('项目'))['research_status'],'draft')
    def test_duplicate_json_key(self):
        p=self.root/'x.json';p.write_text('{"a":1,"a":2}')
        with self.assertRaises(v.InputError):v.read_json(p)
    def test_invalid_json(self):
        p=self.root/'x.json';p.write_text('{oops')
        with self.assertRaises(v.InputError):v.read_json(p)
    def test_utf8_bom(self):
        p=self.root/'x.json';p.write_text('\ufeff{"title":"中文"}',encoding='utf-8')
        self.assertEqual(v.read_json(p)['title'],'中文')
    def test_wrong_schema(self):
        d=fixture();d['schema_version']=99
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_missing_verdict(self):
        d=fixture();d['verdict']['next_step']=''
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_bad_business_type(self):
        d=fixture();d['business']=[]
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_bad_synthesis_type(self):
        d=fixture();d['synthesis']['shared']='not array'
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_bad_section(self):
        d=fixture();d['source_sections'][0]['paragraphs']=[]
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_missing_source(self):
        d=fixture();d['cases'][0]['source_ids']=['NO_SUCH_SOURCE']
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_unread_source_not_verified(self):
        d=fixture();d['cases'][0]['source_ids']=[]
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_duplicate_source(self):
        d=fixture();d['sources'].append(copy.deepcopy(d['sources'][0]))
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_unsafe_url(self):
        for url in ['javascript:alert(1)','data:text/html,x','https://a:b@example.com/a','https://example.com/ bad','file:///tmp/a']:
            with self.subTest(url=url),self.assertRaises(v.InputError):v.safe_url(url)
    def test_canonical_tracking_only(self):
        self.assertEqual(v.canonical_url('https://example.com/p?id=42&utm_source=x#hello'),'https://example.com/p?id=42')
    def test_dedupe_preserves_meaning(self):
        out=v.dedupe([{'url':'https://example.com/p?id=1&utm_source=a'},{'url':'https://example.com/p?id=1&utm_source=b'},{'url':'https://example.com/p?id=2'}])
        self.assertEqual(len(out['sources']),2);self.assertFalse(out['independence_checked'])
    def test_queries_do_not_claim_search(self):self.assertIn('没有发起搜索',v.queries(fixture()))
    def test_complete_missing_peers(self):
        d=fixture();d['research_status']='complete';d['cases']=[]
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_complete_same_entity(self):
        d=fixture();d['research_status']='complete'
        for c in d['cases']:c['entity_id']='same'
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_complete_missing_source_sections(self):
        d=fixture();d['research_status']='complete';d['expected_source_sections'].append('missing')
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_complete_partial_source(self):
        d=fixture();d['research_status']='complete';d['source_sections'][0]['read_status']='partial'
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_no_fake_probability(self):
        d=fixture();d['states'][0]['probability']='90%'
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_selected_state_must_exist(self):
        d=fixture();d['selected_state']='missing'
        with self.assertRaises(v.InputError):v.validate_data(d)
    def test_source_outline_preserves(self):
        p=self.root/'source.md';p.write_text('# 起因\n一个具体细节。\n## 返工\n失败后改过步骤。',encoding='utf-8')
        result=v.outline(p)
        self.assertEqual(result['sections'][1]['original_text'],'失败后改过步骤。');self.assertTrue(result['extraction_only'])
    def test_html_outline_preserves_links(self):
        p=self.root/'source.html';p.write_text('<h1>原文</h1><p>正文</p><a href="https://example.com/full">全文</a><script>attack</script>',encoding='utf-8')
        result=v.outline(p)
        self.assertEqual(result['links_to_review'],['https://example.com/full']);self.assertNotIn('attack',str(result['sections']))
    def test_outline_reject_binary(self):
        p=self.root/'source.pdf';p.write_bytes(b'%PDF')
        with self.assertRaises(v.InputError):v.outline(p)
    def test_refuse_overwrite(self):
        p=self.root/'out.html';v.atomic_write(p,'first')
        with self.assertRaises(v.InputError):v.atomic_write(p,'second')
        self.assertEqual(p.read_text(),'first')
    def test_atomic_force(self):
        p=self.root/'out.html';v.atomic_write(p,'first');v.atomic_write(p,'second',True)
        self.assertEqual(p.read_text(),'second');self.assertEqual(list(self.root.glob('.venture-*')),[])
    def test_merge_wrong_project(self):
        a=self.root/'project.json';b=self.root/'backup.json';a.write_text(json.dumps(fixture()));b.write_text(json.dumps({'report_id':'wrong','schema_version':1,'tasks':[]}))
        self.assertEqual(v.main(['merge-tasks',str(a),'--tasks',str(b),'--out',str(self.root/'out.json')]),2)
        self.assertFalse((self.root/'out.json').exists())
    def test_merge_deleted_example_task_keeps_customer_plan_and_explanation(self):
        original=fixture();a=self.root/'project.json';b=self.root/'backup.json';out=self.root/'updated.json'
        a.write_text(json.dumps(original));b.write_text(json.dumps({'schema_version':1,'report_id':original['report_id'],'tasks':[]}))
        self.assertEqual(v.main(['merge-tasks',str(a),'--tasks',str(b),'--out',str(out)]),0)
        updated=v.read_json(out);self.assertEqual(updated['tasks'],[])
        self.assertEqual(updated['source_sections'],original['source_sections'])
        self.assertEqual(updated['reading_guide']['first_action']['example'],original['reading_guide']['first_action']['example'])
        self.assertTrue(updated['reading_guide']['first_action']['removed_from_plan'])
        self.assertIn('已从当前计划删除',v.render(updated))
    def test_merge_saved_html_keeps_edits_state_and_research(self):
        original=fixture();saved=copy.deepcopy(original)
        saved['tasks'][0]['notes']='用户保存的修改';saved['selected_state']=saved['states'][0]['id']
        a=self.root/'project.json';b=self.root/'saved.html';out=self.root/'updated.json'
        a.write_text(json.dumps(original));b.write_text(v.render(saved))
        self.assertEqual(v.main(['merge-tasks',str(a),'--tasks',str(b),'--out',str(out)]),0)
        merged=v.read_json(out)
        self.assertEqual(merged['tasks'][0]['notes'],'用户保存的修改')
        self.assertEqual(merged['selected_state'],saved['selected_state'])
        self.assertEqual(merged['source_sections'],original['source_sections'])
        self.assertEqual(a.read_text(),json.dumps(original))
    def test_saved_task_order_recovers_without_changing_dependencies(self):
        original=fixture();saved=copy.deepcopy(original)
        saved['tasks'][0],saved['tasks'][1]=saved['tasks'][1],saved['tasks'][0]
        a=self.root/'project.json';b=self.root/'saved.html';out=self.root/'updated.json'
        a.write_text(json.dumps(original));b.write_text(v.render(saved))
        self.assertEqual(v.main(['merge-tasks',str(a),'--tasks',str(b),'--out',str(out)]),0)
        merged=v.read_json(out)
        self.assertEqual(merged['tasks'],saved['tasks'])
        self.assertEqual({t['id']:t['depends_on'] for t in merged['tasks']},{t['id']:t['depends_on'] for t in original['tasks']})
        self.assertEqual(merged['source_sections'],original['source_sections'])
    def test_merge_html_wrong_project_does_not_write(self):
        a=self.root/'project.json';b=self.root/'saved.html';out=self.root/'updated.json'
        a.write_text(json.dumps(fixture()));other=fixture();other['report_id']='other-project';b.write_text(v.render(other))
        self.assertEqual(v.main(['merge-tasks',str(a),'--tasks',str(b),'--out',str(out)]),2)
        self.assertFalse(out.exists())
    def test_merge_html_missing_or_duplicate_payload_rejected(self):
        a=self.root/'project.json';b=self.root/'saved.html';out=self.root/'updated.json';a.write_text(json.dumps(fixture()))
        for text in ['<html><body>普通文章</body></html>',v.render(fixture()).replace('</body>','<script id="vp-data" type="application/json">{}</script></body>')]:
            b.write_text(text)
            self.assertEqual(v.main(['merge-tasks',str(a),'--tasks',str(b),'--out',str(out)]),2)
            self.assertFalse(out.exists())
    def test_merge_never_overwrites_saved_html(self):
        a=self.root/'project.json';b=self.root/'saved.html';a.write_text(json.dumps(fixture()));b.write_text(v.render(fixture()));before=b.read_bytes()
        self.assertEqual(v.main(['merge-tasks',str(a),'--tasks',str(b),'--out',str(b),'--force']),2)
        self.assertEqual(b.read_bytes(),before)
    def test_doctor_missing_poster_fails_with_specific_gap(self):
        for name in ['report.css','tasks.js','brand.json']:
            p=self.root/'assets'/name;p.parent.mkdir(exist_ok=True);p.write_text('fixture')
        output=io.StringIO()
        with patch.object(v,'ROOT',self.root),redirect_stdout(output):code=v.main(['doctor'])
        self.assertEqual(code,2)
        receipt=json.loads(output.getvalue());self.assertFalse(receipt['assets_present'])
        self.assertEqual(receipt['missing_assets'],['会员体验卡海报.jpg'])


class TasksTests(unittest.TestCase):
    def test_normalize_defaults(self):self.assertEqual(v.validate_tasks([task()])[0]['status'],'todo')
    def test_duplicate_id(self):
        with self.assertRaises(v.InputError):v.validate_tasks([task(),task()])
    def test_bad_id(self):
        with self.assertRaises(v.InputError):v.validate_tasks([task('../x')])
    def test_invalid_date(self):
        with self.assertRaises(v.InputError):v.validate_tasks([task(due='2026-02-31')])
    def test_missing_dep(self):
        with self.assertRaises(v.InputError):v.validate_tasks([task(depends_on=['NO'])])
    def test_duplicate_dep(self):
        with self.assertRaises(v.InputError):v.validate_tasks([task(),task('T2',depends_on=['T1','T1'])])
    def test_cycle(self):
        with self.assertRaises(v.InputError):v.validate_tasks([task(depends_on=['T2']),task('T2',depends_on=['T1'])])
    def test_self_dep(self):
        with self.assertRaises(v.InputError):v.validate_tasks([task(depends_on=['T1'])])
    def test_done_unfinished_dep(self):
        with self.assertRaises(v.InputError):v.validate_tasks([task(),task('T2',status='done',depends_on=['T1'])])
    def test_long_chain_no_recursion(self):
        raw=[task('T'+str(i),depends_on=['T'+str(i-1)] if i else []) for i in range(1000)]
        self.assertEqual(len(v.validate_tasks(raw)),1000)
    def test_limit(self):
        with self.assertRaises(v.InputError):v.validate_tasks([task(str(i)) for i in range(1001)])
    def test_invalid_type(self):
        with self.assertRaises(v.InputError):v.validate_tasks([task(notes={'a':'b'})])
    def test_safe_csv(self):
        text=v.export_tasks({'tasks':[task(title='=WEBSERVICE("x")',notes='@formula')]})
        self.assertIn("'=WEBSERVICE",text);self.assertIn("'@formula",text);self.assertTrue(text.startswith('\ufeff'))
    def test_edit_text_not_html(self):self.assertEqual(v.validate_tasks([task(title='<img onerror=evil>')])[0]['title'],'<img onerror=evil>')


class ReportTests(unittest.TestCase):
    def test_workflow_graph_keeps_order_conditions_and_text_alternative(self):
        steps=[{'title':'找真实需求','detail':'没有原始材料就先暂停。'},
               {'title':'做可核对的试样','detail':'试样通过仍不代表已成交。'}]
        rendered=v.workflow_graph(steps)
        for fragment in re.findall(r'<svg\b.*?</svg>',rendered,re.S):
            graph=ET.fromstring(fragment)
            self.assertEqual(graph.attrib['role'],'img')
            ns={'svg':'http://www.w3.org/2000/svg'}
            self.assertEqual([n.attrib['data-step'] for n in graph.findall('svg:g',ns)],['1','2'])
            self.assertEqual(len(graph.findall('svg:path',ns)),1)
            self.assertTrue(graph.find('svg:desc',ns).text)
        self.assertEqual(len(re.findall(r'<svg\b',rendered)),2)
        for step in steps:self.assertIn(step['detail'],rendered)

    def test_workflow_graph_escapes_input_and_handles_single_step(self):
        rendered=v.workflow_graph([{'title':'<script>坏输入</script>','detail':'保留条件'}])
        self.assertNotIn('<script>',rendered)
        for fragment in re.findall(r'<svg\b.*?</svg>',rendered,re.S):
            graph=ET.fromstring(fragment)
            self.assertEqual(len(graph.findall('{http://www.w3.org/2000/svg}path')),0)
            self.assertIn('<script>坏输入</script>',''.join(graph.itertext()))
        self.assertEqual(v.workflow_graph([]),'')
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'report.html'
    def tearDown(self):self.temp.cleanup()
    def render(self,data=None):self.path.write_text(v.render(data or fixture()),encoding='utf-8');return self.path.read_text()
    def test_structure_pass(self):self.render();self.assertTrue(v.check_html(self.path)['passed'])
    def test_not_semantic_certification(self):
        self.render();r=v.check_html(self.path);self.assertFalse(r['semantic_research_verified']);self.assertFalse(r['browser_verified'])
    def test_all_sections(self):
        text=self.render()
        for k in ['overview','source','cases','business','actions','states','sources']:self.assertIn('id="'+k+'"',text)
    def test_source_text_retained(self):
        d=fixture();text=self.render(d)
        for s in d['source_sections']:
            for para in s['paragraphs']:self.assertIn(v.esc(para),text)
    def test_reading_guide_preserves_research_and_task_payload(self):
        d=fixture();d.pop('reading_guide',None);d['revision']='customer-existing-revision'
        before=self.render(copy.deepcopy(d));original=copy.deepcopy(d)
        d['reading_guide']=guide();after=self.render(d)
        for section in d['source_sections']:
            for para in section['paragraphs']:self.assertIn(v.esc(para),after)
        payload=lambda text:json.loads(re.search(r'<script id="vp-data" type="application/json">(.*?)</script>',text,re.S).group(1))
        self.assertEqual(payload(before),payload(after))
        self.assertEqual(d['source_sections'],original['source_sections'])
        self.assertTrue(v.check_html(self.path)['passed'])
    def test_reading_guide_rejects_invalid_references_and_shapes(self):
        variants=[None,{'overview':'缺少示例'}]
        for key,value in [('terms',[{'term':'词','explanation':'说明','section_id':'missing'}]),
                          ('terms',[{'term':'词','explanation':'说明','section_id':{'id':'delivery'}}]),
                          ('first_action',{'task_id':'missing','example':'说明'}),
                          ('first_action',{'task_id':[],'example':'说明'}),
                          ('first_action',{'task_id':'T01','example':'说明','removed_from_plan':'true'}),
                          ('first_action',{'task_id':'T01','example':'说明','removed_from_plan':True}),
                          ('self_check',[{'question':'问题','answer':'答案','section_id':'missing'}]),
                          ('self_check',[])]:
            invalid=guide();invalid[key]=value;variants.append(invalid)
        duplicate=guide();duplicate['terms']*=2;variants.append(duplicate)
        for invalid in variants:
            with self.subTest(guide=invalid):
                d=fixture();d['reading_guide']=invalid
                with self.assertRaises(v.InputError):v.validate_data(d)
    def test_reading_guide_escapes_untrusted_text(self):
        d=fixture();d['reading_guide']=guide()
        attack='<img src=x onerror="alert(1)">'
        d['reading_guide']['overview']=attack
        d['reading_guide']['terms'][0]['explanation']=attack
        d['reading_guide']['first_action']['example']=attack
        d['reading_guide']['self_check'][0]['answer']=attack
        text=self.render(d);self.assertEqual(text.count(v.esc(attack)),4)
        self.assertNotIn(attack,text);self.assertTrue(v.check_html(self.path)['passed'])
    def test_reading_guide_works_without_original_article(self):
        d=fixture();d['source_mode']='idea';d['source_sections']=[];d['reading_guide']=guide()
        d['reading_guide']['terms'][0].pop('section_id')
        d['reading_guide']['self_check'][0].pop('section_id')
        text=self.render(d);self.assertIn('定期付费；不等于无限产能。',text)
        self.assertTrue(v.check_html(self.path)['passed'])
    def test_plain_input_escaped(self):
        d=fixture();d['source_sections'][0]['paragraphs'].append('<script>alert(1)</script>')
        text=self.render(d);self.assertIn('&lt;script&gt;',text);self.assertTrue(v.check_html(self.path)['passed'])
    def test_payload_script_breakout_escaped(self):
        d=fixture();d['tasks'][0]['notes']='</script><script>alert(1)</script>'
        text=self.render(d);self.assertIn('\\u003c/script\\u003e',text);self.assertTrue(v.check_html(self.path)['passed'])
    def test_runtime_tamper_detected(self):
        text=self.render();self.path.write_text(text.replace("'use strict';","'use strict';alert(1);"))
        self.assertFalse(v.check_html(self.path)['passed'])
    def test_style_tamper_detected(self):
        text=self.render();self.path.write_text(text.replace('<style id="vp-style">','<style id="vp-style">body{color:red}'))
        self.assertFalse(v.check_html(self.path)['passed'])
    def test_inline_events_rejected(self):
        text=self.render();self.path.write_text(text.replace('<body>','<body onload="alert(1)">'))
        self.assertFalse(v.check_html(self.path)['passed'])
    def test_foreign_script_rejected(self):
        text=self.render();self.path.write_text(text.replace('</body>','<script src="https://example.com/x.js"></script></body>'))
        self.assertFalse(v.check_html(self.path)['passed'])
    def test_external_resource_rejected(self):
        text=self.render();self.path.write_text(text.replace('</body>','<img src="https://example.com/x.png"></body>'))
        self.assertFalse(v.check_html(self.path)['passed'])
    def test_original_referral_poster_embedded_at_start(self):
        text=self.render();card=re.search(r'</header>(<section id="referral"[^>]*>.*?)</section><section id="overview">',text,re.S)
        self.assertIsNotNone(card,'每份报告须在标题后、决策速览前保留分享卡片')
        src=re.search(r'<img[^>]*src="([^"]+)"',card.group(1)).group(1)
        self.assertTrue(src.startswith('data:image/jpeg;base64,'))
        self.assertEqual(base64.b64decode(src.split(',',1)[1]),(ROOT/'会员体验卡海报.jpg').read_bytes())
        self.assertIn('id="referral-link"',card.group(1))
        self.assertNotIn('work.weixin.qq.com',card.group(1))
        self.assertIn('3天体验',card.group(1))
        self.assertLess(text.index('<h1>'),text.index('id="referral"'))
        self.assertLess(text.index('id="referral"'),text.index('id="overview"'))
    def test_referral_copy_matches_business_value_without_disclaimer(self):
        card=v.referral_card().split('</div><button id="referral-link"',1)[0]
        self.assertIn('精华帖、风向标',card)
        self.assertIn('整理下一步怎么做',card)
        self.assertNotIn('id="referral-cta"',card)
        self.assertNotRegex(card,r'推荐奖励|阅读权益|实际体验.*账号|注册后可连接生财资料')
    def test_referral_explains_customer_activation_before_connection(self):
        card=re.sub(r'src="data:[^"]+"','src="embedded"',v.referral_card())
        self.assertIn('客服确认已开通',card)
        self.assertIn('开通3天体验卡',card)
        self.assertIn('体验已开通，连接生财有术',card)
        self.assertIn('连接生财有术',card)
        self.assertIn('id="copy-connect"',card)
        self.assertIn('登录并确认授权',card)
        self.assertIn('AI 检查连接成功',card)
    def test_scys_connection_is_optional_enhancement(self):
        card=re.sub(r'src="data:[^"]+"','src="embedded"',v.referral_card())
        self.assertIn('直接用',card)
        self.assertIn('项目想法',card)
        self.assertIn('生成报告和行动清单',card)
        self.assertIn('加入后更强',card)
        self.assertIn('可选增强',card)
    def test_missing_referral_card_rejected(self):
        text=self.render();self.path.write_text(re.sub(r'<section id="referral".*?</section>','',text,flags=re.S))
        self.assertFalse(v.check_html(self.path)['passed'])
    def test_substituted_referral_image_rejected(self):
        text=self.render();self.path.write_text(re.sub(r'(id="referral-poster"[^>]*src=")[^"]+',r'\g<1>data:image/jpeg;base64,/9j/2Q==',text))
        self.assertFalse(v.check_html(self.path)['passed'])
    def test_external_referral_button_rejected(self):
        text=self.render();self.path.write_text(text.replace('<button id="referral-link"','<button href="https://example.com/other-referral" id="referral-link"'))
        self.assertFalse(v.check_html(self.path)['passed'])
    def test_card_moved_above_report_rejected(self):
        text=self.render();card=re.search(r'<section id="referral".*?</section>',text,re.S).group()
        self.path.write_text(text.replace(card,'').replace('<main>','<main>'+card))
        self.assertFalse(v.check_html(self.path)['passed'])
    def test_card_moved_to_bottom_rejected(self):
        text=self.render();card=re.search(r'<section id="referral".*?</section>',text,re.S).group()
        self.path.write_text(text.replace(card,'').replace('</main>',card+'</main>'))
        self.assertFalse(v.check_html(self.path)['passed'])
    def test_content_before_card_rejected(self):
        text=self.render();self.path.write_text(text.replace('<section id="referral"','<section id="before-card">提前插入正文</section><section id="referral"'))
        self.assertFalse(v.check_html(self.path)['passed'])
    def test_broken_anchor_rejected(self):
        text=self.render();self.path.write_text(text.replace('href="#overview"','href="#not-there"',1))
        self.assertFalse(v.check_html(self.path)['passed'])
    def test_empty_check_rejected(self):self.path.write_text('');self.assertFalse(v.check_html(self.path)['passed'])
    def test_no_runtime_network(self):
        js=(ROOT/'assets/tasks.js').read_text()
        for token in ['fetch(', 'XMLHttpRequest','WebSocket(','eval(','new Function(']:self.assertNotIn(token,js)
    def test_brand_used(self):
        text=self.render();brand=v.read_json(ROOT/'assets/brand.json');self.assertIn(brand['name'],text);self.assertIn(brand['tagline'],text)


if __name__=='__main__':unittest.main(verbosity=2)
