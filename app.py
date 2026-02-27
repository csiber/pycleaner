from flask import Flask, render_template, jsonify, request, send_from_directory
import os
import shutil
import platform
import subprocess
import stat
import time
import json
from pathlib import Path
import tempfile
from datetime import datetime

app = Flask(__name__)
SYSTEM = platform.system()

# ---- Static / Favicon ----
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico', mimetype='image/vnd.microsoft.icon'
    )

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(app.root_path, 'static'), filename)

# ---- Helpers ----

def get_temp_dirs():
    dirs = [tempfile.gettempdir()]
    if SYSTEM == "Windows":
        dirs += [
            os.path.expandvars(r"%TEMP%"),
            os.path.expandvars(r"%TMP%"),
            os.path.expandvars(r"%LOCALAPPDATA%\Temp"),
            os.path.expandvars(r"%WINDIR%\Temp"),
        ]
    elif SYSTEM == "Linux":
        dirs += ["/tmp", "/var/tmp", os.path.expanduser("~/.cache/thumbnails")]
    elif SYSTEM == "Darwin":
        dirs += ["/tmp", os.path.expanduser("~/Library/Caches")]
    return list(set([d for d in dirs if os.path.exists(d)]))

def get_browser_cache_dirs():
    home = os.path.expanduser("~")
    dirs = []
    if SYSTEM == "Windows":
        local = os.path.expandvars("%LOCALAPPDATA%")
        roaming = os.path.expandvars("%APPDATA%")
        dirs = [
            os.path.join(local, "Google", "Chrome", "User Data", "Default", "Cache"),
            os.path.join(local, "Google", "Chrome", "User Data", "Default", "Code Cache"),
            os.path.join(local, "Google", "Chrome", "User Data", "Default", "GPUCache"),
            os.path.join(local, "Mozilla", "Firefox", "Profiles"),
            os.path.join(roaming, "Mozilla", "Firefox", "Profiles"),
            os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "Cache"),
            os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "Code Cache"),
            os.path.join(local, "BraveSoftware", "Brave-Browser", "User Data", "Default", "Cache"),
        ]
    elif SYSTEM == "Linux":
        dirs = [
            os.path.join(home, ".cache", "google-chrome"),
            os.path.join(home, ".cache", "chromium"),
            os.path.join(home, ".mozilla", "firefox"),
            os.path.join(home, ".cache", "mozilla"),
        ]
    elif SYSTEM == "Darwin":
        lib = os.path.join(home, "Library")
        dirs = [
            os.path.join(lib, "Caches", "Google", "Chrome"),
            os.path.join(lib, "Caches", "Firefox"),
            os.path.join(lib, "Application Support", "Google", "Chrome", "Default", "Cache"),
        ]
    return [d for d in dirs if os.path.exists(d)]

def get_log_dirs():
    if SYSTEM == "Windows":
        dirs = [os.path.expandvars(r"%WINDIR%\Logs"), os.path.expandvars(r"%WINDIR%\Temp")]
    elif SYSTEM == "Linux":
        dirs = ["/var/log"]
    elif SYSTEM == "Darwin":
        dirs = ["/var/log", os.path.expanduser("~/Library/Logs")]
    else:
        dirs = []
    return [d for d in dirs if os.path.exists(d)]

def get_thumbnail_dirs():
    if SYSTEM == "Windows":
        dirs = [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Explorer")]
    elif SYSTEM == "Linux":
        dirs = [os.path.expanduser("~/.cache/thumbnails"), os.path.expanduser("~/.thumbnails")]
    elif SYSTEM == "Darwin":
        dirs = [os.path.expanduser("~/Library/Caches/com.apple.QuickLookDaemon")]
    else:
        dirs = []
    return [d for d in dirs if os.path.exists(d)]

def format_size(n):
    if n < 1024: return f"{n} B"
    if n < 1024**2: return f"{n/1024:.1f} KB"
    if n < 1024**3: return f"{n/1024**2:.1f} MB"
    return f"{n/1024**3:.2f} GB"

def get_dir_size(path):
    total = 0
    try:
        for dp, dn, fn in os.walk(path):
            for f in fn:
                try: total += os.path.getsize(os.path.join(dp, f))
                except: pass
    except: pass
    return total

def count_files(path):
    count = 0
    try:
        for dp, dn, fn in os.walk(path):
            count += len(fn)
    except: pass
    return count

def clean_directory(path, delete_subdirs=False, min_age_days=0):
    removed = 0; errors = 0; freed = 0
    now = time.time()
    try:
        for item in os.listdir(path):
            ip = os.path.join(path, item)
            try:
                if min_age_days > 0:
                    if (now - os.path.getmtime(ip)) / 86400 < min_age_days:
                        continue
                size = get_dir_size(ip) if os.path.isdir(ip) else os.path.getsize(ip)
                if os.path.isfile(ip):
                    os.chmod(ip, stat.S_IWRITE)
                    os.remove(ip)
                    removed += 1; freed += size
                elif os.path.isdir(ip) and delete_subdirs:
                    shutil.rmtree(ip, ignore_errors=True)
                    removed += 1; freed += size
            except: errors += 1
    except: errors += 1
    return removed, errors, freed

# ---- History ----
HISTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clean_history.json")

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return []

def save_history(entry):
    history = load_history()
    history.insert(0, entry)
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history[:50], f, ensure_ascii=False, indent=2)
    except: pass

