"""
PyCleaner v3.0 — Teljes rendszertisztító
Funkciók: tisztítás, RAM/CPU monitor, duplikált fájlok, registry,
          ütemező, backup, profil, témaváltó, riport export
"""

from flask import Flask, render_template, jsonify, request, send_from_directory, Response
import os, shutil, platform, subprocess, stat, time, json, hashlib, zipfile
import threading, re, tempfile, sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# psutil opcionális (RAM/CPU monitorhoz)
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

app = Flask(__name__)
SYSTEM = platform.system()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "static"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "backups"), exist_ok=True)

# ── Config & Profiles ──────────────────────────────────────────────────────────

CONFIG_FILE  = os.path.join(DATA_DIR, "config.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
SCHED_FILE   = os.path.join(DATA_DIR, "schedule.json")

DEFAULT_CONFIG = {
    "theme": "dark",
    "active_profile": "default",
    "profiles": {
        "default": {
            "name": "Alapértelmezett",
            "password": "",
            "color_accent": "#00c8f0",
            "color_accent2": "#ff6b35",
            "notify_toast": True,
            "custom_dirs": [],
            "auto_backup": True,
            "backup_max_mb": 200,
        }
    }
}

def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                # merge missing keys
                for k, v in DEFAULT_CONFIG.items():
                    if k not in cfg:
                        cfg[k] = v
                return cfg
    except: pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except: pass

def get_profile():
    cfg = load_config()
    pid = cfg.get("active_profile", "default")
    return cfg.get("profiles", {}).get(pid, DEFAULT_CONFIG["profiles"]["default"])

# ── History ────────────────────────────────────────────────────────────────────

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return []

def save_history(entry):
    h = load_history(); h.insert(0, entry)
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(h[:100], f, ensure_ascii=False, indent=2)
    except: pass

# ── Scheduler (pure Python thread) ────────────────────────────────────────────

_scheduler_thread = None
_scheduler_stop   = threading.Event()

def load_schedule():
    try:
        if os.path.exists(SCHED_FILE):
            with open(SCHED_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return {"enabled": False, "interval_hours": 24, "categories": ["temp","browser","logs"], "last_run": None}

def save_schedule(s):
    try:
        with open(SCHED_FILE, 'w', encoding='utf-8') as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except: pass

def _scheduler_worker():
    while not _scheduler_stop.is_set():
        s = load_schedule()
        if s.get("enabled"):
            last = s.get("last_run")
            interval_h = s.get("interval_hours", 24)
            run_now = False
            if last is None:
                run_now = True
            else:
                try:
                    last_dt = datetime.fromisoformat(last)
                    if datetime.now() - last_dt >= timedelta(hours=interval_h):
                        run_now = True
                except: run_now = True
            if run_now:
                cats = s.get("categories", ["temp","browser","logs"])
                _do_clean(cats, 0, auto=True)
                s["last_run"] = datetime.now().isoformat()
                save_schedule(s)
        _scheduler_stop.wait(300)  # check every 5 min

def start_scheduler():
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_worker, daemon=True)
    _scheduler_thread.start()

start_scheduler()

# ── Filesystem helpers ─────────────────────────────────────────────────────────

def fmt(n):
    if n < 1024:        return f"{n} B"
    if n < 1024**2:     return f"{n/1024:.1f} KB"
    if n < 1024**3:     return f"{n/1024**2:.1f} MB"
    return f"{n/1024**3:.2f} GB"

def dir_size(path):
    total = 0
    try:
        for dp, _, fn in os.walk(path):
            for f in fn:
                try: total += os.path.getsize(os.path.join(dp, f))
                except: pass
    except: pass
    return total

def count_files(path):
    n = 0
    try:
        for _, _, fn in os.walk(path): n += len(fn)
    except: pass
    return n

def get_temp_dirs():
    d = [tempfile.gettempdir()]
    if SYSTEM == "Windows":
        d += [os.path.expandvars(r"%TEMP%"), os.path.expandvars(r"%TMP%"),
              os.path.expandvars(r"%LOCALAPPDATA%\Temp"), os.path.expandvars(r"%WINDIR%\Temp")]
    elif SYSTEM == "Linux":
        d += ["/tmp", "/var/tmp"]
    elif SYSTEM == "Darwin":
        d += ["/tmp", os.path.expanduser("~/Library/Caches")]
    return list(set([x for x in d if os.path.exists(x)]))

def get_browser_dirs():
    h = os.path.expanduser("~")
    if SYSTEM == "Windows":
        la = os.path.expandvars("%LOCALAPPDATA%")
        ra = os.path.expandvars("%APPDATA%")
        dirs = [
            os.path.join(la, "Google","Chrome","User Data","Default","Cache"),
            os.path.join(la, "Google","Chrome","User Data","Default","Code Cache"),
            os.path.join(la, "Google","Chrome","User Data","Default","GPUCache"),
            os.path.join(la, "Mozilla","Firefox","Profiles"),
            os.path.join(ra, "Mozilla","Firefox","Profiles"),
            os.path.join(la, "Microsoft","Edge","User Data","Default","Cache"),
            os.path.join(la, "Microsoft","Edge","User Data","Default","Code Cache"),
            os.path.join(la, "BraveSoftware","Brave-Browser","User Data","Default","Cache"),
        ]
    elif SYSTEM == "Linux":
        dirs = [os.path.join(h,".cache","google-chrome"), os.path.join(h,".cache","chromium"),
                os.path.join(h,".mozilla","firefox"), os.path.join(h,".cache","mozilla")]
    elif SYSTEM == "Darwin":
        lib = os.path.join(h,"Library")
        dirs = [os.path.join(lib,"Caches","Google","Chrome"), os.path.join(lib,"Caches","Firefox"),
                os.path.join(lib,"Application Support","Google","Chrome","Default","Cache")]
    else: dirs = []
    return [x for x in dirs if os.path.exists(x)]

def get_log_dirs():
    if SYSTEM == "Windows":
        d = [os.path.expandvars(r"%WINDIR%\Logs"), os.path.expandvars(r"%WINDIR%\Temp")]
    elif SYSTEM == "Linux":  d = ["/var/log"]
    elif SYSTEM == "Darwin": d = ["/var/log", os.path.expanduser("~/Library/Logs")]
    else: d = []
    return [x for x in d if os.path.exists(x)]

def get_thumb_dirs():
    if SYSTEM == "Windows":
        d = [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Explorer")]
    elif SYSTEM == "Linux":
        d = [os.path.expanduser("~/.cache/thumbnails"), os.path.expanduser("~/.thumbnails")]
    elif SYSTEM == "Darwin":
        d = [os.path.expanduser("~/Library/Caches/com.apple.QuickLookDaemon")]
    else: d = []
    return [x for x in d if os.path.exists(x)]

def clean_dir(path, subdirs=True, min_age=0):
    removed=0; errors=0; freed=0; now=time.time()
    try:
        for item in os.listdir(path):
            ip = os.path.join(path, item)
            try:
                if min_age > 0 and (now - os.path.getmtime(ip))/86400 < min_age:
                    continue
                sz = dir_size(ip) if os.path.isdir(ip) else os.path.getsize(ip)
                if os.path.isfile(ip):
                    os.chmod(ip, stat.S_IWRITE); os.remove(ip)
                    removed += 1; freed += sz
                elif os.path.isdir(ip) and subdirs:
                    shutil.rmtree(ip, ignore_errors=True)
                    removed += 1; freed += sz
            except: errors += 1
    except: errors += 1
    return removed, errors, freed

# ── Backup before clean ────────────────────────────────────────────────────────

def create_backup(categories, dirs_map):
    """Zip up to backup_max_mb worth of files before deletion."""
    profile = get_profile()
    if not profile.get("auto_backup", True):
        return None
    max_bytes = profile.get("backup_max_mb", 200) * 1024 * 1024
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BASE_DIR, "backups", f"backup_{ts}.zip")
    total_added = 0
    try:
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            for cat in categories:
                for d in dirs_map.get(cat, []):
                    if not os.path.exists(d): continue
                    try:
                        for root, _, files in os.walk(d):
                            for f in files:
                                if total_added >= max_bytes: break
                                fp = os.path.join(root, f)
                                try:
                                    sz = os.path.getsize(fp)
                                    if total_added + sz > max_bytes: continue
                                    arc_name = os.path.relpath(fp, os.path.dirname(d))
                                    zf.write(fp, os.path.join(cat, arc_name))
                                    total_added += sz
                                except: pass
                    except: pass
        return backup_path if os.path.getsize(backup_path) > 22 else None
    except:
        return None

# ── Core clean logic ───────────────────────────────────────────────────────────

def _do_clean(categories, min_age=0, auto=False):
    total_freed=0; total_files=0; total_errors=0; details=[]

    dirs_map = {
        "temp":       get_temp_dirs(),
        "browser":    get_browser_dirs(),
        "logs":       get_log_dirs(),
        "thumbnails": get_thumb_dirs(),
    }
    # Custom dirs from profile
    profile = get_profile()
    for cd in profile.get("custom_dirs", []):
        if os.path.exists(cd):
            dirs_map.setdefault("custom", []).append(cd)

    # Backup first
    backup_file = create_backup([c for c in categories if c not in ("trash",)], dirs_map)

    for cat in categories:
        freed=0; files=0; errs=0
        if cat in dirs_map:
            for d in dirs_map[cat]:
                if not os.path.exists(d): continue
                if cat == "logs":
                    try:
                        for root, _, lf in os.walk(d):
                            for f in lf:
                                if any(f.endswith(e) for e in (".log",".old",".bak",".tmp")):
                                    fp = os.path.join(root, f)
                                    try:
                                        sz=os.path.getsize(fp); os.remove(fp)
                                        files+=1; freed+=sz
                                    except: errs+=1
                    except: pass
                else:
                    f2,e2,b2 = clean_dir(d, True, min_age)
                    files+=f2; errs+=e2; freed+=b2
        elif cat == "trash":
            try:
                if SYSTEM == "Linux":
                    for tp in ["~/.local/share/Trash/files","~/.local/share/Trash/info"]:
                        tp2 = os.path.expanduser(tp)
                        if os.path.exists(tp2):
                            f2,e2,b2 = clean_dir(tp2, True)
                            files+=f2; errs+=e2; freed+=b2
                elif SYSTEM == "Darwin":
                    tp2 = os.path.expanduser("~/.Trash")
                    if os.path.exists(tp2):
                        f2,e2,b2 = clean_dir(tp2, True)
                        files+=f2; errs+=e2; freed+=b2
                elif SYSTEM == "Windows":
                    subprocess.run(["PowerShell","-Command",
                        "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                        capture_output=True, timeout=15)
                    files=1
            except: pass

        total_freed+=freed; total_files+=files; total_errors+=errs
        labels={"temp":"Ideiglenes fájlok","browser":"Böngésző cache","logs":"Log fájlok",
                "thumbnails":"Bélyegkép cache","trash":"Lomtár","custom":"Egyéni mappák"}
        details.append({"category": labels.get(cat, cat), "files": files,
                        "freed": fmt(freed), "freed_bytes": freed, "errors": errs})

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "auto": auto, "categories": categories,
        "total_freed": fmt(total_freed), "total_freed_bytes": total_freed,
        "total_files": total_files, "total_errors": total_errors,
        "details": details,
        "backup": os.path.basename(backup_file) if backup_file else None
    }
    save_history(entry)
    return entry, backup_file

# ── Registry clean (Windows) ───────────────────────────────────────────────────

def scan_registry():
    """Scan for common registry issues. Returns list of found items."""
    if SYSTEM != "Windows":
        return []
    issues = []
    try:
        import winreg
        # Check uninstall entries for missing programs
        uninstall_keys = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
        ]
        for key_path in uninstall_keys:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        try:
                            install_loc, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                            if install_loc and not os.path.exists(install_loc):
                                try:
                                    display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                except: display_name = subkey_name
                                issues.append({
                                    "type": "missing_install",
                                    "description": f"Hiányzó telepítési mappa: {display_name}",
                                    "path": f"HKLM\\{key_path}\\{subkey_name}",
                                    "detail": install_loc
                                })
                        except: pass
                        winreg.CloseKey(subkey)
                        i += 1
                    except OSError: break
                winreg.CloseKey(key)
            except: pass

        # MUI cache
        try:
            mui_path = r"SOFTWARE\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, mui_path)
            count = 0
            i = 0
            while True:
                try:
                    name, _, _ = winreg.EnumValue(key, i)
                    if name.endswith(".FriendlyAppName") or name.endswith(".ApplicationCompany"):
                        exe_path = name.rsplit(".", 1)[0]
                        if not os.path.exists(exe_path):
                            count += 1
                    i += 1
                except OSError: break
            winreg.CloseKey(key)
            if count > 0:
                issues.append({
                    "type": "mui_cache",
                    "description": f"MUI Cache: {count} elavult alkalmazásbejegyzés",
                    "path": f"HKCU\\{mui_path}",
                    "detail": f"{count} elavult bejegyzés"
                })
        except: pass

        # Recent docs
        try:
            recent_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, recent_path)
            count = 0
            i = 0
            while True:
                try: winreg.EnumValue(key, i); count += 1; i += 1
                except OSError: break
            winreg.CloseKey(key)
            if count > 20:
                issues.append({
                    "type": "recent_docs",
                    "description": f"Legutóbbi dokumentumok listája: {count} bejegyzés",
                    "path": f"HKCU\\{recent_path}",
                    "detail": f"{count} bejegyzés (ajánlott: <20)"
                })
        except: pass

        # Run at startup
        try:
            run_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_path)
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    # Extract exe path
                    exe = value.strip('"').split('"')[0].split(' ')[0]
                    if exe and not os.path.exists(exe):
                        issues.append({
                            "type": "startup_missing",
                            "description": f"Hiányzó autostart: {name}",
                            "path": f"HKCU\\{run_path}\\{name}",
                            "detail": exe
                        })
                    i += 1
                except OSError: break
            winreg.CloseKey(key)
        except: pass

    except ImportError:
        issues.append({"type":"info","description":"winreg nem elérhető (nem Windows)","path":"","detail":""})
    except Exception as e:
        issues.append({"type":"error","description":f"Hiba: {e}","path":"","detail":""})

    return issues

