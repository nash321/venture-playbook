"""Shared bootstrap regression; Windows registry is simulated, never edited on Mac."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bootstrap_venture',ROOT/'scripts/bootstrap.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT.parent/'temp');self.home=Path(self.temp.name)
        self.python=self.home/'.local/share/venture-playbook/runtime/python/专用环境/bin/python3.11'
        self.python.parent.mkdir(parents=True);self.python.write_bytes(b'fixture')
        self.platform=patch.object(b.platform,'system',return_value='Darwin');self.platform.start()
    def tearDown(self):self.platform.stop();self.temp.cleanup()
    def test_profile_keeps_user_content_and_is_idempotent(self):
        p=self.home/'.zprofile';before='export OTHER="用户设置"\n';p.write_text(before,encoding='utf-8')
        with patch.dict(b.os.environ,{'SHELL':'/bin/zsh','PATH':'/usr/bin'}):
            first=b.enable_path(self.home,self.python);after=p.read_bytes()
            second=b.enable_path(self.home,self.python)
            self.assertTrue(first['changed']);self.assertFalse(second['changed'])
            self.assertEqual(p.read_bytes(),after);self.assertTrue(p.read_text('utf-8').startswith(before))
            self.assertEqual(b.os.environ['PATH'],'/usr/bin:'+str(self.python.parent))
    def test_profile_rollback_preserves_original_bytes(self):
        p=self.home/'.bash_profile';old=b'# user config\n';p.write_bytes(old)
        with patch.dict(b.os.environ,{'SHELL':'/bin/bash','PATH':'/usr/bin'}):
            token=b.enable_path(self.home,self.python);b.restore_path(token)
            self.assertEqual(p.read_bytes(),old);self.assertEqual(b.os.environ['PATH'],'/usr/bin')
    def test_rollback_does_not_overwrite_concurrent_user_edit(self):
        with patch.dict(b.os.environ,{'SHELL':'/bin/zsh'}):
            token=b.enable_path(self.home,self.python);p=self.home/'.zprofile';p.write_bytes(p.read_bytes()+b'# concurrent user edit\n')
            with self.assertRaisesRegex(ValueError,'path_rollback_conflict'):b.restore_path(token)
            self.assertIn(b'concurrent user edit',p.read_bytes())
    def test_managed_path_cannot_point_at_system_python(self):
        with self.assertRaisesRegex(ValueError,'managed_python_outside_private_directory'):
            b.enable_path(self.home,Path(sys.executable))
        self.assertFalse((self.home/'.zprofile').exists())
    def test_setup_conflict_rolls_path_back_and_keeps_customer_config(self):
        config=self.home/'.cursor/mcp.json';config.parent.mkdir(parents=True)
        original=b'{"mcpServers":{"scys-mcp":{"url":"https://example.invalid/other"}}}'
        config.write_bytes(original)
        profile=self.home/'.zprofile';profile.write_bytes(b'# customer profile\n')
        with patch.dict(b.os.environ,{'SHELL':'/bin/zsh','PATH':'/usr/bin'}),patch.object(b,'doctor'),patch.object(b.sys,'executable',str(self.python)):
            with self.assertRaisesRegex(ValueError,'server_name_conflict'):b.prepare('cursor',self.home,managed=True)
            self.assertEqual(profile.read_bytes(),b'# customer profile\n')
            self.assertEqual(config.read_bytes(),original);self.assertEqual(b.os.environ['PATH'],'/usr/bin')
    def test_symlink_backup_directory_is_not_written(self):
        outside=self.home/'other';outside.mkdir()
        state=self.home/'.local/state/venture-playbook/runtime';state.mkdir(parents=True)
        (state/'backups').symlink_to(outside,target_is_directory=True)
        with patch.dict(b.os.environ,{'SHELL':'/bin/zsh'}):
            with self.assertRaisesRegex(ValueError,'symlink_config_requires_manual_check'):b.enable_path(self.home,self.python)
        self.assertFalse((self.home/'.zprofile').exists());self.assertEqual(list(outside.iterdir()),[])
    def test_existing_python_install_does_not_touch_path_or_download(self):
        with patch.dict(b.os.environ,{'PATH':'/usr/bin'}),patch.object(b,'doctor'),patch.object(b.setup,'ensure',return_value={'configured':True}),patch.object(b,'enable_path') as path:
            result=b.prepare('codex',self.home)
            self.assertTrue(result['ready']);path.assert_not_called();self.assertEqual(b.os.environ['PATH'],'/usr/bin')
    def test_doctor_failure_prevents_path_and_config_changes(self):
        with patch.object(b,'doctor',side_effect=ValueError('missing_assets')),patch.object(b,'enable_path') as path,patch.object(b.setup,'ensure') as install:
            with self.assertRaisesRegex(ValueError,'missing_assets'):b.prepare('codex',self.home,managed=True)
            path.assert_not_called();install.assert_not_called()
    def test_system_is_observed_and_cloud_linux_is_rejected(self):
        for name,expected in [('Darwin','macos'),('Windows','windows')]:
            with patch.object(b.platform,'system',return_value=name):self.assertEqual(b.system_profile()['system'],expected)
        with patch.object(b.platform,'system',return_value='Linux'),patch.object(b.setup,'ensure') as setup:
            with self.assertRaisesRegex(ValueError,'local_mac_or_windows_host_required'):b.prepare('codex',self.home)
            setup.assert_not_called()
    def test_windows_path_preserves_type_entries_and_case_insensitive_reuse(self):
        r=Registry(r'%LOCALAPPDATA%\Apps;C:\Tools')
        entry=r'C:\Users\客户\专用 Python'
        first=b.windows_path(self.home,entry,r);second=b.windows_path(self.home,entry.lower(),r)
        self.assertTrue(first['changed']);self.assertFalse(second['changed'])
        self.assertEqual(r.value,r'%LOCALAPPDATA%\Apps;C:\Tools;'+entry);self.assertEqual(r.kind,r.REG_EXPAND_SZ)
        b.restore_path(first);self.assertEqual(r.value,r'%LOCALAPPDATA%\Apps;C:\Tools')
        self.assertTrue(all(hive==r.HKEY_CURRENT_USER for hive in r.hives))
    def test_windows_rollback_does_not_overwrite_user_edit(self):
        r=Registry('original');token=b.windows_path(self.home,r'C:\Python',r);r.value+=';user edit'
        with self.assertRaisesRegex(ValueError,'path_rollback_conflict'):b.restore_path(token)
        self.assertIn('user edit',r.value)

class Registry:
    HKEY_CURRENT_USER='current-user';KEY_READ=1;KEY_WRITE=2;REG_SZ=1;REG_EXPAND_SZ=2
    def __init__(self,value):self.value=value;self.kind=self.REG_EXPAND_SZ;self.hives=[]
    def CreateKeyEx(self,hive,*args):self.hives.append(hive);return self
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def QueryValueEx(self,*args):
        if self.value is None:raise FileNotFoundError()
        return self.value,self.kind
    def SetValueEx(self,key,name,zero,kind,value):self.value=value;self.kind=kind
    def DeleteValue(self,*args):self.value=None

if __name__=='__main__':unittest.main()