# ---- ROUTES ----

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/scan", methods=["POST"])
def scan():
    cat = request.json.get("category", "all")
    results = {}

    def scan_dirs(dirs, log_only=False, log_exts=None):
        total = 0; fc = 0
        for d in dirs:
            if log_only and log_exts:
                try:
                    for root, _, files in os.walk(d):
                        for f in files:
                            if any(f.endswith(e) for e in log_exts):
                                try:
                                    total += os.path.getsize(os.path.join(root, f))
                                    fc += 1
                                except: pass
                except: pass
            else:
                total += get_dir_size(d); fc += count_files(d)
        return total, fc

    if cat in ("temp", "all"):
        t, f = scan_dirs(get_temp_dirs())
        results["temp"] = {"size": t, "size_fmt": format_size(t), "files": f}

    if cat in ("browser", "all"):
        t, f = scan_dirs(get_browser_cache_dirs())
        results["browser"] = {"size": t, "size_fmt": format_size(t), "files": f}

    if cat in ("logs", "all"):
        t, f = scan_dirs(get_log_dirs(), log_only=True, log_exts=(".log", ".old", ".bak", ".tmp"))
        results["logs"] = {"size": t, "size_fmt": format_size(t), "files": f}

    if cat in ("thumbnails", "all"):
        t, f = scan_dirs(get_thumbnail_dirs())
        results["thumbnails"] = {"size": t, "size_fmt": format_size(t), "files": f}

    if cat in ("trash", "all"):
        trash_size = 0; trash_files = 0
        try:
            if SYSTEM == "Windows":
                for drive in [f"{chr(d)}:\\" for d in range(65, 91) if os.path.exists(f"{chr(d)}:\\")]:
                    rb = os.path.join(drive, "$Recycle.Bin")
                    if os.path.exists(rb):
                        trash_size += get_dir_size(rb)
                        trash_files += count_files(rb)
            elif SYSTEM == "Linux":
                tp = os.path.expanduser("~/.local/share/Trash/files")
                if os.path.exists(tp):
                    trash_size = get_dir_size(tp); trash_files = count_files(tp)
            elif SYSTEM == "Darwin":
                tp = os.path.expanduser("~/.Trash")
                if os.path.exists(tp):
                    trash_size = get_dir_size(tp); trash_files = count_files(tp)
        except: pass
        results["trash"] = {"size": trash_size, "size_fmt": format_size(trash_size), "files": trash_files}

    if cat in ("downloads", "all"):
        dl = os.path.expanduser("~/Downloads")
        t = get_dir_size(dl) if os.path.exists(dl) else 0
        f = len([x for x in os.listdir(dl) if os.path.isfile(os.path.join(dl, x))]) if os.path.exists(dl) else 0
        results["downloads"] = {"size": t, "size_fmt": format_size(t), "files": f}

    try:
        drive = os.path.splitdrive(tempfile.gettempdir())[0] or "/"
        total_d, used_d, free_d = shutil.disk_usage(drive if drive else "/")
        results["disk"] = {
            "total": total_d, "used": used_d, "free": free_d,
            "total_fmt": format_size(total_d), "used_fmt": format_size(used_d),
            "free_fmt": format_size(free_d), "used_pct": round(used_d / total_d * 100, 1)
        }
    except: results["disk"] = {}

    return jsonify(results)