def clean_registry_item(item_path, item_type):
    """Clean a specific registry item."""
    if SYSTEM != "Windows":
        return False
    try:
        import winreg
        # Map path to hive
        hive_map = {
            "HKLM": winreg.HKEY_LOCAL_MACHINE,
            "HKCU": winreg.HKEY_CURRENT_USER,
        }
        parts = item_path.split("\\", 1)
        hive_key = hive_map.get(parts[0], winreg.HKEY_CURRENT_USER)
        sub_path = parts[1] if len(parts) > 1 else ""

        if item_type == "recent_docs":
            key = winreg.OpenKey(hive_key, sub_path, 0, winreg.KEY_ALL_ACCESS)
            # Delete all values
            while True:
                try:
                    name, _, _ = winreg.EnumValue(key, 0)
                    winreg.DeleteValue(key, name)
                except: break
            winreg.CloseKey(key)
            return True
        elif item_type in ("missing_install", "startup_missing"):
            # Delete the key
            parent_path = "\\".join(sub_path.split("\\")[:-1])
            key_name = sub_path.split("\\")[-1]
            parent = winreg.OpenKey(hive_key, parent_path, 0, winreg.KEY_ALL_ACCESS)
            winreg.DeleteKey(parent, key_name)
            winreg.CloseKey(parent)
            return True
        elif item_type == "mui_cache":
            key = winreg.OpenKey(hive_key, sub_path, 0, winreg.KEY_ALL_ACCESS)
            to_delete = []
            i = 0
            while True:
                try:
                    name, _, _ = winreg.EnumValue(key, i)
                    if name.endswith(".FriendlyAppName") or name.endswith(".ApplicationCompany"):
                        exe_path = name.rsplit(".", 1)[0]
                        if not os.path.exists(exe_path):
                            to_delete.append(name)
                    i += 1
                except: break
            for name in to_delete:
                try: winreg.DeleteValue(key, name)
                except: pass
            winreg.CloseKey(key)
            return True
    except Exception as e:
        print(f"Registry clean error: {e}")
    return False

