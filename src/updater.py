"""Optional manifest-based, integrity-checked local EXE updater.

Only accepts HTTPS links, never runs scripts received from the internet.
Release feed can be preconfigured for the public official GitHub repository.
"""
from __future__ import annotations
import hashlib, json, os, re, subprocess, sys, tempfile, urllib.request
from pathlib import Path

VERSION = '0.6.1'
MAX_MANIFEST = 32_768
MAX_EXE = 400 * 1024 * 1024


def version_parts(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{1,4}\.\d{1,4}(?:\.\d{1,4})?',value):
        raise ValueError('Invalid update version')
    return tuple(int(x) for x in (value + ('.0' if value.count('.') == 1 else '')).split('.'))


def safe_https(url):
    from urllib.parse import urlsplit
    if not isinstance(url,str) or len(url)>2048 or any(c.isspace() for c in url):
        raise ValueError('Invalid URL')
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):
        raise ValueError('Updates require an HTTPS URL without credentials')
    return url


def _fetch(url,max_bytes):
    req=urllib.request.Request(safe_https(url),headers={'User-Agent':'ModeShift/'+VERSION,'Accept':'application/json, application/octet-stream'})
    with urllib.request.urlopen(req,timeout=18) as resp:
        safe_https(resp.url)
        if resp.headers.get('Content-Length') and int(resp.headers['Content-Length'])>max_bytes:
            raise ValueError('Download exceeds size limit')
        data=resp.read(max_bytes+1)
        if len(data)>max_bytes:raise ValueError('Download exceeds size limit')
        return data


def check(manifest_url):
    data=json.loads(_fetch(manifest_url,MAX_MANIFEST))
    if not isinstance(data,dict):raise ValueError('Invalid update manifest')
    release_version=data.get('version')
    version_parts(release_version)
    download=safe_https(data.get('url'))
    sha=data.get('sha256')
    if not isinstance(sha,str) or not re.fullmatch('[a-fA-F0-9]{64}',sha):
        raise ValueError('Manifest must contain a SHA-256 digest')
    installer_url=data.get('installer_url');installer_sha=data.get('installer_sha256')
    if installer_url is not None:safe_https(installer_url)
    if installer_sha is not None and (not isinstance(installer_sha,str) or not re.fullmatch('[a-fA-F0-9]{64}',installer_sha)):raise ValueError('Invalid installer digest')
    return {'installer_url':installer_url,'installer_sha256':installer_sha.lower() if installer_sha else None,'version':release_version,'url':download,'sha256':sha.lower(),
            'notes':str(data.get('notes',''))[:1200],
            'available':version_parts(release_version)>version_parts(VERSION)}


def download_verified(release,destination):
    # Download is held in a temporary local directory, not in the active program path.
    blob=_fetch(release['url'],MAX_EXE)
    if hashlib.sha256(blob).hexdigest()!=release['sha256']:
        raise ValueError('Update failed SHA-256 integrity verification')
    if not blob.startswith(b'MZ'):
        raise ValueError('Release is not a Windows executable')
    destination=Path(destination)
    destination.write_bytes(blob)
    return destination


def make_replacement_script(target,staged,expected_sha,pid,folder):
    """Create a local PowerShell replacement helper. Only for user-writable portable EXEs.
    The original executable is kept as a .previous backup until a future update.
    """
    target=Path(target).resolve();staged=Path(staged).resolve()
    if not target.is_file() or not staged.is_file() or target.suffix.lower()!='.exe':
        raise ValueError('Updater can replace only an existing portable EXE')
    if not re.fullmatch('[a-f0-9]{64}',expected_sha):raise ValueError('Invalid expected digest')
    def q(p):return "'"+str(p).replace("'","''")+"'"
    old=target.with_name(target.stem+'.previous.exe')
    script=Path(folder)/'replace_modeshift.ps1'
    script.write_text(f'''$ErrorActionPreference = 'Stop'
$target = {q(target)}
$stage = {q(staged)}
$backup = {q(old)}
$expected = '{expected_sha}'
try {{ Wait-Process -Id {int(pid)} -Timeout 45 -ErrorAction SilentlyContinue }} catch {{}}
Start-Sleep -Milliseconds 700
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $stage).Hash.ToLowerInvariant() -ne $expected) {{ exit 3 }}
try {{
 if (Test-Path -LiteralPath $backup) {{ Remove-Item -LiteralPath $backup -Force }}
 Move-Item -LiteralPath $target -Destination $backup -Force
 try {{ Move-Item -LiteralPath $stage -Destination $target -Force }}
 catch {{ Move-Item -LiteralPath $backup -Destination $target -Force; throw }}
 Start-Process -FilePath $target
}} catch {{ exit 4 }}
''',encoding='utf-8')
    return script


def start_replacement(target,staged,digest,folder):
    if os.name!='nt':raise RuntimeError('Windows is required to install an update')
    script=make_replacement_script(target,staged,digest,os.getpid(),folder)
    subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script)],
                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),close_fds=True)
    return script


def make_installer_script(target, installer, expected_sha, pid, folder):
    """Create a local helper to run a verified Inno Setup upgrade after app exits.

    Installed upgrade is not an in-place EXE move: it must run the installer to
    maintain the uninstall registry and shortcuts. User data is outside app dir.
    """
    target=Path(target).resolve();installer=Path(installer).resolve()
    if not target.is_file() or target.name.lower()!='modeshift.exe' or not installer.is_file():
        raise ValueError('Invalid installed application or installer')
    if not re.fullmatch('[a-f0-9]{64}',expected_sha):raise ValueError('Invalid installer digest')
    def q(p):return "'"+str(p).replace("'","''")+"'"
    script=Path(folder)/'upgrade_modeshift.ps1'
    script.write_text(f'''$ErrorActionPreference = 'Stop'
$exe = {q(target)}
$installer = {q(installer)}
$expected = '{expected_sha}'
try {{ Wait-Process -Id {int(pid)} -Timeout 60 -ErrorAction SilentlyContinue }} catch {{}}
Start-Sleep -Milliseconds 800
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $installer).Hash.ToLowerInvariant() -ne $expected) {{ exit 3 }}
$job = Start-Process -FilePath $installer -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/CLOSEAPPLICATIONS' -PassThru -Wait
if ($job.ExitCode -ne 0) {{ exit $job.ExitCode }}
if (Test-Path -LiteralPath $exe) {{ Start-Process -FilePath $exe }}
''',encoding='utf-8')
    return script


def start_installer_upgrade(target,installer,digest,folder):
    if os.name!='nt':raise RuntimeError('Windows is required')
    script=make_installer_script(target,installer,digest,os.getpid(),folder)
    subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(script)],
                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),close_fds=True)
    return script
