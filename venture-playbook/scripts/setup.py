#!/usr/bin/env python3
"""Quiet, offline global Skill/MCP setup. Authentication is never started here."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import sys
import tempfile
try:
    import tomllib
except ImportError:
    tomllib = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from release import ALLOW
ENDPOINT = 'https://mcp.scys.com/shengcai-web/mcp'
SERVER = 'scys-mcp'
HOSTS = {
    'codex': ('.agents/skills', '.codex/config.toml', 'toml', {'url': ENDPOINT}),
    'claude': ('.claude/skills', '.claude.json', 'mcpServers', {'type': 'http', 'url': ENDPOINT}),
    'cursor': ('.cursor/skills', '.cursor/mcp.json', 'mcpServers', {'url': ENDPOINT}),
    'windsurf': ('.codeium/windsurf/skills', '.config/devin/mcp_config.json', 'mcpServers', {'serverUrl': ENDPOINT}),
    'gemini': ('.gemini/skills', '.gemini/settings.json', 'mcpServers', {'httpUrl': ENDPOINT}),
    'opencode': ('.config/opencode/skills', '.config/opencode/opencode.json', 'mcp', {'type': 'remote', 'url': ENDPOINT, 'enabled': False}),
}


def state_dir(home, host):
    return Path(home).expanduser().resolve()/'.local/state/venture-playbook'/host


def detect(home):
    if os.environ.get('CODEX_THREAD_ID'): return 'codex'
    if os.environ.get('CLAUDECODE'): return 'claude'
    candidates = [h for h, (_, path, _, _) in HOSTS.items() if (Path(home)/path).is_file() or
                  (Path(path).parent != Path('.') and (Path(home)/Path(path).parent).exists())]
    if 'claude' not in candidates and (Path(home)/'.claude').exists():candidates.append('claude')
    if len(candidates) != 1: raise ValueError('harness_required')
    return candidates[0]


def host_paths(host, home):
    skill_root, config_name, _, _ = HOSTS[host]
    skill, config = home/skill_root/'venture-playbook', home/config_name
    if home == Path.home().resolve():
        if host=='codex' and os.environ.get('CODEX_HOME'):config=Path(os.environ['CODEX_HOME']).expanduser()/'config.toml'
        if host=='claude' and os.environ.get('CLAUDE_CONFIG_DIR'):raise ValueError('custom_claude_config_requires_official_cli')
        if host in ('windsurf','opencode') and os.environ.get('XDG_CONFIG_HOME'):
            base=Path(os.environ['XDG_CONFIG_HOME']).expanduser()
            config=base/('devin/mcp_config.json' if host=='windsurf' else 'opencode/opencode.json')
            if host=='opencode':skill=base/'opencode/skills/venture-playbook'
        if host=='windsurf' and os.name=='nt':config=Path(os.environ.get('APPDATA',str(home/'AppData/Roaming')))/'devin/mcp_config.json'
    return skill,config


def reject_symlinks(path, home):
    for item in (path, *path.parents):
        if item == home: break
        if item.is_symlink(): raise ValueError('symlink_config_requires_manual_check')


def atomic_write(path, content, expected, backups):
    path = Path(path)
    current = path.read_bytes() if path.exists() else None
    if current != expected: raise ValueError('concurrent_change')
    if current == content: return False
    path.parent.mkdir(parents=True, exist_ok=True)
    if current is not None:
        backups.mkdir(parents=True, exist_ok=True, mode=0o700)
        backup = backups/(hashlib.sha256(str(path).encode()).hexdigest()[:12]+'-'+hashlib.sha256(current).hexdigest()[:12]+'.bak')
        if not backup.exists():
            with backup.open('xb') as out: out.write(current)
            backup.chmod(0o600)
    fd, tmp = tempfile.mkstemp(prefix='.venture-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out: out.write(content)
        os.chmod(tmp, path.stat().st_mode & 0o777 if path.exists() else 0o600)
        if (path.read_bytes() if path.exists() else None) != expected: raise ValueError('concurrent_change')
        os.replace(tmp, path)
        if path.read_bytes() != content: raise ValueError('readback_failed')
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return True


def ensure(host, home, install_skill=False):
    if host not in HOSTS: raise ValueError('unsupported_harness')
    home = Path(home).expanduser().resolve()
    _, _, section, template = HOSTS[host]
    skill,config=host_paths(host,home)
    state = state_dir(home, host)
    reject_symlinks(config, home); reject_symlinks(skill, home); reject_symlinks(state, home)
    if install_skill and skill.resolve() != ROOT and (skill/'manifest.json').exists():
        reject_symlinks(skill/'manifest.json', home)
        versions = []
        for path in (skill/'manifest.json', ROOT/'manifest.json'):
            item = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(item, dict): raise ValueError('invalid_install_manifest')
            value = item.get('version', '')
            if item.get('name') != 'venture-playbook' or not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
                raise ValueError('invalid_install_manifest')
            versions.append(tuple(map(int, value.split('.'))))
        if versions[0] > versions[1]: raise ValueError('installed_newer_use_global_skill')
    if host == 'opencode' and config.with_suffix('.jsonc').exists(): raise ValueError('jsonc_requires_official_config_editor')
    before = config.read_bytes() if config.exists() else None
    text = before.decode('utf-8') if before else ''
    if section == 'toml':
        if tomllib is None: raise ValueError('codex_setup_requires_python_3_11')
        data = tomllib.loads(text)
        servers = data.get('mcp_servers', {})
    else:
        data = json.loads(text) if text else {}
        if not isinstance(data, dict): raise ValueError('invalid_config_root')
        servers = data.get(section, {})
    if not isinstance(servers, dict): raise ValueError('invalid_mcp_section')
    found = next((name for name, value in servers.items() if isinstance(value, dict) and
                  any(value.get(key) == ENDPOINT for key in ('url','serverUrl','httpUrl'))), None)
    if not found and SERVER in servers: raise ValueError('server_name_conflict')
    if found:
        content = before
    elif section == 'toml':
        content = (text.rstrip()+'\n\n[mcp_servers.scys-mcp]\nurl = '+json.dumps(ENDPOINT)+'\n').lstrip('\n').encode()
        tomllib.loads(content.decode())
    else:
        data.setdefault(section, {})[SERVER] = template.copy()
        content = (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = state/'setup.lock'
    try:
        fd = os.open(lock, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('setup_busy') from None
    os.close(fd)
    journal = []
    try:
        plans = [(config, content, before)]
        if install_skill and skill.resolve() != ROOT:
            for relative in sorted(ALLOW | {'manifest.json'}):
                source = ROOT/relative
                if not source.is_file() or source.is_symlink(): raise ValueError('missing_release_file')
                target = skill/relative
                reject_symlinks(target, home)
                previous = target.read_bytes() if target.exists() else None
                plans.append((target, source.read_bytes(), previous))
        result = {'configured': True, 'changed': content != before, 'harness': host, 'config_path': str(config),
                  'skill_path': str(skill), 'server_name': found or SERVER, 'authentication': 'not_attempted',
                  'connection_deferred': host=='opencode' and not found}
        receipt = state/'setup-receipt.json'
        plans.append((receipt, (json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode(),
                      receipt.read_bytes() if receipt.exists() else None))
        for path, new, old in plans:
            if new == old: continue
            journal.append((path, new, old))
            atomic_write(path, new, old, state/'backups')
        return result
    except (OSError, ValueError):
        rollback_failed = False
        for path, new, old in reversed(journal):
            try:
                current = path.read_bytes() if path.exists() else None
                if current == old: continue
                if current != new:
                    rollback_failed = True
                    continue
                if old is None: path.unlink()
                else: atomic_write(path, old, new, state/'backups')
            except (OSError, ValueError): rollback_failed = True
        if rollback_failed: raise ValueError('rollback_conflict') from None
        raise
    finally:
        lock.unlink()


def activate(host, home):
    """Enable OpenCode only after the customer chooses to connect."""
    result = ensure(host, home)
    if host == 'opencode':
        path = Path(result['config_path']); before = path.read_bytes(); data = json.loads(before)
        data['mcp'][result['server_name']]['enabled'] = True
        atomic_write(path, (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode(), before, state_dir(home,host)/'backups')
    return result


def main():
    p=argparse.ArgumentParser(description='默认静默安装到全局目录并配置生财；不登录、不联网。')
    p.add_argument('--harness', choices=['auto', *HOSTS], default='auto')
    p.add_argument('--home', type=Path, default=Path.home())
    p.add_argument('--install-skill', action='store_true')
    p.add_argument('--activate', action='store_true')
    p.add_argument('--json', action='store_true', help='仅供Agent读取，客户界面不展示')
    p.add_argument('--report', type=Path)
    args=p.parse_args()
    try:
        host=detect(args.home) if args.harness=='auto' else args.harness
        result=activate(host,args.home) if args.activate else ensure(host,args.home,args.install_skill)
        code=0
    except (OSError, ValueError, UnicodeError) as exc:
        known={'harness_required','unsupported_harness','symlink_config_requires_manual_check','jsonc_requires_official_config_editor',
               'codex_setup_requires_python_3_11','custom_claude_config_requires_official_cli','invalid_config_root','invalid_mcp_section','server_name_conflict','setup_busy','concurrent_change','readback_failed','missing_release_file','rollback_conflict','installed_newer_use_global_skill','invalid_install_manifest'}
        reason=str(exc) if str(exc) in known else 'invalid_or_unwritable_config'
        result={'configured':False,'reason':reason,'authentication':'not_attempted'};code=2
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if args.json: print(json.dumps(result,ensure_ascii=False))
    return code


if __name__=='__main__':raise SystemExit(main())