# ── Duplicate finder ──────────────────────────────────────────────────────────

def find_duplicates(path, min_size_kb=10):
    min_bytes = min_size_kb * 1024
    size_map = defaultdict(list)
    try:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith('.') and
                      d not in ('node_modules','__pycache__','$Recycle.Bin',
                                'System Volume Information','Windows')]
            for f in files:
                fp = os.path.join(root, f)
                try:
                    sz = os.path.getsize(fp)
                    if sz >= min_bytes:
                        size_map[sz].append(fp)
                except: pass
    except: pass

    # Hash files that share size
    hash_map = defaultdict(list)
    for sz, paths in size_map.items():
        if len(paths) < 2: continue
        for fp in paths:
            try:
                h = hashlib.md5()
                with open(fp, 'rb') as f:
                    while chunk := f.read(65536):
                        h.update(chunk)
                hash_map[h.hexdigest()].append({"path": fp, "size": sz, "size_fmt": fmt(sz)})
            except: pass

    groups = [{"hash": h, "files": files, "wasted": fmt(files[0]["size"]*(len(files)-1)),
               "wasted_bytes": files[0]["size"]*(len(files)-1)}
              for h, files in hash_map.items() if len(files) >= 2]
    groups.sort(key=lambda x: x["wasted_bytes"], reverse=True)
    return groups[:100]

