"""ModeShift — personal, reversible Windows workstation optimization manager.
Standard-library user interface; optional psutil improves metrics.
"""
from __future__ import annotations
import ctypes, csv, datetime as dt, json, os, platform, subprocess, sys, threading, time, traceback, shutil, re
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
import updater
from tkinter import messagebox, filedialog, ttk

try:
    import psutil
except ImportError:
    psutil = None
try:
    import winreg
except ImportError:
    winreg = None

APP = 'ModeShift'
ROOT = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / APP
ROOT.mkdir(parents=True, exist_ok=True)
SESSION_DIR = ROOT / 'measurements'
STATE_FILE = ROOT / 'state.json'
LOG_FILE = ROOT / 'activity.log'
BG='#080e19'; PANEL='#101b2b'; PANEL2='#1b2a40'; LINE='#253750'; TXT='#f0f5ff'; MUTED='#96a9c3'; ACC='#ffad38'; BLUE='#4b8fff'; GOOD='#2fdfaa'; BAD='#fa817c'
FONT='Segoe UI'

def log(s):
    with LOG_FILE.open('a',encoding='utf-8') as f:
        f.write(f'[{dt.datetime.now().isoformat(timespec="seconds")}] {s}\n')

def run(args,timeout=12):
    p=subprocess.run(args,text=True,capture_output=True,timeout=timeout,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if p.returncode: raise RuntimeError((p.stderr or p.stdout or 'Command failed').strip()[:400])
    return p.stdout

def on_windows():
    return os.name == "nt"

def is_admin():
    if os.name!='nt':return False
    try:return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:return False

def read_json(p,default):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except (OSError,ValueError):return default

def persist(p,x):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,indent=2),encoding='utf-8');tmp.replace(p)

@dataclass(frozen=True)
class Tweak:
    key:str; name:str; category:str; desc:str; impact:str; admin:bool=False; restart:bool=False; risk:str='Low'
    # values are registry DWORD desired and default state; None means delete on restore if prior missing
    hive:str=''; path:str=''; value:str=''; on:int|None=None; off:int|None=None