@app.route("/api/clean", methods=["POST"])
def clean():
    categories = request.json.get("categories", [])
    min_age = request.json.get("min_age_days", 0)
    total_freed = 0; total_files = 0; total_errors = 0; details = []

    def do_clean(dirs, subdirs=True, log_exts=None):
        freed = 0; files = 0; errs = 0
        for d in dirs:
            if not os.path.exists(d): continue
            if log_exts:
                try:
                    for root, _, lf in os.walk(d):
                        for f in lf:
                            if any(f.endswith(e) for e in log_exts):
                                fp = os.path.join(root, f)
                                try:
                                    sz = os.path.getsize(fp); os.remove(fp)
                                    files += 1; freed += sz
                                except: errs += 1
                except: pass
            else:
                f2, e2, b2 = clean_directory(d, subdirs, min_age)
                files += f2; errs += e2; freed += b2
        return files, errs, freed

    if "temp" in categories:
        f, e, b = do_clean(get_temp_dirs())
        total_files += f; total_errors += e; total_freed += b
        details.append({"category": "Ideiglenes fájlok", "files": f, "freed": format_size(b)})

    if "browser" in categories:
        f, e, b = do_clean(get_browser_cache_dirs())
        total_files += f; total_errors += e; total_freed += b
        details.append({"category": "Böngésző gyorsítótár", "files": f, "freed": format_size(b)})

    if "logs" in categories:
        f, e, b = do_clean(get_log_dirs(), log_exts=(".log", ".old", ".bak", ".tmp"))
        total_files += f; total_errors += e; total_freed += b
        details.append({"category": "Log fájlok", "files": f, "freed": format_size(b)})

    if "thumbnails" in categories:
        f, e, b = do_clean(get_thumbnail_dirs())
        total_files += f; total_errors += e; total_freed += b
        details.append({"category": "Bélyegkép cache", "files": f, "freed": format_size(b)})

    if "trash" in categories:
        f = 0; b = 0
        try:
            if SYSTEM == "Linux":
                for tp in ["~/.local/share/Trash/files", "~/.local/share/Trash/info"]:
                    tp2 = os.path.expanduser(tp)
                    if os.path.exists(tp2):
                        f2, e2, b2 = clean_directory(tp2, True)
                        f += f2; total_errors += e2; b += b2
            elif SYSTEM == "Darwin":
                tp2 = os.path.expanduser("~/.Trash")
                if os.path.exists(tp2):
                    f2, e2, b2 = clean_directory(tp2, True)
                    f += f2; total_errors += e2; b += b2
            elif SYSTEM == "Windows":
                subprocess.run(["PowerShell", "-Command",
                    "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                    capture_output=True, timeout=15)
                f = 1
        except: pass
        total_files += f; total_freed += b
        details.append({"category": "Lomtár", "files": f, "freed": format_size(b)})

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "categories": categories,
        "total_freed": format_size(total_freed),
        "total_freed_bytes": total_freed,
        "total_files": total_files,
        "total_errors": total_errors,
        "details": details
    }
    save_history(entry)

    return jsonify({"success": True, "total_freed": format_size(total_freed),
                    "total_freed_bytes": total_freed, "total_files": total_files,
                    "total_errors": total_errors, "details": details})

@app.route("/api/disk_usage")
def disk_usage():
    home = os.path.expanduser("~")
    dirs = [
        ("Dokumentumok", os.path.join(home, "Documents")),
        ("Letöltések", os.path.join(home, "Downloads")),
        ("Képek", os.path.join(home, "Pictures")),
        ("Videók", os.path.join(home, "Videos")),
        ("Zene", os.path.join(home, "Music")),
        ("Asztal", os.path.join(home, "Desktop")),
        ("Ideiglenes", tempfile.gettempdir()),
    ]
    results = []
    for name, path in dirs:
        if os.path.exists(path):
            size = get_dir_size(path)
            results.append({"name": name, "path": path, "size": size, "size_fmt": format_size(size)})
    results.sort(key=lambda x: x["size"], reverse=True)
    return jsonify(results)

@app.route("/api/system_info")
def system_info():
    info = {
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "python": platform.python_version(),
        "hostname": platform.node(),
        "processor": platform.processor() or platform.machine(),
    }
    try:
        drive = os.path.splitdrive(tempfile.gettempdir())[0] or "/"
        total, used, free = shutil.disk_usage(drive if drive else "/")
        info.update({"disk_total": format_size(total), "disk_used": format_size(used),
                     "disk_free": format_size(free), "disk_pct": round(used / total * 100, 1)})
    except: pass
    return jsonify(info)

@app.route("/api/history")
def get_history():
    return jsonify(load_history())

@app.route("/api/history/clear", methods=["POST"])
def clear_history():
    try:
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
    except: pass
    return jsonify({"ok": True})

@app.route("/api/large_files", methods=["POST"])
def large_files():
    path = request.json.get("path", os.path.expanduser("~"))
    min_mb = request.json.get("min_size_mb", 50)
    min_bytes = min_mb * 1024 * 1024
    results = []
    skip_dirs = {'.git', '$Recycle.Bin', 'System Volume Information', 'Windows', 'Program Files',
                 'Program Files (x86)', 'node_modules', '__pycache__'}
    try:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
            for f in files:
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                    if size >= min_bytes:
                        results.append({"name": f, "path": fp, "size": size,
                                        "size_fmt": format_size(size),
                                        "ext": os.path.splitext(f)[1].lower()})
                except: pass
    except: pass
    results.sort(key=lambda x: x["size"], reverse=True)
    return jsonify(results[:40])

if __name__ == "__main__":
    app.run(debug=True, port=5000)