# ── Monitoring (SSE) ──────────────────────────────────────────────────────────

def generate_monitor():
    """Server-Sent Events generator for real-time CPU/RAM/disk."""
    while True:
        try:
            if HAS_PSUTIL:
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory()
                swap = psutil.swap_memory()
                try:
                    drive = os.path.splitdrive(tempfile.gettempdir())[0] or "/"
                    disk = psutil.disk_usage(drive if drive else "/")
                    disk_pct = disk.percent
                    disk_free = fmt(disk.free)
                except:
                    disk_pct = 0; disk_free = "N/A"
                # Network
                try:
                    net = psutil.net_io_counters()
                    net_sent = fmt(net.bytes_sent)
                    net_recv = fmt(net.bytes_recv)
                except:
                    net_sent = net_recv = "N/A"
                # Top processes by memory
                try:
                    procs = []
                    for p in psutil.process_iter(['pid','name','memory_percent','cpu_percent']):
                        try:
                            procs.append({
                                "pid": p.info['pid'],
                                "name": p.info['name'],
                                "mem_pct": round(p.info['memory_percent'] or 0, 1),
                                "cpu_pct": round(p.info['cpu_percent'] or 0, 1),
                            })
                        except: pass
                    procs.sort(key=lambda x: x['mem_pct'], reverse=True)
                    top_procs = procs[:8]
                except:
                    top_procs = []

                data = {
                    "cpu": cpu,
                    "ram_pct": mem.percent, "ram_used": fmt(mem.used), "ram_total": fmt(mem.total),
                    "ram_available": fmt(mem.available),
                    "swap_pct": swap.percent, "swap_used": fmt(swap.used), "swap_total": fmt(swap.total),
                    "disk_pct": disk_pct, "disk_free": disk_free,
                    "net_sent": net_sent, "net_recv": net_recv,
                    "processes": top_procs,
                    "ts": datetime.now().strftime("%H:%M:%S")
                }
            else:
                data = {"error": "psutil nem elérhető", "ts": datetime.now().strftime("%H:%M:%S")}
            yield f"data: {json.dumps(data)}\n\n"
        except GeneratorExit:
            break
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            time.sleep(2)

