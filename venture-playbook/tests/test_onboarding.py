import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('setup_venture', ROOT/'scripts/setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
spec = importlib.util.spec_from_file_location('onboarding', ROOT/'scripts/onboarding.py')
guide = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guide)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT.parent/'temp')
        self.home = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_each_host_global_config_without_login(self):
        for host in setup.HOSTS:
            with self.subTest(host=host):
                result = setup.ensure(host, self.home, install_skill=True)
                self.assertTrue(Path(result['skill_path']).joinpath('SKILL.md').is_file())
                self.assertTrue(Path(result['config_path']).is_file())
                self.assertEqual(result['authentication'], 'not_attempted')
                self.assertTrue(setup.ensure(host,self.home)['configured'])
    def test_preserves_other_servers_and_target_credentials(self):
        path=self.home/'.cursor/mcp.json';path.parent.mkdir(parents=True)
        original={'theme':'custom','mcpServers':{'other':{'command':'keep'},'scys-mcp':{'url':setup.ENDPOINT,'headers':{'Authorization':'test-only-secret'}}}}
        path.write_text(json.dumps(original))
        before=path.read_bytes()
        setup.ensure('cursor',self.home)
        self.assertEqual(path.read_bytes(),before)
    def test_existing_endpoint_with_different_name_reused(self):
        path=self.home/'.gemini/settings.json';path.parent.mkdir(parents=True)
        path.write_text(json.dumps({'mcpServers':{'my-scys':{'httpUrl':setup.ENDPOINT}}}))
        result=setup.ensure('gemini',self.home)
        self.assertEqual(result['server_name'],'my-scys')
        self.assertEqual(len(json.loads(path.read_text())['mcpServers']),1)
    def test_conflicting_name_unchanged(self):
        path=self.home/'.cursor/mcp.json';path.parent.mkdir(parents=True)
        path.write_text('{"mcpServers":{"scys-mcp":{"url":"https://example.invalid/mcp"}}}')
        before=path.read_bytes()
        with self.assertRaises(ValueError): setup.ensure('cursor',self.home)
        self.assertEqual(path.read_bytes(),before)
    def test_bad_json_unchanged(self):
        path=self.home/'.claude.json';path.write_text('{broken')
        with self.assertRaises(ValueError): setup.ensure('claude',self.home)
        self.assertEqual(path.read_text(),'{broken')
    def test_codex_keeps_comments_and_unrelated_config(self):
        path=self.home/'.codex/config.toml';path.parent.mkdir(parents=True)
        original='# retain this comment\nmodel = "existing"\n[mcp_servers.other]\ncommand = "keep"\n'
        path.write_text(original)
        setup.ensure('codex',self.home)
        self.assertTrue(path.read_text().startswith(original))
        before=path.read_bytes();setup.ensure('codex',self.home)
        self.assertEqual(path.read_bytes(),before)
    def test_write_failure_does_not_damage_config(self):
        path=self.home/'.cursor/mcp.json';path.parent.mkdir(parents=True);path.write_text('{"mcpServers":{}}')
        before=path.read_bytes()
        with patch.object(setup.os,'replace',side_effect=OSError('test failure')):
            with self.assertRaises(OSError):setup.ensure('cursor',self.home)
        self.assertEqual(path.read_bytes(),before)
    def test_detect_ambiguous_needs_one_choice(self):
        (self.home/'.cursor').mkdir();(self.home/'.gemini').mkdir()
        with patch.dict(setup.os.environ,{},clear=True), self.assertRaises(ValueError):setup.detect(self.home)
    def test_target_symlink_rejected(self):
        outside=self.home/'original.json';outside.write_text('{}')
        (self.home/'.cursor').mkdir();(self.home/'.cursor/mcp.json').symlink_to(outside)
        with self.assertRaises(ValueError):setup.ensure('cursor',self.home)
        self.assertEqual(outside.read_text(),'{}')
    def test_late_install_failure_rolls_back_config_and_skill(self):
        path=self.home/'.cursor/mcp.json';path.parent.mkdir(parents=True);path.write_text('{"mcpServers":{}}')
        skill=self.home/'.cursor/skills/venture-playbook';skill.mkdir(parents=True)
        (skill/'README.md').write_text('previous version')
        before=path.read_bytes();write=setup.atomic_write
        def fail_once(target,*args):
            if Path(target)==skill/'scripts/onboarding.py':raise OSError('copy failed')
            return write(target,*args)
        with patch.object(setup,'atomic_write',side_effect=fail_once),self.assertRaises(OSError):
            setup.ensure('cursor',self.home,install_skill=True)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual((skill/'README.md').read_text(),'previous version')
        self.assertFalse((skill/'SKILL.md').exists())
    def test_install_only_release_allowlist(self):
        with patch.object(setup,'ROOT',self.home/'source'):
            setup.ROOT.mkdir()
            for relative in setup.ALLOW|{'manifest.json'}:
                target=setup.ROOT/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('fixture')
            (setup.ROOT/'private.txt').write_text('must stay local')
            result=setup.ensure('cursor',self.home,install_skill=True)
        self.assertFalse((Path(result['skill_path'])/'private.txt').exists())
    def test_rollback_preserves_concurrent_edit_and_restores_other_files(self):
        path=self.home/'.cursor/mcp.json';path.parent.mkdir(parents=True);path.write_text('{"mcpServers":{}}')
        skill=self.home/'.cursor/skills/venture-playbook';before=path.read_bytes();write=setup.atomic_write
        def concurrent_failure(target,*args):
            if Path(target)==skill/'scripts/onboarding.py':
                (skill/'README.md').write_text('concurrent user edit')
                raise OSError('copy failed')
            return write(target,*args)
        with patch.object(setup,'atomic_write',side_effect=concurrent_failure),self.assertRaisesRegex(ValueError,'rollback_conflict'):
            setup.ensure('cursor',self.home,install_skill=True)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual((skill/'README.md').read_text(),'concurrent user edit')
        self.assertFalse((skill/'SKILL.md').exists())


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT.parent/'temp')
        self.home=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_first_prompt_then_no_repeat(self):
        self.assertTrue(guide.status('codex',self.home)['show_intro'])
        guide.choose('codex',self.home,'skip')
        self.assertFalse(guide.status('codex',self.home)['show_intro'])
        self.assertEqual(guide.status('codex',self.home)['mode'],'web')
    def test_registered_continues_login_one_step(self):
        guide.choose('codex',self.home,'register')
        self.assertEqual(guide.step('codex',self.home)['stage'],'scan')
        self.assertEqual(guide.advance('codex',self.home)['stage'],'register')
        self.assertEqual(guide.advance('codex',self.home)['stage'],'verify')
        self.assertEqual(guide.login('codex',self.home)['stage'],'login')
        result=guide.step('codex',self.home)
        self.assertIsInstance(result['instruction'],str)
        self.assertNotIn('steps',result)
        self.assertEqual(result['agent_action'],['codex','mcp','login','scys-mcp'])
    def test_user_done_does_not_claim_authenticated(self):
        guide.choose('codex',self.home,'connect')
        guide.login('codex',self.home)
        result=guide.advance('codex',self.home)
        self.assertEqual(result['stage'],'sign_in')
        self.assertEqual(guide.status('codex',self.home)['authentication'],'unknown')
    def test_skip_mid_guide_persists(self):
        guide.choose('cursor',self.home,'register');guide.choose('cursor',self.home,'skip')
        self.assertFalse(guide.status('cursor',self.home)['show_intro'])
    def test_readonly_receipt_required(self):
        guide.choose('codex',self.home,'connect')
        with self.assertRaises(ValueError):guide.verified('codex',self.home,{'ok':True})
        receipt={'ok':True,'server_url':setup.ENDPOINT,'tool':'searchTopic','operation':'read','verified_at':'2026-10-13T01:00:00+08:00'}
        result=guide.verified('codex',self.home,receipt)
        self.assertEqual(result['authentication'],'verified')
        self.assertEqual(guide.status('codex',self.home)['authentication'],'unknown')
        self.assertTrue(guide.status('codex',self.home)['last_verified'])
    def test_state_is_outside_skill_and_upgrade_preserves_it(self):
        guide.choose('gemini',self.home,'skip')
        setup.ensure('gemini',self.home,install_skill=True)
        self.assertFalse(guide.status('gemini',self.home)['show_intro'])
        self.assertNotIn('onboarding.json',[p.name for p in (self.home/'.gemini/skills/venture-playbook').rglob('*')])
    def test_existing_connection_check_has_no_login_action(self):
        result=guide.choose('codex',self.home,'connect')
        self.assertEqual(result['stage'],'verify')
        self.assertEqual(result['agent_action'],[])
    def test_skip_resume_keeps_exact_step(self):
        guide.choose('cursor',self.home,'register');guide.advance('cursor',self.home)
        guide.choose('cursor',self.home,'skip')
        self.assertEqual(guide.step('cursor',self.home)['stage'],'done')
        self.assertEqual(guide.resume('cursor',self.home)['stage'],'register')
    def test_resume_login_checks_connection_again(self):
        guide.choose('codex',self.home,'connect');guide.login('codex',self.home)
        guide.choose('codex',self.home,'skip')
        result=guide.resume('codex',self.home)
        self.assertEqual(result['stage'],'verify');self.assertEqual(result['agent_action'],[])
    def test_resume_without_skip_keeps_current_registration_step(self):
        guide.choose('codex',self.home,'register');guide.advance('codex',self.home)
        self.assertEqual(guide.resume('codex',self.home)['stage'],'register')
    def test_corrupt_state_is_explicit_error(self):
        path=setup.state_dir(self.home,'codex')/'choice.json';path.parent.mkdir(parents=True)
        path.write_text('{}')
        with self.assertRaises(ValueError):guide.status('codex',self.home)
    def test_qr_asset_exists(self):
        self.assertTrue(ROOT.joinpath('会员体验卡海报.jpg').is_file())


if __name__=='__main__':unittest.main()
