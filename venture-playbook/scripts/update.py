#!/usr/bin/env python3
"""Check the fixed Gitee repository on every invocation; never run downloaded code."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from setup import atomic_write, reject_symlinks
API = 'https://gitee.com/api/v5/repos/cursorsome/venture-playbook'
TAG = re.compile(r'venture-playbook-v(\d+)\.(\d+)\.(\d+)\Z')
VERSION = re.compile(r'\d+\.\d+\.\d+\Z')
LIMIT = 16 * 1024 * 1024

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('redirect_rejected')

class Gitee:
    def get(self, suffix):
        # The fixed distribution repository is public; never send customer credentials.
        headers = {'Accept': 'application/json', 'User-Agent': 'venture-playbook-updater'}
        request = urllib.request.Request(API + suffix, headers=headers)
        with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
            data = response.read(LIMIT + 1)
        if len(data) > LIMIT: raise ValueError('response_too_large')
        return json.loads(data)
    def latest(self):
        versions = []
        for page in range(1, 101):
            tags = self.get(f'/tags?per_page=100&page={page}')
            if not isinstance(tags, list): raise ValueError('invalid_tags')
            for item in tags:
                match = TAG.fullmatch(item.get('name', ''))
                if match:
                    sha = item.get('commit', {}).get('sha', '')
                    if not re.fullmatch('[0-9a-f]{40}', sha): raise ValueError('invalid_commit')
                    versions.append((tuple(map(int, match.groups())), sha))
            if len(tags) < 100: break
        else: raise ValueError('tag_listing_incomplete')
        if not versions: raise ValueError('no_stable_version')
        version, sha = max(versions)
        return '.'.join(map(str, version)), sha
    def file(self, sha, name):
        from urllib.parse import quote
        item = self.get('/contents/' + quote('venture-playbook/' + name, safe='/') + '?ref=' + sha)
        if item.get('type') != 'file' or item.get('encoding') != 'base64':
            raise ValueError('invalid_remote_file')
        return base64.b64decode(''.join(item['content'].split()), validate=True)


def version(value):
    if not isinstance(value, str) or not VERSION.fullmatch(value): raise ValueError('invalid_version')
    return tuple(map(int, value.split('.')))


def manifest(data, require_update=True):
    value = json.loads(data)
    if value.get('name') != 'venture-playbook': raise ValueError('wrong_package')
    version(value.get('version'))
    files = value.get('sha256')
    if not isinstance(files, dict) or not files or len(files) > 200: raise ValueError('invalid_manifest')
    folded = set()
    for name, digest in files.items():
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or any(p in ('..', '.') for p in name.split('/'))
                or '\\' in name or ':' in name or name.endswith(('.', ' '))
                or any(p.startswith('.') for p in path.parts) or name == 'manifest.json'
                or name.casefold() in folded or not re.fullmatch('[0-9a-f]{64}', str(digest))):
            raise ValueError('unsafe_manifest')
        if len(path.parts) > 1 and path.parts[0] not in {'scripts','assets','references','agents','tests','examples'}:
            raise ValueError('unsafe_manifest')
        folded.add(name.casefold())
    required = {'SKILL.md','scripts/venture.py','scripts/setup.py'}
    if require_update: required.add('scripts/update.py')
    if not required <= files.keys():
        raise ValueError('incomplete_update')
    return value


def update(root, work, client=None):
    root, work = Path(root).absolute(), Path(work).absolute()
    reject_symlinks(root, root.anchor)
    if root.is_relative_to(work) or work.is_relative_to(root): raise ValueError('work_must_be_outside_skill')
    work.mkdir(parents=True, exist_ok=True)
    client = client or Gitee()
    old_bytes = (root/'manifest.json').read_bytes()
    old = manifest(old_bytes, require_update=False)
    for name, digest in old['sha256'].items():
        target = root/name; reject_symlinks(target, root.parent)
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError('local_modification')
    current = old['version']
    newest, sha = client.latest()  # Deliberately no daily cache.
    result = {'source': API, 'current_version': current, 'latest_version': newest, 'commit': sha}
    if version(newest) <= version(current):
        return dict(result, ready=True, status='current' if newest == current else 'local_ahead', skill_path=str(root))
    lock = root.parent/('.' + root.name + '-update.lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    journal = []
    try:
        transaction = Path(tempfile.mkdtemp(prefix='update-', dir=work))
        raw = client.file(sha, 'manifest.json'); new = manifest(raw)
        if new['version'] != newest: raise ValueError('tag_manifest_mismatch')
        with ThreadPoolExecutor(max_workers=4) as pool:
            contents = dict(zip(new['sha256'], pool.map(lambda n: client.file(sha, n), new['sha256'])))
        if sum(map(len, contents.values())) > LIMIT: raise ValueError('package_too_large')
        for name, digest in new['sha256'].items():
            if hashlib.sha256(contents[name]).hexdigest() != digest: raise ValueError('checksum_mismatch')
        if not re.search(r'^  version: "' + re.escape(newest) + r'"\s*$', contents['SKILL.md'].decode('utf-8'), re.M):
            raise ValueError('skill_version_mismatch')
        contents['manifest.json'] = raw
        plans = []
        for name in sorted(set(old['sha256']) | set(contents)):
            # Validate old names too, before accessing any target.
            p = PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name: raise ValueError('unsafe_old_manifest')
            target = root/name; reject_symlinks(target, root.parent)
            before = target.read_bytes() if target.exists() else None
            expected = old['sha256'].get(name)
            if name == 'manifest.json':
                if before != old_bytes: raise ValueError('concurrent_change')
            elif expected:
                if before is None or hashlib.sha256(before).hexdigest() != expected: raise ValueError('local_modification')
            elif before is not None: raise ValueError('untracked_file_collision')
            after = contents.get(name)
            if before != after: plans.append((target, after, before))
        # Write manifest last so its version never announces a partial install.
        plans.sort(key=lambda row: row[0].name == 'manifest.json')
        (transaction/'plan.json').write_text(json.dumps([{'path':str(p.relative_to(root)),
            'before_sha256':hashlib.sha256(b).hexdigest() if b is not None else None,
            'after_sha256':hashlib.sha256(a).hexdigest() if a is not None else None}
            for p,a,b in plans], ensure_ascii=False, indent=2), encoding='utf-8')
        for target, after, before in plans:
            journal.append((target, after, before))
            if after is None:
                if target.read_bytes() != before: raise ValueError('concurrent_change')
                backup = transaction/'removed'/target.relative_to(root)
                backup.parent.mkdir(parents=True, exist_ok=True); backup.write_bytes(before)
                target.unlink()
            else: atomic_write(target, after, before, transaction/'backups')
        for name, data in contents.items():
            if (root/name).read_bytes() != data: raise ValueError('readback_failed')
        return dict(result, ready=True, status='updated', skill_path=str(root), backup_path=str(transaction), reload_skill=True)
    except Exception:
        conflict = False
        for target, after, before in reversed(journal):
            try:
                actual = target.read_bytes() if target.exists() else None
                if actual == before: continue
                if actual != after: conflict = True; continue
                if before is None: target.unlink()
                else: atomic_write(target, before, after, transaction/'backups')
            except Exception: conflict = True
        if conflict: raise ValueError('rollback_conflict') from None
        raise
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description='每次先检查Gitee正式版本，校验后更新；失败阻断后续任务。')
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try: result = update(ROOT, args.work_dir); code = 0
    except Exception as exc:
        # Never include server response bodies, credentials or raw exception text.
        known = {'local_modification','untracked_file_collision','rollback_conflict','checksum_mismatch',
                 'tag_manifest_mismatch','skill_version_mismatch','unsafe_manifest','incomplete_update',
                 'concurrent_change','readback_failed','no_stable_version','redirect_rejected'}
        reason = str(exc) if str(exc) in known else 'update_check_failed'
        if isinstance(exc, urllib.error.HTTPError):
            reason = {401:'public_source_unavailable', 403:'source_denied_or_rate_limited',
                      404:'public_source_not_found', 429:'source_rate_limited'}.get(exc.code, 'source_http_error')
        elif isinstance(exc, (urllib.error.URLError, TimeoutError)): reason = 'network_unavailable'
        elif isinstance(exc, FileExistsError): reason = 'update_busy_or_stale_lock'
        elif isinstance(exc, PermissionError): reason = 'update_permission_denied'
        result = {'ready':False, 'status':'blocked', 'reason':reason}; code = 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return code

if __name__ == '__main__': raise SystemExit(main())