# ── HTML Report ───────────────────────────────────────────────────────────────

def build_html_report(history):
    total_freed = sum(e.get("total_freed_bytes", 0) for e in history)
    total_ops   = len(history)
    total_files = sum(e.get("total_files", 0) for e in history)

    rows = ""
    for e in history[:50]:
        cats = ", ".join(e.get("categories", []))
        rows += f"""<tr>
            <td>{e.get('timestamp','')}</td>
            <td>{cats}</td>
            <td>{e.get('total_freed','')}</td>
            <td>{e.get('total_files',0)}</td>
            <td>{'✅ Igen' if e.get('backup') else '—'}</td>
            <td>{'⚙️ Auto' if e.get('auto') else '👤 Manuális'}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="hu"><head><meta charset="UTF-8">
<title>PyCleaner Riport — {datetime.now().strftime('%Y-%m-%d')}</title>
<style>
  body{{font-family:monospace;background:#0a0c10;color:#c0d0e0;padding:32px;max-width:1000px;margin:0 auto}}
  h1{{color:#00c8f0;font-size:28px;margin-bottom:4px}}
  h2{{color:#ff6b35;font-size:16px;margin:24px 0 10px}}
  .stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:20px 0}}
  .stat-box{{background:#0d1117;border:1px solid #1a2535;border-radius:4px;padding:16px;text-align:center}}
  .stat-val{{font-size:24px;font-weight:bold;color:#00c8f0}}
  .stat-lbl{{font-size:11px;color:#506070;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;font-size:12px}}
  th{{background:#0d1117;color:#506070;padding:8px 12px;text-align:left;border-bottom:1px solid #1a2535;font-size:10px;text-transform:uppercase;letter-spacing:1px}}
  td{{padding:8px 12px;border-bottom:1px solid #1a2535}}
  tr:hover td{{background:#0d1117}}
  .footer{{margin-top:32px;font-size:10px;color:#506070;border-top:1px solid #1a2535;padding-top:12px}}
</style></head><body>
<h1>🧹 PyCleaner — Tisztítási Riport</h1>
<p style="color:#506070;font-size:12px">Generálva: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Rendszer: {platform.system()} {platform.release()}</p>
<h2>Összefoglaló</h2>
<div class="stats">
  <div class="stat-box"><div class="stat-val">{total_ops}</div><div class="stat-lbl">Tisztítás összesen</div></div>
  <div class="stat-box"><div class="stat-val" style="color:#5eff6e">{fmt(total_freed)}</div><div class="stat-lbl">Összes felszabadítva</div></div>
  <div class="stat-box"><div class="stat-val" style="color:#ff6b35">{total_files}</div><div class="stat-lbl">Törölt fájlok</div></div>
</div>
<h2>Előzmények</h2>
<table><thead><tr><th>Időpont</th><th>Kategóriák</th><th>Felszabadítva</th><th>Fájlok</th><th>Backup</th><th>Típus</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="footer">PyCleaner v3.0 — python {platform.python_version()} — {platform.node()}</div>
</body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path,'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/static/<path:fn>')
def static_files(fn):
    return send_from_directory(os.path.join(app.root_path,'static'), fn)

@app.route('/backups/<path:fn>')
def serve_backup(fn):
    return send_from_directory(os.path.join(BASE_DIR,'backups'), fn,
                               as_attachment=True)

@app.route('/')
def index():
    return render_template('index.html')

# ── Scan ─────────────────────────────────────────────────────────────────────

@app.route('/api/scan', methods=['POST'])
def scan():
    cat = request.json.get('category', 'all')
    res = {}

    def scan_dirs(dirs, log_only=False):
        t=0; fc=0
        for d in dirs:
            if log_only:
                try:
                    for root,_,files in os.walk(d):
                        for f in files:
                            if any(f.endswith(e) for e in (".log",".old",".bak",".tmp")):
                                try: t+=os.path.getsize(os.path.join(root,f)); fc+=1
                                except: pass
                except: pass
            else:
                t+=dir_size(d); fc+=count_files(d)
        return t, fc

    if cat in ('temp','all'):
        t,f = scan_dirs(get_temp_dirs())
        res['temp'] = {'size':t,'size_fmt':fmt(t),'files':f}
    if cat in ('browser','all'):
        t,f = scan_dirs(get_browser_dirs())
        res['browser'] = {'size':t,'size_fmt':fmt(t),'files':f}
    if cat in ('logs','all'):
        t,f = scan_dirs(get_log_dirs(), log_only=True)
        res['logs'] = {'size':t,'size_fmt':fmt(t),'files':f}
    if cat in ('thumbnails','all'):
        t,f = scan_dirs(get_thumb_dirs())
        res['thumbnails'] = {'size':t,'size_fmt':fmt(t),'files':f}

    profile = get_profile()
    custom_total = 0; custom_files = 0
    for cd in profile.get('custom_dirs', []):
        if os.path.exists(cd):
            custom_total += dir_size(cd); custom_files += count_files(cd)
    res['custom'] = {'size':custom_total,'size_fmt':fmt(custom_total),'files':custom_files}

    # Trash
    ts=0; tf=0
    try:
        if SYSTEM == "Windows":
            for drv in [f"{chr(d)}:\\" for d in range(65,91) if os.path.exists(f"{chr(d)}:\\")]:
                rb = os.path.join(drv,"$Recycle.Bin")
                if os.path.exists(rb): ts+=dir_size(rb); tf+=count_files(rb)
        elif SYSTEM == "Linux":
            tp = os.path.expanduser("~/.local/share/Trash/files")
            if os.path.exists(tp): ts=dir_size(tp); tf=count_files(tp)
        elif SYSTEM == "Darwin":
            tp = os.path.expanduser("~/.Trash")
            if os.path.exists(tp): ts=dir_size(tp); tf=count_files(tp)
    except: pass
    res['trash'] = {'size':ts,'size_fmt':fmt(ts),'files':tf}

    dl = os.path.expanduser("~/Downloads")
    dls = dir_size(dl) if os.path.exists(dl) else 0
    dlf = len([x for x in os.listdir(dl) if os.path.isfile(os.path.join(dl,x))]) if os.path.exists(dl) else 0
    res['downloads'] = {'size':dls,'size_fmt':fmt(dls),'files':dlf}

    try:
        drv = os.path.splitdrive(tempfile.gettempdir())[0] or "/"
        tot,used,free = shutil.disk_usage(drv if drv else "/")
        res['disk'] = {'total':tot,'used':used,'free':free,
                       'total_fmt':fmt(tot),'used_fmt':fmt(used),'free_fmt':fmt(free),
                       'used_pct':round(used/tot*100,1)}
    except: res['disk'] = {}

    return jsonify(res)

# ── Clean ─────────────────────────────────────────────────────────────────────

@app.route('/api/clean', methods=['POST'])
def clean():
    categories = request.json.get('categories', [])
    min_age    = request.json.get('min_age_days', 0)
    entry, backup = _do_clean(categories, min_age)
    if backup:
        entry['backup_url'] = f'/backups/{os.path.basename(backup)}'
    return jsonify(entry)

# ── Monitor SSE ────────────────────────────────────────────────────────────────

@app.route('/api/monitor')
def monitor():
    return Response(generate_monitor(),
                    mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache',
                             'X-Accel-Buffering':'no'})

# ── System info ───────────────────────────────────────────────────────────────

@app.route('/api/system_info')
def system_info():
    info = {
        'os':        f"{platform.system()} {platform.release()}",
        'machine':   platform.machine(),
        'python':    platform.python_version(),
        'hostname':  platform.node(),
        'processor': (platform.processor() or platform.machine())[:40],
        'has_psutil': HAS_PSUTIL,
    }
    try:
        drv = os.path.splitdrive(tempfile.gettempdir())[0] or "/"
        tot,used,free = shutil.disk_usage(drv if drv else "/")
        info.update({'disk_total':fmt(tot),'disk_used':fmt(used),
                     'disk_free':fmt(free),'disk_pct':round(used/tot*100,1)})
    except: pass
    return jsonify(info)

# ── Disk usage ────────────────────────────────────────────────────────────────

@app.route('/api/disk_usage')
def disk_usage():
    home = os.path.expanduser("~")
    dirs = [("Dokumentumok",os.path.join(home,"Documents")),
            ("Letöltések",  os.path.join(home,"Downloads")),
            ("Képek",       os.path.join(home,"Pictures")),
            ("Videók",      os.path.join(home,"Videos")),
            ("Zene",        os.path.join(home,"Music")),
            ("Asztal",      os.path.join(home,"Desktop")),
            ("Ideiglenes",  tempfile.gettempdir())]
    res = []
    for name, path in dirs:
        if os.path.exists(path):
            sz = dir_size(path)
            res.append({"name":name,"path":path,"size":sz,"size_fmt":fmt(sz)})
    res.sort(key=lambda x:x['size'], reverse=True)
    return jsonify(res)

# ── Large files ───────────────────────────────────────────────────────────────

@app.route('/api/large_files', methods=['POST'])
def large_files():
    path    = request.json.get('path', os.path.expanduser('~'))
    min_mb  = request.json.get('min_size_mb', 50)
    min_b   = min_mb * 1024 * 1024
    skip    = {'.git','$Recycle.Bin','System Volume Information','Windows',
               'Program Files','Program Files (x86)','node_modules','__pycache__'}
    results = []
    try:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in skip and not d.startswith('.')]
            for f in files:
                fp = os.path.join(root, f)
                try:
                    sz = os.path.getsize(fp)
                    if sz >= min_b:
                        results.append({"name":f,"path":fp,"size":sz,
                                        "size_fmt":fmt(sz),"ext":os.path.splitext(f)[1].lower()})
                except: pass
    except: pass
    results.sort(key=lambda x:x['size'], reverse=True)
    return jsonify(results[:40])

# ── Duplicates ────────────────────────────────────────────────────────────────

@app.route('/api/duplicates', methods=['POST'])
def duplicates():
    path     = request.json.get('path', os.path.expanduser('~'))
    min_size = request.json.get('min_size_kb', 10)
    groups   = find_duplicates(path, min_size)
    total_waste = sum(g['wasted_bytes'] for g in groups)
    return jsonify({'groups': groups, 'total_groups': len(groups),
                    'total_wasted': fmt(total_waste), 'total_wasted_bytes': total_waste})

@app.route('/api/delete_file', methods=['POST'])
def delete_file():
    path = request.json.get('path', '')
    try:
        if os.path.isfile(path):
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)
            return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
    return jsonify({'ok': False, 'error': 'Fájl nem található'})

# ── Registry ─────────────────────────────────────────────────────────────────

@app.route('/api/registry/scan')
def registry_scan():
    return jsonify({'issues': scan_registry(), 'system': SYSTEM})

@app.route('/api/registry/clean', methods=['POST'])
def registry_clean():
    item_path = request.json.get('path', '')
    item_type = request.json.get('type', '')
    ok = clean_registry_item(item_path, item_type)
    return jsonify({'ok': ok})

# ── Scheduler ─────────────────────────────────────────────────────────────────

@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    return jsonify(load_schedule())

@app.route('/api/schedule', methods=['POST'])
def set_schedule():
    s = request.json
    save_schedule(s)
    if s.get('enabled'):
        start_scheduler()
    return jsonify({'ok': True})

# ── Config / Profiles ─────────────────────────────────────────────────────────

@app.route('/api/config', methods=['GET'])
def get_config():
    cfg = load_config()
    # Don't expose passwords in listing
    safe = json.loads(json.dumps(cfg))
    for pid, prof in safe.get('profiles', {}).items():
        if prof.get('password'):
            prof['password'] = '***'
    return jsonify(safe)

@app.route('/api/config', methods=['POST'])
def set_config():
    data = request.json
    cfg = load_config()
    # Theme
    if 'theme' in data: cfg['theme'] = data['theme']
    # Active profile
    if 'active_profile' in data: cfg['active_profile'] = data['active_profile']
    # Profile update
    if 'profile_update' in data:
        pid = cfg.get('active_profile','default')
        if pid not in cfg['profiles']:
            cfg['profiles'][pid] = DEFAULT_CONFIG['profiles']['default'].copy()
        pu = data['profile_update']
        # Don't overwrite password with '***'
        if pu.get('password') == '***':
            del pu['password']
        cfg['profiles'][pid].update(pu)
    # New profile
    if 'new_profile' in data:
        np = data['new_profile']
        pid = re.sub(r'\W+','_', np.get('id','profile'))
        cfg['profiles'][pid] = {**DEFAULT_CONFIG['profiles']['default'], **np}
        cfg['active_profile'] = pid
    # Delete profile
    if 'delete_profile' in data:
        pid = data['delete_profile']
        if pid != 'default' and pid in cfg['profiles']:
            del cfg['profiles'][pid]
            cfg['active_profile'] = 'default'
    save_config(cfg)
    return jsonify({'ok': True})

@app.route('/api/config/verify_password', methods=['POST'])
def verify_password():
    pid = request.json.get('profile_id', load_config().get('active_profile','default'))
    pwd = request.json.get('password', '')
    cfg = load_config()
    stored = cfg.get('profiles', {}).get(pid, {}).get('password', '')
    return jsonify({'ok': (stored == '' or stored == pwd)})

# ── History ───────────────────────────────────────────────────────────────────

@app.route('/api/history')
def get_history():
    return jsonify(load_history())

@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    try:
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
    except: pass
    return jsonify({'ok': True})

# ── Export report ─────────────────────────────────────────────────────────────

@app.route('/api/export/html')
def export_html():
    html = build_html_report(load_history())
    return Response(html, mimetype='text/html',
                    headers={'Content-Disposition':
                             f'attachment; filename=pycleaner_report_{datetime.now().strftime("%Y%m%d")}.html'})

@app.route('/api/export/json')
def export_json():
    data = json.dumps({'history': load_history(),
                       'exported': datetime.now().isoformat(),
                       'system': platform.system()}, ensure_ascii=False, indent=2)
    return Response(data, mimetype='application/json',
                    headers={'Content-Disposition':
                             f'attachment; filename=pycleaner_data_{datetime.now().strftime("%Y%m%d")}.json'})

# ── Backups ───────────────────────────────────────────────────────────────────

@app.route('/api/backups')
def list_backups():
    backup_dir = os.path.join(BASE_DIR, 'backups')
    bk = []
    try:
        for f in sorted(os.listdir(backup_dir), reverse=True):
            if f.endswith('.zip'):
                fp = os.path.join(backup_dir, f)
                bk.append({'name':f,'size':fmt(os.path.getsize(fp)),
                           'url':f'/backups/{f}',
                           'date':datetime.fromtimestamp(os.path.getmtime(fp)).strftime('%Y-%m-%d %H:%M')})
    except: pass
    return jsonify(bk)

@app.route('/api/backups/delete', methods=['POST'])
def delete_backup():
    name = request.json.get('name','')
    if name and re.match(r'^backup_\d+_\d+\.zip$', name):
        try:
            os.remove(os.path.join(BASE_DIR,'backups',name))
            return jsonify({'ok':True})
        except: pass
    return jsonify({'ok':False})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