# Only documented, narrowly-scoped Windows user settings. System power plans handled separately.
TWEAKS=[
 Tweak('game_mode','Windows Game Mode','Gaming','Enables Windows Game Mode scheduling preferences. May benefit games; results vary.','Gaming',False,False,'Low','HKCU',r'Software\Microsoft\GameBar','AutoGameModeEnabled',1,0),
 Tweak('game_dvr','Disable background game recording','Gaming','Turns off Game DVR capture in the current user profile; re-enable for clips.','Gaming',False,False,'Low','HKCU',r'System\GameConfigStore','GameDVR_Enabled',0,1),
 Tweak('capture','Disable Windows game capture','Gaming','Suppresses app capture in the Windows Game Bar configuration.','Gaming',False,False,'Low','HKCU',r'Software\Microsoft\Windows\CurrentVersion\GameDVR','AppCaptureEnabled',0,1),
 Tweak('visual_fx','Prefer Windows performance effects','Responsiveness','Sets the Windows visual effects preference to performance; some effects may need sign-out.','Everyday',False,True,'Medium','HKCU',r'Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects','VisualFXSetting',2,0),
 Tweak('transparency','Disable transparency effects','Responsiveness','Removes translucent Windows surfaces to reduce visual overhead.','Everyday',False,False,'Low','HKCU',r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize','EnableTransparency',0,1),
 Tweak('taskbar_anim','Disable taskbar animations','Responsiveness','Disables taskbar animations for the current user.','Everyday',False,True,'Low','HKCU',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','TaskbarAnimations',0,1),
 Tweak('mouse_trails','Disable pointer trails','Responsiveness','Turns off cursor trails if enabled.','Everyday',False,True,'Low','HKCU',r'Control Panel\Mouse','MouseTrails',0,1),
 Tweak('widgets','Hide taskbar widgets','Focus','Hides Windows taskbar Widgets entry on supported Windows builds.','Office',False,False,'Low','HKCU',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','TaskbarDa',0,1),
 Tweak('search_button','Hide taskbar search box','Focus','Hides taskbar search field; Windows Search remains available from Start.','Office',False,False,'Low','HKCU',r'Software\Microsoft\Windows\CurrentVersion\Search','SearchboxTaskbarMode',0,2),
 Tweak('notification_center','Disable toast notifications','Focus','Disables notification toasts for the current user; important alerts may be less visible.','Office',False,True,'Medium','HKCU',r'Software\Microsoft\Windows\CurrentVersion\PushNotifications','ToastEnabled',0,1),
 Tweak('background_apps','Restrict UWP background applications','Focus','Changes background permission for supported Store apps; may delay notifications/sync.','Office',False,True,'Medium','HKCU',r'Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications','GlobalUserDisabled',1,0),
 Tweak('file_ext','Show file extensions','Developer','Shows known file extensions in File Explorer to improve file safety and development workflow.','Developer',False,True,'Low','HKCU',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','HideFileExt',0,1),
 Tweak('hidden_files','Show hidden files','Developer','Displays hidden files in File Explorer (not protected operating-system files).','Developer',False,True,'Low','HKCU',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','Hidden',1,2),
 Tweak('explorer_thispc','Open File Explorer to This PC','Developer','Sets Explorer initial location to This PC.','Developer',False,False,'Low','HKCU',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','LaunchTo',1,2),
 Tweak('clipboard','Enable clipboard history','Productivity','Enables multi-item Windows clipboard history (Win+V); consider sensitive copied data.','Office',False,False,'Medium','HKCU',r'Software\Microsoft\Clipboard','EnableClipboardHistory',1,0),
 Tweak('snap','Enable window snapping','Productivity','Enables Windows Snap Assist for multitasking.','Office',False,False,'Low','HKCU',r'Control Panel\Desktop','WindowArrangementActive',1,0),
]
# Additional narrowly-scoped preferences. These are *not* presented as FPS boosts.
# Exact prior registry data/types are captured before every write.
EXTRA_SETTINGS = [
 # key, label, category, meaning, path, name, enabled, disabled, registry_string, restart
 ('task_view','Hide Task View button','Workspace','Hide the Task View taskbar button; Win+Tab remains available.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','ShowTaskViewButton',0,1,False,True),
 ('taskbar_badges','Hide app badges','Workspace','Hide taskbar notification badges without disabling notifications.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','TaskbarBadges',0,1,False,True),
 ('taskbar_seconds','Show clock seconds','Workspace','Show seconds in the system tray clock; may increase power usage.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','ShowSecondsInSystemClock',1,0,False,True),
 ('taskbar_align','Left-align taskbar','Workspace','Place Windows 11 taskbar buttons on the left.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','TaskbarAl',0,1,False,True),
 ('taskbar_desktop','Enable show desktop corner','Workspace','Enable show-desktop shortcut at the taskbar corner.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','TaskbarSd',1,0,False,True),
 ('taskbar_share','Enable taskbar window sharing','Workspace','Enable supported taskbar share-window functionality.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','TaskbarSn',1,0,False,True),
 ('taskbar_flash','Allow taskbar flashing','Workspace','Allow taskbar buttons to flash when an app requests attention.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','TaskbarFlashing',1,0,False,True),
 ('taskbar_multi','Show taskbar on all displays','Workspace','Show taskbar on secondary displays on supported builds.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','MMTaskbarEnabled',1,0,False,True),
 ('taskbar_nevercombine','Never combine taskbar buttons','Workspace','Show separate app windows on the taskbar where supported.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','TaskbarGlomLevel',2,0,False,True),
 ('taskbar_secondcombine','Never combine on secondary monitors','Workspace','Show separate taskbar buttons on secondary monitors.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','MMTaskbarGlomLevel',2,0,False,True),
 ('taskbar_chat','Hide Chat button (legacy)','Workspace','Hide legacy Windows 11 Chat button where still present.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','TaskbarMn',0,1,False,True),
 ('recent_items','Hide recent items in Start/Explorer','Privacy','Hide recent files in Start, jump lists and File Explorer.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','Start_TrackDocs',0,1,False,True),
 ('advertising_id','Disable advertising ID','Privacy','Turn off app-accessible Windows advertising identifier for this user.',r'Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo','Enabled',0,1,False,True),
 ('tailored','Disable tailored experiences (legacy)','Privacy','Disable legacy diagnostic-data-tailored experience suggestions.',r'Software\Microsoft\Windows\CurrentVersion\Privacy','TailoredExperiencesWithDiagnosticDataEnabled',0,1,False,True),
 ('suggested_apps','Disable suggested app installs','Privacy','Turn off supported silent suggested-app installation behavior.',r'Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager','SilentInstalledAppsEnabled',0,1,False,True),
 ('soft_landing','Disable Windows tips','Focus','Reduce suggestions for new Windows features where supported.',r'Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager','SoftLandingEnabled',0,1,False,True),
 ('content_suggestions','Disable content suggestions','Focus','Reduce suggested content in supported Windows surfaces.',r'Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager','SystemPaneSuggestionsEnabled',0,1,False,True),
 ('show_status','Show Explorer status bar','Explorer','Display details in the Explorer status bar when supported.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','ShowStatusBar',1,0,False,True),
 ('show_tooltips','Show Explorer file tips','Explorer','Enable pop-up information tips for files and folders.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','ShowInfoTip',1,0,False,True),
 ('separate_explorer','Separate Explorer processes','Explorer','Run folder windows in separate processes; uses additional memory.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','SeparateProcess',1,0,False,True),
 ('auto_check','Use selection checkboxes','Explorer','Enable checkboxes to select files and folders.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','AutoCheckSelect',1,0,False,True),
 ('expand_nav','Expand navigation to current folder','Explorer','Automatically expand Explorer tree to the active folder.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','NavPaneExpandToCurrentFolder',1,0,False,True),
 ('show_all_nav','Show all folders in navigation','Explorer','Include all folders in Explorer navigation pane.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','NavPaneShowAllFolders',1,0,False,True),
 ('show_empty','Show empty drives','Explorer','Show empty drives in This PC as well as occupied drives.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','HideDrivesWithNoMedia',0,1,False,True),
 ('superhidden','Show protected OS files (advanced)','Explorer','Reveal protected system files. Be careful not to delete or change them.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','ShowSuperHidden',1,0,False,True),
 ('colored_compressed','Color compressed/encrypted files','Explorer','Show compressed/encrypted NTFS files with distinctive text color.',r'Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced','ShowCompColor',1,0,False,True),
 ('window_contents','Show window contents during drag','Appearance','Draw window contents while dragging, rather than just an outline.',r'Control Panel\Desktop','DragFullWindows',1,0,True,True),
 ('menu_fast','Reduce menu animation delay','Appearance','Reduce menu hover delay to 100 ms. Not a CPU/FPS optimization.',r'Control Panel\Desktop','MenuShowDelay',100,400,True,True),
 ('window_animation','Disable minimize/maximize animations','Appearance','Suppress window minimize/maximize animation where supported.',r'Control Panel\Desktop\WindowMetrics','MinAnimate',0,1,True,True),
 ('cursor_shadow','Disable mouse pointer shadow','Appearance','Reduce decorative cursor shadow effect in Windows.',r'Control Panel\Cursors','CursorShadow',0,1,False,True),
 ('wallpaper_quality','Preserve wallpaper JPEG quality','Appearance','Request full JPEG wallpaper quality; visual preference, not a speedup.',r'Control Panel\Desktop','JPEGImportQuality',100,85,False,True),
 ('keyboard_delay','Faster keyboard repeat start','Input','Reduce delay before a held key begins repeating (applies after sign-out).',r'Control Panel\Keyboard','KeyboardDelay',0,1,True,True),
 ('keyboard_repeat','Faster keyboard repeat','Input','Use the fastest standard keyboard repeat speed.',r'Control Panel\Keyboard','KeyboardSpeed',31,25,True,True),
 ('hover_speed','Shorter mouse hover delay','Input','Reduce mouse hover delay to 200 ms.',r'Control Panel\Mouse','MouseHoverTime',200,400,True,True),
 ('pointer_precision','Disable Enhance Pointer Precision','Input','Disable Windows pointer acceleration for consistent mouse input.',r'Control Panel\Mouse','MouseSpeed',0,1,True,True),
 ('pointer_threshold1','Disable pointer acceleration threshold 1','Input','Set first pointer acceleration threshold to zero (pair with EPP toggle).',r'Control Panel\Mouse','MouseThreshold1',0,6,True,True),
 ('pointer_threshold2','Disable pointer acceleration threshold 2','Input','Set second pointer acceleration threshold to zero (pair with EPP toggle).',r'Control Panel\Mouse','MouseThreshold2',0,10,True,True),
 ('sticky_prompt','Disable Sticky Keys hotkey','Accessibility','Prevent Shift five-times hotkey from activating Sticky Keys; accessibility trade-off.',r'Control Panel\Accessibility\StickyKeys','HotkeyActive',0,1,True,True),
 ('toggle_prompt','Disable Toggle Keys hotkey','Accessibility','Prevent Num Lock hold shortcut from triggering Toggle Keys.',r'Control Panel\Accessibility\ToggleKeys','HotkeyActive',0,1,True,True),
 ('filter_prompt','Disable Filter Keys hotkey','Accessibility','Prevent prolonged right-Shift shortcut activating Filter Keys.',r'Control Panel\Accessibility\Keyboard Response','HotkeyActive',0,1,True,True),
 ('sound_scheme','Disable Windows event sounds','Focus','Set current user sound scheme to No Sounds; may remove useful system alerts.',r'AppEvents\Schemes','(Default)', '.None', '.Default',True,True),
]
# Some values above are version-specific or implementation-dependent. Do not expose
# the three accessibility hotkey entries until Windows-native validation confirms them.
EXTRA_SETTINGS=[x for x in EXTRA_SETTINGS if x[0] not in {'sticky_prompt','toggle_prompt','filter_prompt','sound_scheme','cursor_shadow'}]
for key,name,category,desc,path,value,on,off,as_string,restart in EXTRA_SETTINGS:
    TWEAKS.append(Tweak(key,name,category,desc,'Windows preference',False,restart,
                        'Medium' if key in {'superhidden','separate_explorer','pointer_precision','recent_items'} else 'Low',
                        'HKCU',path,value,on,off))

TW={t.key:t for t in TWEAKS}
# Snap and mouse trails are REG_SZ on some Windows versions; use correct value type.
STR_KEYS={'snap','mouse_trails'} | {x[0] for x in EXTRA_SETTINGS if x[8]}
POWER_SCHEMES={'Balanced':'381b4222-f694-41f0-9685-ff5bb260df2e','High performance':'8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c','Power saver':'a1841308-3541-4fab-bc81-f71556f20b4a'}
PRESETS={
 'Balanced':{'power':'Balanced','tweaks':['snap']},
 'Gaming':{'power':'High performance','tweaks':['game_mode','game_dvr','capture','transparency','taskbar_anim']},
 '3D / Rendering':{'power':'High performance','tweaks':['transparency','taskbar_anim','file_ext','hidden_files']},
 'Roblox Studio / Dev':{'power':'High performance','tweaks':['transparency','file_ext','hidden_files','explorer_thispc','snap']},
 'Work / Productivity':{'power':'Balanced','tweaks':['widgets','file_ext','snap','clipboard']},
 'Quiet / Battery':{'power':'Power saver','tweaks':['transparency','taskbar_anim']},
 'Focused Session':{'power':'Balanced','tweaks':['widgets','search_button','notification_center','snap']},
}

# Workloads are detected passively. ModeShift never alters another process automatically.
WORKLOADS={
 'Blender / Rendering': ('blender.exe','blender'),
 'Roblox Studio': ('robloxstudiobeta.exe','robloxstudio.exe'),
 'Video editing': ('premiere pro.exe','resolve.exe','afterfx.exe','vegaspro.exe'),
 'Game development': ('unity.exe','unrealeditor.exe','godot.exe'),
 'AI / Local models': ('ollama.exe','comfyui.exe','llama-server.exe','lmstudio.exe','koboldcpp.exe'),
 'Gaming': ('robloxplayerbeta.exe','fortniteclient-win64-shipping.exe','valorant-win64-shipping.exe'),
}

def detect_workloads(process_names):
    names={str(n).lower() for n in process_names}
    return [label for label, executables in WORKLOADS.items() if names.intersection(executables)]

def gpu_names_windows():
    # Vendor-neutral *names*, not vendor-neutral usage telemetry.
    if not on_windows():return []
    try:
        output=run(['powershell','-NoProfile','-NonInteractive','-Command',
                    '(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join "`n"'],timeout=7)
        return [s.strip() for s in output.splitlines() if s.strip()]
    except (OSError,RuntimeError,subprocess.TimeoutExpired):return []

def windows_gpu_fallback():
    """Best-effort Windows GPU engine load using OS performance counters.

    This reports the busiest GPU engine, NOT a vendor-equivalent whole-card load.
    Windows can omit performance counters or use localized counter names.
    """
    if not on_windows():
        return None
    script = r"""
    $ErrorActionPreference = 'Stop'
    $adapters = @(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name)
    $load = $null
    try {
      $samples = @(Get-Counter -Counter '\GPU Engine(*)\Utilization Percentage' -ErrorAction Stop).CounterSamples
      if ($samples.Count -gt 0) {
        $load = [Math]::Round(($samples | Measure-Object -Property CookedValue -Maximum).Maximum, 1)
      }
    } catch {}
    [pscustomobject]@{ names=$adapters; engine_peak=$load } | ConvertTo-Json -Compress -Depth 3
    """
    try:
        output=run(['powershell','-NoProfile','-NonInteractive','-Command',script],timeout=8)
        item=json.loads(output)
        names=item.get('names') or []
        if isinstance(names,str):names=[names]
        load=item.get('engine_peak')
        if load is not None:load=max(0.,min(100.,float(load)))
        return [{'name':str(name),'utilization':load,'vram_used_mib':None,
                 'vram_total_mib':None,'temp_c':None,'source':'Windows GPU engine counter'}
                for name in names if str(name).strip()] or None
    except (OSError,RuntimeError,subprocess.TimeoutExpired,ValueError,TypeError,KeyError):
        return None


def gpu_metrics():
    """Read NVIDIA telemetry, falling back to Windows adapter/engine detection."""
    exe=shutil.which('nvidia-smi')
    if not exe and os.name=='nt':
        for base in (os.environ.get('ProgramW6432',''),os.environ.get('ProgramFiles','')):
            if not base:continue
            candidate=Path(base)/'NVIDIA Corporation'/'NVSMI'/'nvidia-smi.exe'
            if candidate.is_file():exe=str(candidate);break
    if exe:
        try:
            result=run([exe,'--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu', '--format=csv,noheader,nounits'],timeout=3)
            out=[]
            def number(value):
                try:return float(value)
                except (ValueError,TypeError):return None
            for line in result.splitlines():
                parts=[v.strip() for v in line.split(',')]
                if len(parts)!=5:continue
                name,util,used,total,temp=parts
                out.append({'name':name,'utilization':number(util),'vram_used_mib':number(used),
                            'vram_total_mib':number(total),'temp_c':number(temp),'source':'NVIDIA driver'})
            if out:return out
        except (OSError,RuntimeError,subprocess.TimeoutExpired):pass
    return windows_gpu_fallback()

def system_snapshot():
    report={'sample_time':time.time(),'cpu_percent':None,'ram_percent':None,'ram_total_gib':None,'ram_available_gib':None,
            'disk_percent':None,'gpus':gpu_metrics(),'top_processes':[],'workloads':[]}
    if not psutil:return report
    try:
        report['cpu_percent']=psutil.cpu_percent(interval=None)
        mem=psutil.virtual_memory()
        report.update(ram_percent=mem.percent,ram_total_gib=round(mem.total/1024**3,2),ram_available_gib=round(mem.available/1024**3,2))
        report['disk_percent']=psutil.disk_usage(os.environ.get('SystemDrive','C:')+'\\' if os.name=='nt' else '/').percent
        procs=[]
        for proc in psutil.process_iter(['name','memory_info']):
            try:
                details=proc.info
                if details['name'] and details['memory_info']:
                    procs.append((details['memory_info'].rss,details['name']))
            except (psutil.Error,AttributeError,KeyError):continue
        report['top_processes']=[{'name':n,'ram_gib':round(m/1024**3,2)} for m,n in sorted(procs,reverse=True)[:12]]
        report['workloads']=detect_workloads(n for _,n in procs)
    except (psutil.Error,OSError):pass
    return report

def recommendations(info):
    result=[]
    if info['ram_percent'] is not None and info['ram_percent']>=85:
        result.append(('High memory pressure','Memory usage is at least 85%. Inspect the largest processes; close unnecessary apps or reduce project assets. Do not disable the pagefile.'))
    if info['ram_available_gib'] is not None and info['ram_available_gib']<3:
        result.append(('Low available RAM','Less than 3 GiB RAM is available. Heavy Blender and Studio sessions may page to disk. Save work before closing programs.'))
    gpus=info['gpus'] or []
    if any(g.get('utilization') is not None and g['utilization']>=95 for g in gpus):
        result.append(('GPU nearing capacity','High GPU utilization is normal during rendering. Avoid simultaneous GPU-heavy jobs; check VRAM, thermals, and render settings.'))
    if any(g.get('vram_total_mib') is not None and g.get('vram_used_mib') is not None and g['vram_total_mib']-g['vram_used_mib']<1024 for g in gpus):
        result.append(('GPU VRAM nearly full','Less than 1 GiB of reported VRAM remains on a GPU. Reduce scene textures, render complexity, or competing GPU workloads.'))
    if 'Roblox Studio' in info['workloads'] and 'Blender / Rendering' in info['workloads']:
        result.append(('Competing creative workloads','Blender and Roblox Studio are both running. Avoid concurrent heavy rendering and Studio playtests if responsiveness matters.'))
    if not result:result.append(('System load overview','No major pressure threshold detected in available metrics. Measure performance in each app before applying tweaks.'))
    return result

# Automatic actions deliberately affect power plan ONLY, never registry settings or processes.
# Users must opt in and leave ModeShift running. A short stable-observation window avoids
# rapid switching when application helpers briefly start or stop.
AUTOMATION_DEFAULTS={
 'enabled':False,
 'mapping':{
  'Blender / Rendering':'3D / Rendering',
  'Roblox Studio':'Roblox Studio / Dev',
  'Video editing':'3D / Rendering',
  'Game development':'Roblox Studio / Dev',
  'AI / Local models':'3D / Rendering',
  'Gaming':'Gaming',
 },
}
WORKLOAD_PRIORITY=tuple(AUTOMATION_DEFAULTS['mapping'])

def recommend_profile(workloads,mapping=None,profiles=None):
    choices=mapping if mapping is not None else AUTOMATION_DEFAULTS['mapping']
    allowed=profiles if profiles is not None else PRESETS
    for workload in WORKLOAD_PRIORITY:
        target=choices.get(workload)
        if workload in workloads and target in allowed:
            return target
    return None

class TelemetrySampler:
    """Off-UI-thread metrics. GPU driver timeouts never block Tk rendering."""
    def __init__(self,period=4):
        self.period=period
        self._lock=threading.Lock()
        self._stop=threading.Event()
        self._latest=None
        self._gpu_names=[]
        self._worker=threading.Thread(target=self._loop,name='ModeShiftTelemetry',daemon=True)
        self._worker.start()
    def _loop(self):
        self._gpu_names=gpu_names_windows()
        while not self._stop.is_set():
            try:
                snapshot=system_snapshot()
                snapshot['gpu_names']=self._gpu_names
                with self._lock:self._latest=snapshot
            except Exception as exc:log('SAMPLER ERROR '+str(exc))
            self._stop.wait(self.period)
    def latest(self):
        with self._lock:return self._latest
    def stop(self):self._stop.set()

class SnapshotConflict(RuntimeError):
    """A saved snapshot does not match the current system state."""

# Unattended work guard: advisory by design. Never kills/suspends processes or
# modifies GPU clocks. It cannot prevent OOM, driver reset, overheating or power loss.
GUARD_FILE = ROOT / 'unattended_guard.jsonl'
GUARD_DEFAULTS = {'enabled': False, 'ram_warn': 85, 'ram_critical': 94,
                  'disk_warn': 93, 'vram_warn': 92, 'log_interval_s': 60}

def assess_unattended(info, config):
    """Return actionable pressure findings; missing telemetry is NOT zero usage."""
    found=[]
    ram=info.get('ram_percent')
    if ram is None:
        found.append(('Unknown', 'RAM monitoring unavailable; no memory safety guarantee.'))
    elif ram >= config['ram_critical']:
        found.append(('Critical', f'RAM at {ram:.1f}%. Stop starting new jobs; consider reducing Blender samples/scene memory and Roblox Studio sessions.'))
    elif ram >= config['ram_warn']:
        found.append(('Warning', f'RAM at {ram:.1f}%. Avoid launching another heavy render, AI job or Studio instance.'))
    disk=info.get('disk_percent')
    if disk is not None and disk >= config['disk_warn']:
        found.append(('Warning', f'Disk {disk:.1f}% full. Exports, caches and autosaves may fail.'))
    for g in info.get('gpus') or []:
        total=g.get('vram_total_mib');used=g.get('vram_used_mib')
        if total and used is not None and 100*used/total >= config['vram_warn']:
            found.append(('Warning', f"{g.get('name','GPU')}: VRAM {100*used/total:.1f}% full. A new render may exhaust VRAM."))
    return found

def write_guard_event(path,info,findings):
    path.parent.mkdir(parents=True,exist_ok=True)
    payload={'timestamp':dt.datetime.now().astimezone().isoformat(timespec='seconds'),
             'cpu_percent':info.get('cpu_percent'),'ram_percent':info.get('ram_percent'),
             'disk_percent':info.get('disk_percent'),'gpus':info.get('gpus') or [],
             'workloads':info.get('workloads') or [], 'alerts':findings}
    with path.open('a',encoding='utf-8') as f:f.write(json.dumps(payload,ensure_ascii=False)+'\n')

class Backend:
 def __init__(self):
    self.data=read_json(STATE_FILE,{'history':[],'profiles':{},'last_profile':'','first_run':True})
    if not isinstance(self.data,dict):self.data={}
    if not isinstance(self.data.get('history'),list):self.data['history']=[]
    if not isinstance(self.data.get('profiles'),dict):self.data['profiles']={}
    if not isinstance(self.data.get('automation'),dict):self.data['automation']={}
    auto=self.data['automation']
    auto.setdefault('enabled',False)
    if not isinstance(auto.get('mapping'),dict):auto['mapping']={}
    for workload,profile in AUTOMATION_DEFAULTS['mapping'].items():auto['mapping'].setdefault(workload,profile)
    for k,v in PRESETS.items():self.data['profiles'].setdefault(k,v)
    guard=self.data.get('unattended_guard')
    if not isinstance(guard,dict):guard={}
    self.data['unattended_guard']={**GUARD_DEFAULTS,**{k:v for k,v in guard.items() if k in GUARD_DEFAULTS}}
    self.save()
 def save(self):persist(STATE_FILE,self.data)
 def current_power(self):
    if os.name!='nt':return None
    try:
        s=run(['powercfg','/getactivescheme'])
        import re
        m=re.search(r'[a-f\d]{8}-(?:[a-f\d]{4}-){3}[a-f\d]{12}',s,re.I)
        return m.group(0).lower() if m else None
    except Exception:return None
 def get_value(self,key):
    t=TW[key]
    if not winreg:return {'exists':False,'data':None,'type':None}
    root=winreg.HKEY_CURRENT_USER
    try:
        with winreg.OpenKey(root,t.path,0,winreg.KEY_READ) as k:
            val,kind=winreg.QueryValueEx(k,t.value)
            return {'exists':True,'data':val,'type':kind}
    except FileNotFoundError:return {'exists':False,'data':None,'type':None}
 def enabled(self,key):
    t=TW[key];v=self.get_value(key)
    return v['exists'] and str(v['data'])==str(t.on)
 def set_value(self,key,value):
    if not winreg:raise RuntimeError('Changes require Windows.')
    t=TW[key]
    if value is None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,t.path,0,winreg.KEY_SET_VALUE) as k:winreg.DeleteValue(k,t.value)
        except FileNotFoundError:pass
    else:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,t.path,0,winreg.KEY_SET_VALUE) as k:
            kind=winreg.REG_SZ if key in STR_KEYS else winreg.REG_DWORD
            winreg.SetValueEx(k,t.value,0,kind,str(value) if kind==winreg.REG_SZ else int(value))
 def restore_value(self,key,original):
    if not original['exists']:return self.set_value(key,None)
    t=TW[key]
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,t.path,0,winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k,t.value,0,original['type'],original['data'])
 def set_power(self,guid):
    if not on_windows():raise RuntimeError('Power plans require Windows.')
    if not guid:return
    # Do not duplicate or create unknown power schemes behind the user's back.
    try:run(['powercfg','/setactive',guid])
    except RuntimeError as exc:
        raise RuntimeError('Requested power plan is unavailable or blocked. Windows may expose only Balanced on some PCs. '+str(exc)) from exc
 def apply(self,requests,power=None,label='Custom changes'):
    """Journal intended changes *before* modifying the system.

    A crash can leave an incomplete journal, but cannot lose the original values.
    Successfully applied values are read back and stored for conflict-safe undo.
    """
    if not on_windows():raise RuntimeError('Apply is available only on Windows.')
    valid={k:bool(v) for k,v in requests.items() if k in TW}
    originals={k:self.get_value(k) for k,wanted in valid.items() if self.enabled(k)!=wanted}
    previous_power=self.current_power()
    power_requested=bool(power and power!=previous_power)
    if not originals and not power_requested:
        return {'count':0,'restart':False,'failures':[]}
    record={'time':dt.datetime.now().isoformat(timespec='seconds'),'label':label,
            'before':originals,'power_before':previous_power if power_requested else None,
            'after':{},'after_values':{},'power_after':None,'status':'pending'}
    # Save the original values before performing any writes, to survive unexpected exits.
    self.data['history'].append(record)
    self.save()
    failures=[]
    for key,prior in originals.items():
        try:
            self.set_value(key,TW[key].on if valid[key] else TW[key].off)
            record['after'][key]=valid[key]
            record['after_values'][key]=self.get_value(key)
        except Exception as exc:
            failures.append(f'{TW[key].name}: {exc}')
        finally:self.save()  # Persist progress, even if an individual setting fails.
    if power_requested:
        try:
            self.set_power(power)
            actual=self.current_power()
            if actual is None:raise RuntimeError('Could not verify active power scheme')
            record['power_after']=actual
        except Exception as exc:failures.append(f'Power plan: {exc}')
        finally:self.save()
    # Failed changes are not claimed as applied. Their originals remain in
    # the journal because the write may have partially succeeded.
    record['status']='partial' if failures else 'complete'
    self.data['history']=self.data['history'][-100:]
    self.save()
    log(f'APPLY {label}: {list(record["after"])} power={record["power_after"]} failures={failures}')
    return {'count':len(record['after'])+(1 if record['power_after'] else 0),
            'restart':any(TW[k].restart for k in record['after']),
            'failures':failures}

 def rollback(self,index=-1,force=False):
    """Never silently overwrite a value modified after a snapshot was taken."""
    snapshots=self.data['history']
    if not snapshots:raise RuntimeError('No snapshots available.')
    snap_index=index if index>=0 else len(snapshots)+index
    snap=snapshots[snap_index]
    if not force:
        if snap.get('status') in ('pending','partial'):
            raise SnapshotConflict('This operation did not finish cleanly. Review the snapshot before forcing a restore.')
        changed=[]
        expected=snap.get('after_values',{})
        for key,state in expected.items():
            if self.get_value(key)!=state:changed.append(TW[key].name if key in TW else key)
        if snap.get('power_after'):
            if self.current_power()!=snap['power_after']:changed.append('active power plan')
        if changed:
            raise SnapshotConflict('Some values changed after this snapshot:\n• '+'\n• '.join(changed))
        if 'after_values' not in snap:
            raise SnapshotConflict('This older snapshot cannot verify later changes.')
    current={k:self.get_value(k) for k in snap['before']}
    power_now=self.current_power() if snap.get('power_before') else None
    errors=[]
    # Write-ahead rollback journal, so an interrupted restore remains recoverable.
    undo={'time':dt.datetime.now().isoformat(timespec='seconds'),
          'label':'Undo: '+snap['label'],'before':current,
          'power_before':power_now,'after':{},'after_values':{},
          'power_after':None,'status':'pending'}
    self.data['history'].append(undo);self.save()
    for key,prior in snap['before'].items():
        try:
            self.restore_value(key,prior)
            undo['after_values'][key]=self.get_value(key)
        except Exception as exc:errors.append(f'{key}: {exc}')
        finally:self.save()
    if snap.get('power_before'):
        try:
            self.set_power(snap['power_before'])
            undo['power_after']=self.current_power()
        except Exception as exc:errors.append(f'Power plan: {exc}')
        finally:self.save()
    undo['status']='partial' if errors else 'complete'
    if not errors:
        # Index still addresses the original: the undo journal was appended at end.
        self.data['history'].pop(snap_index)
    self.data['history']=self.data['history'][-100:]
    self.save()
    if errors:
        log('PARTIAL RESTORE '+snap['label']+': '+'; '.join(errors))
        raise RuntimeError('Some values could not be restored. Recovery snapshot saved. '+'; '.join(errors))
    log(f'UNDO {snap["label"]}')
    return snap

class App(tk.Tk):
 def __init__(self):
    super().__init__();self.backend=Backend();self.title('ModeShift — Workstation Control')
    self.geometry('1450x920');self.minsize(1080,700);self.configure(bg=BG)
    if on_windows():
        try:
            location=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'assets'/'modeshift.ico'
            if location.is_file():self.iconbitmap(str(location))
        except (OSError,tk.TclError):pass
    self.option_add('*Font',(FONT,10));self.setup_theme();self.protocol('WM_DELETE_WINDOW',self.close_app)
    self.active='Dashboard';self.category='All';self.query='';self.scheduled={};self.current_preset=tk.StringVar(value='Balanced')
    self.telemetry=TelemetrySampler()
    self.samples=[];self.last_sample_epoch=None;self.last_guard_log=0;self.guard_last_alert='Not sampled yet'
    self.measurement_running=False;self.measurement_rows=[];self.measurement_sessions=self.load_measurements()
    self.update_release=None;self.update_busy=False;self.auto_candidate=None;self.auto_hits=0;self.auto_next_retry=0;self.auto_original_power=None;self.auto_applied_power=None;self.auto_profile=None
    self.build_shell();self.navigate('Dashboard');self.after(1000,self.tick)
    if os.name!='nt':self.after(400,lambda:messagebox.showinfo('Preview mode','This environment is not Windows. You can preview the UI, but registry and power changes only run on Windows.'))
 def setup_theme(self):
    style=ttk.Style(self)
    try:style.theme_use('clam')
    except tk.TclError:pass
    style.configure('TCombobox',fieldbackground=PANEL2,background=PANEL2,foreground=TXT,bordercolor=LINE,padding=8)
    style.map('TCombobox',fieldbackground=[('readonly',PANEL2)],foreground=[('readonly',TXT)])
    style.configure('Vertical.TScrollbar',background=PANEL2,troughcolor=BG,bordercolor=BG,arrowcolor=MUTED)
 def label(self,parent,s,size=11,fg=TXT,bold=False,**kw):
    return tk.Label(parent,text=s,font=(FONT,size,'bold' if bold else 'normal'),fg=fg,bg=parent['bg'],**kw)
 def btn(self,parent,s,command,accent=False,width=None):
    b=tk.Button(parent,text=s,command=command,bg=ACC if accent else PANEL2,fg=BG if accent else TXT,activebackground='#fbc06a' if accent else '#283a55',activeforeground=BG if accent else TXT,bd=0,relief='flat',font=(FONT,10,'bold'),cursor='hand2',padx=17,pady=11,highlightthickness=0)
    if width:b.configure(width=width)
    return b
 def clear(self,parent):
    for c in parent.winfo_children():c.destroy()
 def card(self,parent,**kw):return tk.Frame(parent,bg=PANEL,highlightbackground=LINE,highlightthickness=1,**kw)
 def build_shell(self):
    top=tk.Frame(self,bg='#080d18',height=48);top.pack(side='top',fill='x');top.pack_propagate(False)
    self.label(top,'◈  MODESHIFT',15,TXT,True).pack(side='left',padx=24)
    self.label(top,'WORKLOAD CONTROL  /  v0.5.2',9,MUTED).pack(side='left',padx=12)
    self.admin_label=self.label(top,'●  '+('Admin' if is_admin() else 'Standard user'),10,GOOD if is_admin() else MUTED)
    self.admin_label.pack(side='right',padx=24)
    body=tk.Frame(self,bg=BG);body.pack(fill='both',expand=True)
    nav=tk.Frame(body,bg='#0c1625',width=202);nav.pack(side='left',fill='y');nav.pack_propagate(False)
    self.navbuttons={}
    for i,(name,symbol) in enumerate([('Dashboard','⌂'),('Optimizations','☷'),('Presets','◈'),('Automation','⟳'),('Unattended','☾'),('Measurements','▤'),('Snapshots','↶'),('Hardware','▥'),('Settings','⚙')]):
        b=tk.Button(nav,text=f'  {symbol}    {name}',anchor='w',bg='#0c1625',fg=MUTED,activebackground=PANEL2,activeforeground=TXT,borderwidth=0,relief='flat',highlightthickness=0,font=(FONT,11),padx=12,pady=13,cursor='hand2',command=lambda n=name:self.navigate(n))
        b.pack(fill='x',padx=8,pady=(12 if i==0 else 0,0));self.navbuttons[name]=b
    self.label(nav,'LOCAL • NO SUBSCRIPTION',9,MUTED).pack(side='bottom',pady=13)
    self.content=tk.Frame(body,bg=BG);self.content.pack(side='left',fill='both',expand=True)
 def navigate(self,name):
    self.active=name
    for key,b in self.navbuttons.items():b.configure(bg=PANEL2 if key==name else '#0c1625',fg=ACC if key==name else MUTED)
    self.clear(self.content)
    head=tk.Frame(self.content,bg=BG);head.pack(fill='x',padx=32,pady=(23,15))
    self.label(head,name+('  •  '+str(len(TWEAKS))+' controls' if name=='Optimizations' else ''),23,TXT,True).pack(side='left')
    self.label(head,'Your system. Your workflows. Your control.',10,MUTED).pack(side='right',pady=10)
    page=tk.Frame(self.content,bg=BG);page.pack(fill='both',expand=True,padx=32,pady=(0,18))
    getattr(self,'page_'+name.lower())(page)
 def notice(self,parent,msg,color=MUTED):
    f=tk.Frame(parent,bg=PANEL2);f.pack(fill='x',pady=(0,12));self.label(f,msg,10,color,wraplength=1040,justify='left').pack(anchor='w',padx=15,pady=11)
 def page_dashboard(self,p):
    hero=self.card(p);hero.pack(fill='x',pady=(0,14))
    lead=tk.Frame(hero,bg=PANEL);lead.pack(side='left',fill='both',expand=True,padx=23,pady=18)
    self.label(lead,'YOUR PC. ONE CONTROL CENTER.',10,ACC,True).pack(anchor='w')
    self.label(lead,'Find your flow.',25,TXT,True).pack(anchor='w',pady=(5,6))
    self.label(lead,'Swap workloads in seconds. Every manual optimization is previewed and backed up.',10,MUTED,wraplength=670,justify='left').pack(anchor='w')
    actions=tk.Frame(hero,bg=PANEL);actions.pack(side='right',padx=22)
    self.btn(actions,'All optimizations  →',lambda:self.navigate('Optimizations')).pack(pady=6)
    self.btn(actions,'Snapshots  ↶',lambda:self.navigate('Snapshots')).pack(pady=6)
    metrics=tk.Frame(p,bg=BG);metrics.pack(fill='x',pady=(0,14));self.metric_labels={}
    for idx,name in enumerate(('CPU','Memory','Disk','GPU')):
        metrics.grid_columnconfigure(idx,weight=1,uniform='metric')
        c=self.card(metrics);c.grid(row=0,column=idx,sticky='nsew',padx=(0,10) if idx<3 else 0)
        self.label(c,name.upper()+'  /  LIVE',9,MUTED,True).pack(anchor='w',padx=18,pady=(14,3))
        v=self.label(c,'—',23,TXT,True);v.pack(anchor='w',padx=18,pady=(0,15));self.metric_labels[name]=v
    workspace=tk.Frame(p,bg=BG);workspace.pack(fill='both',expand=True)
    left=self.card(workspace);left.pack(side='left',fill='both',expand=True,padx=(0,7))
    right=self.card(workspace);right.pack(side='left',fill='both',expand=True,padx=(7,0))
    self.label(left,'QUICK MODES',10,ACC,True).pack(anchor='w',padx=18,pady=(15,3))
    self.label(left,'What are you doing?',18,TXT,True).pack(anchor='w',padx=18,pady=(0,4))
    self.label(left,'Apply a safe preset with a confirmation and restore point.',9,MUTED).pack(anchor='w',padx=18,pady=(0,8))
    modes=[('🎮','Gaming','Minimize distractions while playing'),('▣','3D / Rendering','Focus your workstation on render jobs'),
           ('⌘','Roblox Studio / Dev','Build, compile and create'),('▤','Work / Productivity','Focus, files and multitasking'),
           ('☾','Quiet / Battery','Favor efficiency and quiet operation')]
    for ico,name,description in modes:
        r=tk.Frame(left,bg=PANEL2);r.pack(fill='x',padx=14,pady=4)
        self.label(r,ico,18,ACC).pack(side='left',padx=(12,9))
        labels=tk.Frame(r,bg=PANEL2);labels.pack(side='left',fill='x',expand=True,pady=8)
        self.label(labels,name,11,TXT,True).pack(anchor='w')
        self.label(labels,description,9,MUTED).pack(anchor='w')
        self.btn(r,'Apply  →',lambda n=name:self.preview_profile(n)).pack(side='right',padx=8,pady=7)
    auto=tk.Frame(left,bg=PANEL);auto.pack(fill='x',padx=15,pady=(13,8))
    self.label(auto,'AUTO MODE',10,ACC,True).pack(anchor='w')
    self.quick_auto=tk.BooleanVar(value=bool(self.backend.data['automation']['enabled']))
    cb=tk.Checkbutton(auto,text='Detect apps and switch power plans',variable=self.quick_auto,
                      command=self.dashboard_auto_change,bg=PANEL,fg=TXT,activebackground=PANEL,
                      activeforeground=TXT,selectcolor=PANEL2,font=(FONT,11),anchor='w')
    cb.pack(anchor='w',pady=3)
    self.label(auto,'Opt-in • Power plans only • Works while ModeShift is open',9,MUTED).pack(anchor='w')
    self.btn(auto,'Configure auto rules →',lambda:self.navigate('Automation')).pack(anchor='w',pady=(7,4))
    self.btn(auto,'Unattended Dev + Rendering guard →',lambda:self.navigate('Unattended'),True).pack(anchor='w',pady=(5,6))
    self.label(right,'SYSTEM INSIGHTS',10,ACC,True).pack(anchor='w',padx=18,pady=(15,3))
    self.label(right,'Recommendations for you',17,TXT,True).pack(anchor='w',padx=18,pady=(0,12))
    self.recs_frame=tk.Frame(right,bg=PANEL);self.recs_frame.pack(fill='both',expand=True)
    self.update_recommendations()
    self.spark=tk.Canvas(p,bg=PANEL,height=86,highlightthickness=1,highlightbackground=LINE)
    self.spark.pack(fill='x',pady=(12,0));self.draw_spark()
 def dashboard_auto_change(self):
    self.autovar=self.quick_auto
    self.change_automation()
 def draw_spark(self):
    if self.active!='Dashboard' or not hasattr(self,'spark') or not self.spark.winfo_exists():return
    canvas=self.spark;canvas.delete('all')
    w=max(50,canvas.winfo_width());h=max(60,canvas.winfo_height())
    canvas.create_text(12,12,text='Live resource trends (up to 3 minutes):',anchor='w',fill=MUTED,font=(FONT,9))
    for key,color,caption in [('cpu_percent',BLUE,'CPU'),('ram_percent',ACC,'RAM'),('gpu_percent',GOOD,'GPU')]:
        vals=[(x['time'],x[key]) for x in self.samples if x.get(key) is not None]
        if len(vals)>1:
            x0=vals[0][0];range_t=max(1,vals[-1][0]-x0)
            points=[]
            for t,v in vals:
                points.extend((12+(w-24)*(t-x0)/range_t, h-10-(h-34)*min(max(v,0),100)/100))
            canvas.create_line(*points,fill=color,width=2,smooth=False)
    for i,(color,text) in enumerate([(BLUE,'CPU'),(ACC,'RAM'),(GOOD,'GPU')]):
        canvas.create_text(w-152+i*50,12,text=text,anchor='w',fill=color,font=(FONT,9,'bold'))
 def update_recommendations(self,info=None):
    if not hasattr(self,'recs_frame') or not self.recs_frame.winfo_exists():return
    self.clear(self.recs_frame)
    info=info or self.telemetry.latest() or system_snapshot()
    for title,txt in recommendations(info):
        q=tk.Frame(self.recs_frame,bg=PANEL2);q.pack(fill='x',padx=16,pady=5)
        self.label(q,title,11,TXT,True).pack(anchor='w',padx=12,pady=(8,2))
        self.label(q,txt,9,MUTED,wraplength=440,justify='left').pack(anchor='w',padx=12,pady=(0,9))
    names=', '.join(info['workloads']) or 'No recognized heavy workloads running'
    self.label(self.recs_frame,'Detected: '+names,9,GOOD,wraplength=420,justify='left').pack(anchor='w',padx=20,pady=12)
 def page_optimizations(self,p):
    top=tk.Frame(p,bg=BG);top.pack(fill='x')
    self.searchvar=tk.StringVar(value=self.query)
    entry=tk.Entry(top,textvariable=self.searchvar,bg=PANEL2,fg=TXT,insertbackground=TXT,relief='flat',font=(FONT,11),width=34)
    entry.pack(side='left',ipady=11,padx=(0,12));entry.bind('<KeyRelease>',lambda e:self.refresh_tweaks())
    self.btn(top,'Review changes',self.review_changes,True).pack(side='right')
    self.btn(top,'Clear selection',lambda:(self.scheduled.clear(),self.refresh_tweaks())).pack(side='right',padx=9)
    cats=tk.Frame(p,bg=BG);cats.pack(fill='x',pady=(13,12))
    self.label(cats,'Category',10,MUTED).pack(side='left',padx=(0,10))
    catvar=tk.StringVar(value=self.category)
    cb=ttk.Combobox(cats,textvariable=catvar,values=['All']+sorted({t.category for t in TWEAKS}),state='readonly',width=24)
    cb.pack(side='left');cb.bind('<<ComboboxSelected>>',lambda event:self.change_category(catvar.get()))
    self.label(cats,'Changes are staged until you review and confirm.',10,MUTED).pack(side='right')
    self.canvas=tk.Canvas(p,bg=BG,highlightthickness=0)
    bar=ttk.Scrollbar(p,orient='vertical',command=self.canvas.yview);self.canvas.configure(yscrollcommand=bar.set)
    bar.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True)
    self.listframe=tk.Frame(self.canvas,bg=BG);wid=self.canvas.create_window((0,0),window=self.listframe,anchor='nw')
    self.listframe.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
    self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(wid,width=e.width))
    self.canvas.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(int(-e.delta/120),'units'))
    self.refresh_tweaks()
 def change_category(self,c):self.category=c;self.navigate('Optimizations')
 def refresh_tweaks(self):
    if not hasattr(self,'listframe') or not self.listframe.winfo_exists():return
    self.query=self.searchvar.get().lower();self.clear(self.listframe)
    visible=[t for t in TWEAKS if (self.category=='All' or t.category==self.category) and self.query in (t.name+' '+t.desc+' '+t.category).lower()]
    if not visible:self.label(self.listframe,'No matching settings.',13,MUTED).pack(pady=25)
    for t in visible:
        row=self.card(self.listframe);row.pack(fill='x',pady=5)
        left=tk.Frame(row,bg=PANEL);left.pack(side='left',fill='both',expand=True,padx=15,pady=13)
        self.label(left,t.name,12,TXT,True).pack(anchor='w')
        self.label(left,t.desc,9,MUTED,wraplength=720,justify='left').pack(anchor='w',pady=(4,4))
        self.label(left,t.category+'   •   '+t.risk+' risk'+('   •   Sign-out/restart may help' if t.restart else ''),9,ACC if t.risk=='Medium' else MUTED).pack(anchor='w')
        current=self.backend.enabled(t.key)
        selected=self.scheduled.get(t.key,current)
        f=tk.Frame(row,bg=PANEL);f.pack(side='right',padx=18)
        self.label(f,'ON' if current else 'OFF',9,GOOD if current else MUTED).pack(side='left',padx=10)
        b=self.btn(f,'Enabled' if selected else 'Disabled',lambda k=t.key,v=not selected:self.set_pending(k,v))
        b.configure(bg=BLUE if selected else PANEL2);b.pack(side='left')
        if selected!=current:self.label(f,'● pending',9,ACC).pack(side='left',padx=8)
 def set_pending(self,k,v):self.scheduled[k]=v;self.refresh_tweaks()
 def preview_profile(self,name):
    d=self.backend.data['profiles'][name]
    self._preview(name,d)
 def _preview(self,name,d):
    choices={k:(k in d['tweaks']) for k in TW}
    # Presets are additive for safe behavior: only enable explicitly selected tweaks; leave all others alone.
    choices={k:True for k in d['tweaks'] if k in TW}
    desc='\n'.join('• '+TW[k].name for k in choices)
    power=d.get('power','Balanced')
    if messagebox.askyesno('Apply preset: '+name,f'Power plan: {power}\n\nThe following optimizations will be ENABLED:\n{desc or "(none)"}\n\nAll other settings remain unchanged. A rollback snapshot is created.\n\nApply now?'):
        self.execute(choices,POWER_SCHEMES.get(power),name)
 def review_changes(self):
    changes={k:v for k,v in self.scheduled.items() if self.backend.enabled(k)!=v}
    if not changes:return messagebox.showinfo('Nothing selected','Select a different toggle state first.')
    lines='\n'.join(('Enable' if v else 'Disable')+'  '+TW[k].name for k,v in changes.items())
    if messagebox.askyesno('Confirm changes',lines+'\n\nOriginal values will be saved before applying.\n\nProceed?'):
        self.execute(changes,None,'Manual selection');self.scheduled.clear()
 def execute(self,changes,power,label):
    try:
        r=self.backend.apply(changes,power,label)
        msg=f'{r["count"]} changes completed. Snapshot recorded.'
        if r['restart']:msg+='\n\nSome display or Explorer settings may require sign-out or restart to take full effect.'
        if r['failures']:msg+='\n\nNot applied:\n'+'\n'.join(r['failures'])
        messagebox.showwarning('Finished with notes',msg) if r['failures'] else messagebox.showinfo('Applied',msg)
    except Exception as e:messagebox.showerror('Could not apply',str(e));log('ERROR '+traceback.format_exc())
    self.navigate(self.active)
 def page_presets(self,p):
    self.notice(p,'Presets apply only their explicitly listed settings and selected power plan. Other settings are preserved. All changes get a rollback snapshot.')
    self.btn(p,'+ Create custom preset',lambda:self.edit_profile(None),True).pack(anchor='w',pady=8)
    cv=tk.Canvas(p,bg=BG,highlightthickness=0);sb=ttk.Scrollbar(p,command=cv.yview)
    cv.configure(yscrollcommand=sb.set);sb.pack(side='right',fill='y');cv.pack(fill='both',expand=True)
    grid=tk.Frame(cv,bg=BG);w=cv.create_window((0,0),window=grid,anchor='nw')
    grid.bind('<Configure>',lambda e:cv.configure(scrollregion=cv.bbox('all')))
    cv.bind('<Configure>',lambda e:cv.itemconfigure(w,width=e.width))
    cv.bind('<MouseWheel>',lambda e:cv.yview_scroll(int(-e.delta/120),'units'))
    for i,(name,data) in enumerate(self.backend.data['profiles'].items()):
        c=self.card(grid);c.grid(row=i//3,column=i%3,sticky='nsew',padx=7,pady=8)
        self.label(c,name,16,TXT,True).pack(anchor='w',padx=17,pady=(18,8))
        self.label(c,data.get('power','Balanced')+' power plan • '+str(len(data.get('tweaks',[])))+' settings',10,MUTED).pack(anchor='w',padx=17)
        self.label(c,', '.join(TW[k].name for k in data.get('tweaks',[]) if k in TW)[:150] or 'No registry settings',9,MUTED,wraplength=320,justify='left').pack(anchor='w',padx=17,pady=(8,12))
        bar=tk.Frame(c,bg=PANEL);bar.pack(fill='x',padx=12,pady=(0,12))
        self.btn(bar,'Apply',lambda n=name:self.preview_profile(n),True).pack(side='left',padx=4)
        self.btn(bar,'Edit',lambda n=name:self.edit_profile(n)).pack(side='left',padx=4)
        if name not in PRESETS:self.btn(bar,'Delete',lambda n=name:self.remove_profile(n)).pack(side='left',padx=4)
    for i in range(3):grid.grid_columnconfigure(i,weight=1)
 def edit_profile(self,name):
    d=self.backend.data['profiles'].get(name,{'power':'Balanced','tweaks':[]})
    win=tk.Toplevel(self);win.title('Preset editor');win.geometry('565x660');win.configure(bg=BG);win.transient(self);win.grab_set()
    self.label(win,'Create / edit preset',19,TXT,True).pack(anchor='w',padx=24,pady=(19,14))
    n=tk.StringVar(value=name or 'My workflow');en=tk.Entry(win,textvariable=n,bg=PANEL2,fg=TXT,insertbackground=TXT,relief='flat');en.pack(fill='x',padx=24,ipady=9)
    self.label(win,'Power plan',11,MUTED).pack(anchor='w',padx=24,pady=(16,5))
    power=tk.StringVar(value=d.get('power','Balanced'))
    ttk.Combobox(win,values=list(POWER_SCHEMES),textvariable=power,state='readonly').pack(fill='x',padx=24)
    self.label(win,'Settings to enable (others unchanged)',11,MUTED).pack(anchor='w',padx=24,pady=(15,6))
    area=tk.Frame(win,bg=BG);area.pack(fill='both',expand=True,padx=24)
    cv=tk.Canvas(area,bg=BG,highlightthickness=0);sb=ttk.Scrollbar(area,command=cv.yview);cv.configure(yscrollcommand=sb.set);sb.pack(side='right',fill='y');cv.pack(fill='both',expand=True)
    items=tk.Frame(cv,bg=BG);w=cv.create_window((0,0),window=items,anchor='nw');items.bind('<Configure>',lambda e:cv.configure(scrollregion=cv.bbox('all')));cv.bind('<Configure>',lambda e:cv.itemconfigure(w,width=e.width))
    vars={}
    for t in TWEAKS:
        v=tk.BooleanVar(value=t.key in d['tweaks']);vars[t.key]=v
        tk.Checkbutton(items,text=t.name,variable=v,bg=BG,fg=TXT,selectcolor=PANEL2,activebackground=BG,activeforeground=TXT,anchor='w').pack(fill='x',pady=4)
    def save():
        new=n.get().strip()
        if not new:return messagebox.showerror('Invalid','Choose a name.',parent=win)
        if name in PRESETS and new!=name:return messagebox.showerror('Built-in preset','Rename built-in presets by creating a new one.',parent=win)
        if name and name!=new:self.backend.data['profiles'].pop(name,None)
        self.backend.data['profiles'][new]={'power':power.get(),'tweaks':[k for k,v in vars.items() if v.get()]}
        self.backend.save();win.destroy();self.navigate('Presets')
    self.btn(win,'Save preset',save,True).pack(padx=24,pady=15,fill='x')
 def remove_profile(self,name):
    if messagebox.askyesno('Delete preset',f'Delete {name}?'):
        self.backend.data['profiles'].pop(name,None);self.backend.save();self.navigate('Presets')
 def page_snapshots(self,p):
    self.notice(p,'Snapshots preserve exact previous registry values and the previous active Windows power plan. Undo is itself reversible.')
    h=self.backend.data['history']
    if not h:self.label(p,'No changes yet. Apply a preset or an optimization to create your first snapshot.',12,MUTED).pack(pady=30);return
    cv=tk.Canvas(p,bg=BG,highlightthickness=0)
    sb=ttk.Scrollbar(p,orient='vertical',command=cv.yview);cv.configure(yscrollcommand=sb.set)
    sb.pack(side='right',fill='y');cv.pack(side='left',fill='both',expand=True)
    container=tk.Frame(cv,bg=BG);w=cv.create_window((0,0),window=container,anchor='nw')
    container.bind('<Configure>',lambda e:cv.configure(scrollregion=cv.bbox('all')))
    cv.bind('<Configure>',lambda e:cv.itemconfigure(w,width=e.width))
    cv.bind('<MouseWheel>',lambda e:cv.yview_scroll(int(-e.delta/120),'units'))
    for i in range(len(h)-1,-1,-1):
        s=h[i];r=self.card(container);r.pack(fill='x',pady=5)
        left=tk.Frame(r,bg=PANEL);left.pack(side='left',padx=14,pady=12)
        self.label(left,s['label'],12,TXT,True).pack(anchor='w')
        self.label(left,s['time']+'   •   '+str(len(s['before']))+' registry values'+('   •   Power plan' if s.get('power_before') else ''),9,MUTED).pack(anchor='w',pady=(4,0))
        self.btn(r,'Restore this snapshot',lambda idx=i:self.confirm_restore(idx)).pack(side='right',padx=15)
 def confirm_restore(self,i):
    if not messagebox.askyesno('Restore earlier values','Restore the original values in this snapshot?\n\nModeShift checks for newer changes before overwriting them.'):
        return
    try:
        self.backend.rollback(i)
        messagebox.showinfo('Restored','Snapshot restored. Some settings may need sign-out or restart.')
    except SnapshotConflict as exc:
        if messagebox.askyesno('Snapshot conflict',str(exc)+'\n\nForce restore and overwrite these newer values?'):
            try:
                self.backend.rollback(i,force=True)
                messagebox.showinfo('Restored','Forced restore completed. You can undo it in Snapshots.')
            except Exception as e:messagebox.showerror('Restore failed',str(e))
    except Exception as e:messagebox.showerror('Restore failed',str(e))
    self.navigate('Snapshots')

 def page_automation(self,p):
    self.notice(p,'Opt-in automatic WORKLOAD POWER PLANS. Registry tweaks never apply automatically. ModeShift must remain open; no Windows service is installed.')
    auto=self.backend.data['automation']
    head=self.card(p);head.pack(fill='x',pady=(5,14))
    self.autovar=tk.BooleanVar(value=bool(auto['enabled']))
    tk.Checkbutton(head, text='Enable automatic power-plan switching',variable=self.autovar,command=self.change_automation,
       font=(FONT,13,'bold'),bg=PANEL,fg=TXT,selectcolor=PANEL2,activebackground=PANEL,activeforeground=TXT).pack(anchor='w',padx=18,pady=(15,6))
    self.label(head,'A workload must persist for several samples. When it ends, the previous power plan is restored. On battery, High performance is not automatically enabled.',10,MUTED,wraplength=940,justify='left').pack(anchor='w',padx=20,pady=(0,14))
    detected=(self.telemetry.latest() or {}).get('workloads',[])
    profile=recommend_profile(detected,auto['mapping'],self.backend.data['profiles'])
    self.auto_status=self.label(p,'Detected: '+(', '.join(detected) if detected else 'No recognized heavy workload')+'   •   Suggested: '+(profile or 'None'),11,GOOD)
    self.auto_status.pack(anchor='w',pady=(3,12))
    mapping=self.card(p);mapping.pack(fill='x',pady=5)
    self.label(mapping,'Per-application workload rules',15,TXT,True).pack(anchor='w',padx=17,pady=(15,8))
    self.label(mapping,'A rule selects the power scheme from its target preset. It does not enable that preset’s Windows switches.',9,MUTED).pack(anchor='w',padx=17,pady=(0,12))
    for workload in WORKLOAD_PRIORITY:
        row=tk.Frame(mapping,bg=PANEL);row.pack(fill='x',padx=18,pady=4)
        self.label(row,workload,11,TXT).pack(side='left')
        selected=tk.StringVar(value=auto['mapping'].get(workload,'Disabled'))
        selector=ttk.Combobox(row,textvariable=selected,values=['Disabled']+list(self.backend.data['profiles']),state='readonly',width=27)
        selector.pack(side='right',padx=8)
        selector.bind('<<ComboboxSelected>>',lambda e,w=workload,v=selected:self.update_rule(w,v.get()))
    actions=tk.Frame(p,bg=BG);actions.pack(fill='x',pady=(17,0))
    self.btn(actions,'Preview currently suggested preset',self.preview_detected_profile,True).pack(side='left',padx=(0,8))
    self.btn(actions,'Restore previous auto power plan',self.manual_end_automation).pack(side='left')
    self.label(p,'Priority when multiple apps are detected: rendering → Roblox Studio → video editing → game development → local AI → gaming. False positives are possible; customize the mappings.',10,MUTED,wraplength=1000,justify='left').pack(anchor='w',pady=14)
 def update_rule(self,workload,profile):
    self.backend.data['automation']['mapping'][workload]=profile
    self.backend.save()
    self.auto_candidate=None;self.auto_hits=0
 def change_automation(self):
    value=self.autovar.get()
    if value and os.name!='nt':
        self.autovar.set(False)
        return messagebox.showinfo('Windows required','Automatic power switching can only run on Windows.')
    if value and not messagebox.askyesno('Enable automation','Allow ModeShift to switch Windows power plans automatically while this app is open?\n\nRegistry tweaks, process priorities and running applications will NOT be changed.'):
        self.autovar.set(False);return
    self.backend.data['automation']['enabled']=value;self.backend.save()
    if not value:self.end_auto_power()
    self.auto_candidate=None;self.auto_hits=0
 def preview_detected_profile(self):
    work=(self.telemetry.latest() or {}).get('workloads',[])
    profile=recommend_profile(work,self.backend.data['automation']['mapping'],self.backend.data['profiles'])
    if profile:self.preview_profile(profile)
    else:messagebox.showinfo('No matched workload','No recognized workload has an enabled mapping.')
 def manual_end_automation(self):
    self.end_auto_power()
    self.backend.data['automation']['enabled']=False;self.backend.save()
    self.auto_candidate=None;self.auto_hits=0
    self.navigate('Automation')
 def end_auto_power(self):
    if self.auto_original_power and self.backend.current_power()==self.auto_applied_power:
        try:
            outcome=self.backend.apply({},self.auto_original_power,'Automation: restore previous power plan')
            if outcome['failures']:log('AUTOMATION RESTORE FAILURE '+str(outcome['failures']))
        except Exception as exc:log('AUTOMATION RESTORE ERROR '+str(exc))
    self.auto_original_power=None;self.auto_applied_power=None;self.auto_profile=None
 def auto_tick(self,info):
    if not self.backend.data['automation']['enabled'] or os.name!='nt':return
    suggested=recommend_profile(info.get('workloads',[]),self.backend.data['automation']['mapping'],self.backend.data['profiles'])
    if time.time()<self.auto_next_retry:return
    if suggested!=self.auto_candidate:
        self.auto_candidate=suggested;self.auto_hits=1
    else:self.auto_hits+=1
    if self.auto_hits<3:return
    if self.auto_profile and psutil:
        try:
            battery=psutil.sensors_battery()
            active_profile=self.backend.data['profiles'].get(self.auto_profile,{})
            if battery and not battery.power_plugged and active_profile.get('power')=='High performance':
                self.end_auto_power()
                return
        except Exception:pass
    if suggested==self.auto_profile:return
    if suggested is None:
        self.end_auto_power();return
    planned=self.backend.data['profiles'].get(suggested)
    if not planned or planned.get('power') not in POWER_SCHEMES:return
    target_scheme=POWER_SCHEMES[planned['power']]
    # Stay conservative on portable Windows machines running on battery.
    if psutil:
        try:
            batt=psutil.sensors_battery()
            if batt and not batt.power_plugged and planned['power']=='High performance':return
        except Exception:pass
    original=self.backend.current_power()
    if not original:return
    if self.auto_original_power is None:self.auto_original_power=original
    try:
        r=self.backend.apply({},target_scheme,'Automation: '+suggested+' (power plan only)')
        if r['failures']:
            log('AUTOMATION FAILED '+str(r['failures']))
            self.auto_next_retry=time.time()+60
        else:
            self.auto_profile=suggested
            self.auto_applied_power=self.backend.current_power()
    except Exception as exc:
        log('AUTOMATION ERROR '+str(exc))
        self.auto_next_retry=time.time()+60

 def page_unattended(self,p):
    self.notice(p,'For unattended Claude + Blender + Roblox Studio sessions. This is an opt-in MONITOR and local event logger, not a crash-proof governor. It does not close, pause, throttle, or modify your development applications.')
    guard=self.backend.data['unattended_guard']
    box=self.card(p);box.pack(fill='x',pady=(5,13))
    self.label(box,'UNATTENDED DEV + RENDERING',17,TXT,True).pack(anchor='w',padx=18,pady=(15,6))
    self.label(box,'Leave ModeShift running to record memory, GPU/VRAM and storage pressure while Claude runs Blender or Roblox Studio.',10,MUTED,wraplength=900,justify='left').pack(anchor='w',padx=18)
    var=tk.BooleanVar(value=bool(guard['enabled']))
    tk.Checkbutton(box,text='Enable unattended resource guard and local incident log',variable=var,
        command=lambda:self.configure_guard('enabled',var.get()),font=(FONT,12,'bold'),
        bg=PANEL,fg=TXT,selectcolor=PANEL2,activebackground=PANEL,activeforeground=TXT).pack(anchor='w',padx=18,pady=(14,10))
    values=tk.Frame(box,bg=PANEL);values.pack(fill='x',padx=18,pady=(0,12))
    for text,key,choices in [('RAM warning','ram_warn',[75,80,85,90]),('RAM critical','ram_critical',[90,92,94,96]),('VRAM warning','vram_warn',[80,85,90,92,95]),('Disk warning','disk_warn',[85,90,93,95])]:
        r=tk.Frame(values,bg=PANEL);r.pack(side='left',padx=(0,16))
        self.label(r,text,9,MUTED).pack(anchor='w')
        chosen=tk.StringVar(value=str(guard[key]))
        cb=ttk.Combobox(r,values=[str(x) for x in choices],textvariable=chosen,state='readonly',width=8)
        cb.pack(anchor='w',pady=5)
        cb.bind('<<ComboboxSelected>>',lambda event,k=key,v=chosen:self.configure_guard(k,int(v.get())))
    self.guard_ui_label=self.label(box,self.guard_status(),11,GOOD if guard['enabled'] else MUTED,wraplength=900,justify='left')
    self.guard_ui_label.pack(anchor='w',padx=18,pady=(0,15))
    self.btn(p,'Open local event log folder',lambda:self.open_folder(ROOT)).pack(anchor='w',pady=6)
    guidance=self.card(p);guidance.pack(fill='x',pady=14)
    self.label(guidance,'Before leaving a long AI-assisted render unattended',14,TXT,True).pack(anchor='w',padx=16,pady=12)
    for item in ['Save the Blender project and ensure recovery/autosave is enabled.',
                 'Have Claude queue heavy jobs sequentially, not Blender render + Studio playtest + local AI inference simultaneously.',
                 'Configure Blender render device and tiles to fit available VRAM; test one render while home.',
                 'Leave adequate disk space for caches and output, and verify cooling and power settings.',
                 'This app cannot enforce Claude job concurrency; configure your Claude workflow separately.']:
        self.label(guidance,'• '+item,10,MUTED,wraplength=950,justify='left').pack(anchor='w',padx=17,pady=5)
 def configure_guard(self,key,value):
    if key=='enabled' and value and not messagebox.askyesno('Enable unattended logging?',
        'Save local system load and workload-name readings periodically while ModeShift is running?\n\nThis cannot prevent crashes or stop Claude from starting new jobs.'):
        self.navigate('Unattended');return
    self.backend.data['unattended_guard'][key]=value
    self.backend.save();self.navigate('Unattended')
 def guard_status(self):
    g=self.backend.data['unattended_guard']
    return ('ACTIVE' if g['enabled'] else 'OFF')+'  •  '+self.guard_last_alert+'  •  Log: '+str(GUARD_FILE)
 def guard_tick(self,info):
    config=self.backend.data['unattended_guard']
    if not config['enabled']:return
    findings=assess_unattended(info,config)
    self.guard_last_alert=('; '.join(level+': '+description for level,description in findings) if findings else 'No threshold exceeded')
    now=time.monotonic()
    if now-self.last_guard_log>=max(20,config['log_interval_s']):
        try:write_guard_event(GUARD_FILE,info,findings)
        except OSError as exc:log('GUARD LOG ERROR '+str(exc))
        self.last_guard_log=now
    if self.active=='Unattended' and hasattr(self,'guard_ui_label') and self.guard_ui_label.winfo_exists():
        self.guard_ui_label.configure(text=self.guard_status(),fg=BAD if findings else GOOD)

 def page_measurements(self,p):
    self.notice(p,'Compare REAL measured resource use rather than synthetic “optimization scores.” Measurements are local and do not promise FPS improvements.')
    actions=tk.Frame(p,bg=BG);actions.pack(fill='x',pady=(5,16))
    self.btn(actions,'Start recording' if not self.measurement_running else 'Stop recording',self.toggle_measurement,True).pack(side='left',padx=(0,9))
    self.btn(actions,'Export last session (CSV)',self.export_session).pack(side='left')
    self.measure_status=self.label(p,'Recording in progress' if self.measurement_running else 'Not recording',12,GOOD if self.measurement_running else MUTED)
    self.measure_status.pack(anchor='w',pady=7)
    self.label(p,'Your last two measurement sessions',16,TXT,True).pack(anchor='w',pady=(20,12))
    for i,session in enumerate(reversed(self.measurement_sessions[-2:])):
        c=self.card(p);c.pack(fill='x',pady=5)
        summary=self.summarize_session(session)
        self.label(c,f'Session {len(self.measurement_sessions)-i}  •  {summary["samples"]} readings  •  {summary["seconds"]:.0f}s',13,TXT,True).pack(anchor='w',padx=17,pady=(12,5))
        self.label(c,f'Average CPU {summary["cpu"]}    RAM {summary["ram"]}    GPU {summary["gpu"]}',11,MUTED).pack(anchor='w',padx=17,pady=(0,13))
    self.label(p,'For a fair comparison, measure the exact same Blender scene, export task or Roblox Studio test before and after a change. GPU at 100% during rendering is often expected and healthy.',10,MUTED,wraplength=920,justify='left').pack(anchor='w',pady=18)
 def summarize_session(self,session):
    values={}
    for key in ('cpu_percent','ram_percent','gpu_percent'):
        readings=[r[key] for r in session if r.get(key) is not None]
        values[key]=f'{sum(readings)/len(readings):.1f}%' if readings else 'N/A'
    return {'cpu':values['cpu_percent'],'ram':values['ram_percent'],'gpu':values['gpu_percent'],
            'samples':len(session),'seconds':session[-1]['time']-session[0]['time'] if len(session)>1 else 0}
 def toggle_measurement(self):
    if self.measurement_running:
        self.measurement_running=False
        if self.measurement_rows:
            rows=self.measurement_rows[:]
            self.measurement_sessions.append(rows)
            self.measurement_sessions=self.measurement_sessions[-10:]
            try:self.save_measurement(rows)
            except OSError as exc:messagebox.showwarning('Local save failed',str(exc))
        self.measurement_rows=[]
    else:
        self.measurement_rows=[];self.measurement_running=True
    self.navigate('Measurements')
 def save_measurement(self,rows):
    SESSION_DIR.mkdir(parents=True,exist_ok=True)
    timestamp=dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    destination=SESSION_DIR / f'measurement_{timestamp}.csv'
    self.write_measurement(destination,rows)
    return destination
 def write_measurement(self,destination,rows):
    fields=['time','cpu_percent','ram_percent','gpu_percent','available_ram_gib','workloads']
    with open(destination,'w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows:writer.writerow({k:row.get(k,'') for k in fields})
 def load_measurements(self):
    result=[]
    if not SESSION_DIR.exists():return result
    for path in sorted(SESSION_DIR.glob('measurement_*.csv'))[-10:]:
        try:
            with path.open('r',encoding='utf-8',newline='') as f:
                rows=[]
                for row in csv.DictReader(f):
                    rows.append({k:(float(v) if v else None) if k in ('time','cpu_percent','ram_percent','gpu_percent','available_ram_gib') else v for k,v in row.items()})
                if rows:result.append(rows)
        except (OSError,ValueError,csv.Error):continue
    return result
 def export_session(self):
    if not self.measurement_sessions:return messagebox.showinfo('No measurements','Record a session first.')
    path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],initialfile='modeshift-resource-session.csv')
    if not path:return
    try:
        self.write_measurement(path,self.measurement_sessions[-1])
        messagebox.showinfo('Export complete',path)
    except OSError as exc:messagebox.showerror('Export failed',str(exc))
 def close_app(self):
    self.telemetry.stop()
    self.end_auto_power()
    self.destroy()

 def page_hardware(self,p):
    self.notice(p,'Live GPU data comes from NVIDIA driver telemetry when available. Windows fallback reports the busiest GPU engine, which is not equivalent to whole-GPU utilization. Missing values are shown as unavailable.')
    info=[('Operating system',platform.platform()),('Processor',platform.processor() or 'Not reported'),('CPU threads',str(os.cpu_count() or 'Unknown')),('Computer',platform.node()),('Memory',self.memory_info()),('Python runtime',sys.version.split()[0])]
    for title,value in info:
        r=self.card(p);r.pack(fill='x',pady=4)
        self.label(r,title,11,MUTED).pack(side='left',padx=16,pady=12)
        self.label(r,value,11,TXT,True).pack(side='right',padx=16)
    self.label(p,'GPU details and peak-process view',14,TXT,True).pack(anchor='w',pady=(20,8))
    gpu=(self.telemetry.latest() or {}).get('gpus')
    detail='\n'.join(f"{g['name']}: " + (f"{g['utilization']:.0f}% " + ('peak engine' if g.get('source')=='Windows GPU engine counter' else 'GPU') if g.get('utilization') is not None else 'load unavailable') + ' | VRAM ' + (f"{g['vram_used_mib']:.0f}/{g['vram_total_mib']:.0f} MiB" if g.get('vram_total_mib') is not None and g.get('vram_used_mib') is not None else 'unavailable') + ' | Temp ' + (f"{g['temp_c']:.0f}°C" if g.get('temp_c') is not None else 'unavailable') for g in gpu) if gpu else self.gpu_name()+' (live utilization unavailable)'
    self.gpuinfo=self.label(p,detail,11,MUTED);self.gpuinfo.pack(anchor='w')
    self.processinfo=self.label(p,'Loading processes…',10,MUTED,justify='left');self.processinfo.pack(anchor='w',pady=12)
    self.after(500,self.update_process)
 def memory_info(self):
    if psutil:
        try:return f'{psutil.virtual_memory().total/(1024**3):.1f} GiB'
        except Exception:pass
    return 'Install psutil for details'
 def gpu_name(self):
    if os.name!='nt':return 'Available when running on Windows.'
    names=(self.telemetry.latest() or {}).get('gpu_names',[])
    return '; '.join(names) or 'GPU model is being identified…'
 def update_process(self):
    if self.active!='Hardware' or not hasattr(self,'processinfo') or not self.processinfo.winfo_exists():return
    processes=(self.telemetry.latest() or {}).get('top_processes') or []
    if processes:
        self.processinfo.configure(text='Most memory-intensive processes:\n'+'\n'.join(f'  {x["name"][:42]:42s}  {x["ram_gib"]:5.2f} GiB' for x in processes[:9]))
    self.after(5000,self.update_process)
 def page_settings(self,p):
    self.notice(p,'ModeShift runs locally. No accounts or telemetry uploads. Optional manual updates require a user-configured HTTPS release source.')
    for name,cmd in [('Open ModeShift data folder',lambda:self.open_folder(ROOT)),('Export presets to JSON',self.export_presets),('Import presets from JSON',self.import_presets),('Read activity log',lambda:self.open_folder(LOG_FILE.parent)),('Export diagnostics to JSON',self.export_diagnostics),('Refresh hardware / UI',lambda:self.navigate('Hardware'))]:
        self.btn(p,name,cmd).pack(anchor='w',pady=7)
    upgrade=self.card(p);upgrade.pack(fill='x',pady=(20,12))
    self.label(upgrade,'APP UPDATES  /  v'+updater.VERSION,13,ACC,True).pack(anchor='w',padx=17,pady=(14,4))
    self.label(upgrade,'Optional HTTPS release manifest. Updates are SHA-256 verified and require your approval. No background downloads.',9,MUTED,wraplength=880,justify='left').pack(anchor='w',padx=17)
    self.update_url=tk.StringVar(value=self.backend.data.get('update_manifest','https://github.com/lolipopkins/ModeShift/releases/latest/download/latest.json'))
    tk.Entry(upgrade,textvariable=self.update_url,bg=PANEL2,fg=TXT,insertbackground=TXT,relief='flat',width=82,font=(FONT,10)).pack(fill='x',padx=17,pady=(9,8),ipady=7)
    row=tk.Frame(upgrade,bg=PANEL);row.pack(anchor='w',padx=17,pady=(0,13))
    self.btn(row,'Save release URL',self.save_update_url).pack(side='left',padx=(0,8))
    self.btn(row,'Check for updates',self.check_updates).pack(side='left',padx=(0,8))
    self.update_button=self.btn(row,'Download and install',self.install_update,True)
    self.update_button.pack(side='left');self.update_button.configure(state='disabled')
    self.update_status=self.label(upgrade,'No update checked. A release URL must be configured first.',9,MUTED,wraplength=880,justify='left')
    self.update_status.pack(anchor='w',padx=17,pady=(0,13))
    self.label(p,'Permissions and compatibility',15,TXT,True).pack(anchor='w',pady=(25,8))
    self.label(p,'Registry switches shown here are per-user. Windows builds and group policies can override them. Power scheme availability varies by PC. No optimizer can promise extra FPS or solve RAM-heavy applications without workload changes or hardware upgrades.',10,MUTED,wraplength=800,justify='left').pack(anchor='w')
 def save_update_url(self):
    value=self.update_url.get().strip()
    if value:
        try:updater.safe_https(value)
        except ValueError as e:return messagebox.showerror('Invalid release URL',str(e))
    self.backend.data['update_manifest']=value;self.backend.save()
    self.update_release=None;self.update_button.configure(state='disabled')
    self.update_status.configure(text='Saved. Click Check for updates to look up available releases.')
 def _update_ui(self,status,enable=False):
    if self.active=='Settings' and hasattr(self,'update_status') and self.update_status.winfo_exists():
        self.update_status.configure(text=status)
        self.update_button.configure(state='normal' if enable else 'disabled')
 def check_updates(self):
    if self.update_busy:return
    url=self.update_url.get().strip()
    try:updater.safe_https(url)
    except ValueError as e:return messagebox.showerror('Set release URL',str(e))
    self.save_update_url();self.update_busy=True;self._update_ui('Checking trusted HTTPS manifest…')
    def job():
        try:
            release=updater.check(url)
            def finish():
                self.update_busy=False;self.update_release=release if release['available'] else None
                self._update_ui(('Update v'+release['version']+' available. '+release['notes']) if release['available'] else 'You are on the latest listed version.',release['available'])
            self.after(0,finish)
        except Exception as exc:
            self.after(0,lambda detail=str(exc):(setattr(self,'update_busy',False),self._update_ui('Update check failed: '+detail)))
    threading.Thread(target=job,daemon=True).start()
 def install_update(self):
    release=self.update_release
    if not release or self.update_busy:return
    if not getattr(sys,'frozen',False) or not on_windows():
        return messagebox.showinfo('Portable Windows EXE required','First launch the packaged ModeShift.exe on Windows. Source launches cannot self-update.')
    if not messagebox.askyesno('Confirm update','Install ModeShift '+release['version']+'?\n\nThe verified application EXE will replace your current portable EXE. Your presets and snapshots in AppData are preserved. The prior EXE will be kept as a backup.'):
        return
    self.update_busy=True;self._update_ui('Downloading and verifying update…')
    def job():
        try:
            folder=ROOT/'updates';folder.mkdir(parents=True,exist_ok=True)
            staged=updater.download_verified(release,folder/'ModeShift-update.exe')
            def install():
                try:
                    self.telemetry.stop();self.end_auto_power()
                    updater.start_replacement(sys.executable,staged,release['sha256'],folder)
                    self.destroy()
                except Exception as exc:
                    self.update_busy=False;messagebox.showerror('Installation failed',str(exc))
            self.after(0,install)
        except Exception as exc:
            self.after(0,lambda detail=str(exc):(setattr(self,'update_busy',False),self._update_ui('Update failed: '+detail,True)))
    threading.Thread(target=job,daemon=True).start()
 def export_diagnostics(self):
    path=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('JSON','*.json')],initialfile='modeshift-diagnostics.json')
    if not path:return
    report=system_snapshot()
    # Process executable names only; no paths, user files, or account details.
    report['captured_at']=dt.datetime.now().isoformat(timespec='seconds')
    try:persist(Path(path),report);messagebox.showinfo('Diagnostics exported','Saved locally: '+path)
    except OSError as e:messagebox.showerror('Export failed',str(e))
 def export_presets(self):
    path=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('JSON','*.json')],initialfile='modeshift-presets.json')
    if path: persist(Path(path),self.backend.data['profiles']);messagebox.showinfo('Export complete',path)
 def import_presets(self):
    path=filedialog.askopenfilename(filetypes=[('JSON','*.json')]);data=read_json(Path(path),None) if path else None
    if data is None:return
    if not isinstance(data,dict):return messagebox.showerror('Invalid','Expected a JSON object.')
    count=0
    for name,d in data.items():
        if isinstance(name,str) and name not in PRESETS and len(name)<=80 and isinstance(d,dict) and d.get('power') in POWER_SCHEMES and isinstance(d.get('tweaks'),list):
            self.backend.data['profiles'][name]={'power':d['power'],'tweaks':[x for x in d['tweaks'] if x in TW]};count+=1
    self.backend.save();messagebox.showinfo('Import',f'Imported {count} presets.');self.navigate('Presets')
 def open_folder(self,path):
    if os.name=='nt':os.startfile(str(path))
    else:messagebox.showinfo('Path',str(path))
 def tick(self):
    info=self.telemetry.latest()
    if info and info.get('sample_time')!=self.last_sample_epoch:
        self.last_sample_epoch=info['sample_time']
        gpu=max((g['utilization'] for g in info.get('gpus') or [] if g.get('utilization') is not None),default=None)
        point={'time':info['sample_time'],'cpu_percent':info['cpu_percent'],
               'ram_percent':info['ram_percent'],'gpu_percent':gpu,
               'available_ram_gib':info['ram_available_gib'],
               'workloads':', '.join(info.get('workloads') or [])}
        self.samples.append(point);self.samples=self.samples[-45:]
        if self.measurement_running:self.measurement_rows.append(point)
        self.auto_tick(info)
        self.guard_tick(info)
    if self.active=='Dashboard' and hasattr(self,'metric_labels') and info:
        vals={'CPU':f"{info['cpu_percent']:.0f}%" if info['cpu_percent'] is not None else '—',
              'Memory':f"{info['ram_percent']:.0f}%  |  {info['ram_total_gib']:.1f} GiB" if info['ram_percent'] is not None else '—',
              'Disk':f"{info['disk_percent']:.0f}% full" if info['disk_percent'] is not None else '—',
              'GPU':(f"{max(g['utilization'] for g in info['gpus'] if g.get('utilization') is not None):.0f}%" if any(g.get('utilization') is not None for g in info['gpus'] or []) else ('Detected · no load metric' if info['gpus'] or info.get('gpu_names') else 'Not detected'))}
        for k,l in self.metric_labels.items():
            if l.winfo_exists():l.configure(text=vals[k])
        self.update_recommendations(info)
        self.draw_spark()
    if self.active=='Automation' and hasattr(self,'auto_status') and self.auto_status.winfo_exists() and info:
        detected=info['workloads'];suggested=recommend_profile(detected,self.backend.data['automation']['mapping'],self.backend.data['profiles'])
        active='  •  Active auto profile: '+str(self.auto_profile) if self.auto_profile else ''
        self.auto_status.configure(text='Detected: '+(', '.join(detected) if detected else 'No recognized heavy workload')+'   •   Suggested: '+(suggested or 'None')+active)
    if self.active=='Measurements' and hasattr(self,'measure_status') and self.measure_status.winfo_exists():
        self.measure_status.configure(text=f'Recording: {len(self.measurement_rows)} samples' if self.measurement_running else 'Not recording')
    self.after(1000,self.tick)

if __name__=='__main__':
    try:App().mainloop()
    except Exception:log('FATAL '+traceback.format_exc());raise
