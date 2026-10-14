import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vp_update', ROOT/'scripts/update.py')
u = importlib.util.module_from_spec(spec); spec.loader.exec_module(u)


def package(ver):
    data = {'SKILL.md': ('---\n  version: "'+ver+'"\n').encode(),
            'scripts/venture.py': b'report', 'scripts/setup.py': b'setup', 'scripts/update.py': b'update'}
    data['manifest.json'] = json.dumps({'name':'venture-playbook', 'version':ver,
        'sha256':{n:hashlib.sha256(v).hexdigest() for n,v in data.items()}}).encode()
    return data

class Fake:
    def __init__(self, ver='9.1.16'):
        self.ver = ver; self.data = package(ver); self.checks = 0
    def latest(self): self.checks += 1; return self.ver, 'a'*40
    def file(self, sha, name):
        assert sha == 'a'*40
        return self.data[name]

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT.parent/'temp')
        self.base = Path(self.tmp.name); self.root = self.base/'中文 空格 Skill'; self.work = self.base/'temp'
        self.old = package('9.1.15')
        for name, data in self.old.items():
            p=self.root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        self.personal=self.root/'personal-note.txt'; self.personal.write_bytes(b'keep')
        self.config=self.base/'config.json'; self.config.write_bytes(b'credentials-remain-outside-package')
    def tearDown(self): self.tmp.cleanup()
    def assertOld(self):
        for name,data in self.old.items(): self.assertEqual((self.root/name).read_bytes(),data)
    def test_upgrade_then_check_every_invocation(self):
        client=Fake(); result=u.update(self.root,self.work,client)
        self.assertEqual(result['status'],'updated'); self.assertTrue(result['reload_skill'])
        for name,data in client.data.items(): self.assertEqual((self.root/name).read_bytes(),data)
        self.assertEqual(u.update(self.root,self.work,client)['status'],'current')
        self.assertEqual(client.checks,2)
        self.assertEqual(self.personal.read_bytes(),b'keep')
        self.assertEqual(self.config.read_bytes(),b'credentials-remain-outside-package')
    def test_staging_creation_failure_releases_lock(self):
        with patch.object(u.tempfile,'mkdtemp',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):u.update(self.root,self.work,Fake())
        self.assertFalse((self.root.parent/('.'+self.root.name+'-update.lock')).exists())
        self.assertOld()
    def test_public_source_ignores_customer_token(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=b'[]'
        opener=MagicMock();opener.open.return_value=response
        with patch.dict(u.os.environ,{'GITEE_ACCESS_TOKEN':'expired-test-value'}),patch.object(u.urllib.request,'build_opener',return_value=opener):
            self.assertEqual(u.Gitee().get('/tags'),[])
        self.assertFalse(opener.open.call_args.args[0].has_header('Authorization'))
    def test_equal_and_older_do_not_write(self):
        for ver in ['9.1.15','9.1.9']:
            with patch.object(u,'atomic_write',side_effect=AssertionError('unexpected write')):
                self.assertTrue(u.update(self.root,self.work,Fake(ver))['ready'])
            self.assertOld()
    def test_checksum_failure_preserves_old(self):
        fake=Fake();fake.data['scripts/venture.py']=b'corrupt'
        with self.assertRaisesRegex(ValueError,'checksum'):u.update(self.root,self.work,fake)
        self.assertOld()
    def test_local_change_preserved(self):
        (self.root/'scripts/venture.py').write_bytes(b'my change')
        with self.assertRaisesRegex(ValueError,'local_modification'):u.update(self.root,self.work,Fake())
        self.assertEqual((self.root/'scripts/venture.py').read_bytes(),b'my change')
    def test_failed_write_rolls_back(self):
        real=u.atomic_write; calls=[]
        def fail_once(*args):
            calls.append(args[0]);real(*args)
            if len(calls)==2:raise OSError('injected post-write failure')
        with patch.object(u,'atomic_write',side_effect=fail_once):
            with self.assertRaises(OSError):u.update(self.root,self.work,Fake())
        self.assertOld()
    def test_unsafe_paths_and_case_collision(self):
        for name in ['../escape','/abs','scripts/../../escape','scripts\\evil','assets/x:ads','SKILL.MD']:
            fake=Fake();m=json.loads(fake.data['manifest.json']);m['sha256'][name]='a'*64
            fake.data['manifest.json']=json.dumps(m).encode()
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'unsafe_manifest'):
                u.update(self.root,self.work,fake)
            self.assertOld()
    def test_tag_manifest_disagreement(self):
        fake=Fake();fake.data=package('9.1.17')
        with self.assertRaisesRegex(ValueError,'tag_manifest'):u.update(self.root,self.work,fake)
        self.assertOld()
    def test_corrupt_current_not_marked_ready(self):
        (self.root/'scripts/venture.py').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'local_modification'):
            u.update(self.root,self.work,Fake('9.1.15'))
    def test_untracked_collision(self):
        fake=Fake();m=json.loads(fake.data['manifest.json'])
        fake.data['personal-note.txt']=b'overwrite'
        m['sha256']['personal-note.txt']=hashlib.sha256(b'overwrite').hexdigest()
        fake.data['manifest.json']=json.dumps(m).encode()
        with self.assertRaisesRegex(ValueError,'untracked_file_collision'):
            u.update(self.root,self.work,fake)
        self.assertOld();self.assertEqual(self.personal.read_bytes(),b'keep')
    def test_symlink_rejected(self):
        (self.root/'scripts/venture.py').unlink()
        (self.root/'scripts/venture.py').symlink_to(self.config)
        with self.assertRaisesRegex(ValueError,'symlink'):
            u.update(self.root,self.work,Fake())
        self.assertEqual(self.config.read_bytes(),b'credentials-remain-outside-package')
    def test_network_failure_preserves_old(self):
        fake=Fake()
        with patch.object(fake,'latest',side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):u.update(self.root,self.work,fake)
        self.assertOld()
    def test_busy_lock_preserved(self):
        lock=self.root.parent/('.'+self.root.name+'-update.lock');lock.touch()
        with self.assertRaises(FileExistsError):u.update(self.root,self.work,Fake())
        self.assertTrue(lock.exists()); self.assertOld()
    def test_only_stable_tags_and_numeric_order(self):
        def tag(name):return {'name':name,'commit':{'sha':'a'*40}}
        with patch.object(u.Gitee,'get',return_value=[tag('venture-playbook-v9.1.9'),tag('venture-playbook-v9.1.16'),tag('venture-playbook-v10.0.0-rc1'),tag('main')]):
            self.assertEqual(u.Gitee().latest()[0],'9.1.16')
    def test_pagination(self):
        tags=[{'name':'ignored'}]*100
        with patch.object(u.Gitee,'get',side_effect=[tags,[{'name':'venture-playbook-v9.1.16','commit':{'sha':'a'*40}}]]) as get:
            self.assertEqual(u.Gitee().latest()[0],'9.1.16'); self.assertEqual(get.call_count,2)
    def test_redirect_rejected(self):
        with self.assertRaisesRegex(ValueError,'redirect_rejected'):
            u.NoRedirect().redirect_request(None,None,302,'',{},'https://example.invalid')
    def test_concurrent_edit_not_overwritten_on_rollback(self):
        real=u.atomic_write
        def edit(path,after,before,backups):
            real(path,after,before,backups);path.write_bytes(b'concurrent');raise OSError('injected')
        with patch.object(u,'atomic_write',side_effect=edit):
            with self.assertRaisesRegex(ValueError,'rollback_conflict'):u.update(self.root,self.work,Fake())
        self.assertEqual((self.root/'SKILL.md').read_bytes(),b'concurrent')

if __name__ == '__main__':unittest.main()
