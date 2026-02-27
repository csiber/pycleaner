from flask import Flask, render_template, jsonify, request
import os
import shutil
import glob
import platform
import subprocess
import stat
import time
from pathlib import Path
import tempfile

app = Flask(__name__)

SYSTEM = platform.system()

def get_temp_dirs():
    dirs = [tempfile.gettempdir()]
    if SYSTEM == "Windows":
        dirs += [
            os.path.expandvars(r"%TEMP%"),
            os.path.expandvars(r"%TMP%"),
            os.path.expandvars(r"%LOCALAPPDATA%\Temp"),
        ]
    elif SYSTEM == "Linux":
        dirs += ["/tmp", "/var/tmp", os.path.expanduser("~/.cache")]
    elif SYSTEM == "Darwin":
        dirs += ["/tmp", "/var/folders", os.path.expanduser("~/Library/Caches")]
    return list(set(dirs))

def get_browser_cache_dirs():
    home = os.path.expanduser("~")
    dirs = []
    if SYSTEM == "Windows":
        local = os.path.expandvars("%LOCALAPPDATA%")
        dirs = [
            os.path.join(local, "Google", "Chrome", "User Data", "Default", "Cache"),
            os.path.join(local, "Google", "Chrome", "User Data", "Default", "Code Cache"),
            os.path.join(local, "Mozilla", "Firefox", "Profiles"),
            os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "Cache"),
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
    dirs = []
    if SYSTEM == "Windows":
        dirs = [
            os.path.expandvars(r"%WINDIR%\Logs"),
            os.path.expandvars(r"%WINDIR%\Temp"),
        ]
    elif SYSTEM == "Linux":
        dirs = ["/var/log"]
    elif SYSTEM == "Darwin":
        dirs = ["/var/log", os.path.expanduser("~/Library/Logs")]
    return [d for d in dirs if os.path.exists(d)]

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes/1024**2:.1f} MB"
    else:
        return f"{size_bytes/1024**3:.2f} GB"

def get_dir_size(path):
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total

def safe_remove(path):
    removed = 0
    errors = 0
    try:
        if os.path.isfile(path):
            try:
                os.chmod(path, stat.S_IWRITE)
                os.remove(path)
                removed += 1
            except (OSError, PermissionError):
                errors += 1
        elif os.path.isdir(path):
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                r, e = safe_remove(item_path)
                removed += r
                errors += e
    except (OSError, PermissionError):
        errors += 1
    return removed, errors

def clean_directory(path, delete_subdirs=False):
    removed_files = 0
    errors = 0
    freed_bytes = 0
    try:
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            try:
                size = get_dir_size(item_path) if os.path.isdir(item_path) else os.path.getsize(item_path)
                if os.path.isfile(item_path):
                    os.chmod(item_path, stat.S_IWRITE)
                    os.remove(item_path)
                    removed_files += 1
                    freed_bytes += size
                elif os.path.isdir(item_path) and delete_subdirs:
                    shutil.rmtree(item_path, ignore_errors=True)
                    removed_files += 1
                    freed_bytes += size
            except (OSError, PermissionError):
                errors += 1
    except (OSError, PermissionError):
        errors += 1
    return removed_files, errors, freed_bytes

# ---- ROUTES ----

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/scan", methods=["POST"])
def scan():
    category = request.json.get("category")
    results = {}

    if category == "temp" or category == "all":
        total = 0
        file_count = 0
        for d in get_temp_dirs():
            s = get_dir_size(d)
            total += s
            try:
                for root, dirs, files in os.walk(d):
                    file_count += len(files)
            except:
                pass
        results["temp"] = {"size": total, "size_fmt": format_size(total), "files": file_count}

    if category == "browser" or category == "all":
        total = 0
        file_count = 0
        for d in get_browser_cache_dirs():
            s = get_dir_size(d)
            total += s
            try:
                for root, dirs, files in os.walk(d):
                    file_count += len(files)
            except:
                pass
        results["browser"] = {"size": total, "size_fmt": format_size(total), "files": file_count}

    if category == "logs" or category == "all":
        total = 0
        file_count = 0
        for d in get_log_dirs():
            # Only scan .log files for safety
            try:
                for root, dirs, files in os.walk(d):
                    for f in files:
                        if f.endswith((".log", ".old", ".bak")):
                            fp = os.path.join(root, f)
                            try:
                                total += os.path.getsize(fp)
                                file_count += 1
                            except:
                                pass
            except:
                pass
        results["logs"] = {"size": total, "size_fmt": format_size(total), "files": file_count}

    if category == "trash" or category == "all":
        trash_size = 0
        trash_files = 0
        try:
            if SYSTEM == "Windows":
                # Windows Recycle Bin (approximate)
                drives = [f"{chr(d)}:\\" for d in range(65, 91) if os.path.exists(f"{chr(d)}:\\")]
                for drive in drives:
                    rb = os.path.join(drive, "$Recycle.Bin")
                    if os.path.exists(rb):
                        s = get_dir_size(rb)
                        trash_size += s
            elif SYSTEM == "Linux":
                trash = os.path.expanduser("~/.local/share/Trash/files")
                if os.path.exists(trash):
                    trash_size = get_dir_size(trash)
                    for root, dirs, files in os.walk(trash):
                        trash_files += len(files)
            elif SYSTEM == "Darwin":
                trash = os.path.expanduser("~/.Trash")
                if os.path.exists(trash):
                    trash_size = get_dir_size(trash)
                    for root, dirs, files in os.walk(trash):
                        trash_files += len(files)
        except:
            pass
        results["trash"] = {"size": trash_size, "size_fmt": format_size(trash_size), "files": trash_files}

    if category == "downloads" or category == "all":
        downloads = os.path.expanduser("~/Downloads")
        dl_size = 0
        dl_files = 0
        if os.path.exists(downloads):
            dl_size = get_dir_size(downloads)
            for f in os.listdir(downloads):
                if os.path.isfile(os.path.join(downloads, f)):
                    dl_files += 1
        results["downloads"] = {"size": dl_size, "size_fmt": format_size(dl_size), "files": dl_files}

    # Disk usage
    try:
        total_disk, used_disk, free_disk = shutil.disk_usage("/")
        results["disk"] = {
            "total": total_disk,
            "used": used_disk,
            "free": free_disk,
            "total_fmt": format_size(total_disk),
            "used_fmt": format_size(used_disk),
            "free_fmt": format_size(free_disk),
            "used_pct": round(used_disk / total_disk * 100, 1)
        }
    except:
        results["disk"] = {}

    return jsonify(results)

@app.route("/api/clean", methods=["POST"])
def clean():
    categories = request.json.get("categories", [])
    total_freed = 0
    total_files = 0
    total_errors = 0
    details = []

    if "temp" in categories:
        freed = 0
        files = 0
        for d in get_temp_dirs():
            if os.path.exists(d):
                f, e, b = clean_directory(d, delete_subdirs=True)
                files += f
                freed += b
                total_errors += e
        total_freed += freed
        total_files += files
        details.append({"category": "Ideiglenes fájlok", "files": files, "freed": format_size(freed)})

    if "browser" in categories:
        freed = 0
        files = 0
        for d in get_browser_cache_dirs():
            if os.path.exists(d):
                f, e, b = clean_directory(d, delete_subdirs=True)
                files += f
                freed += b
                total_errors += e
        total_freed += freed
        total_files += files
        details.append({"category": "Böngésző gyorsítótár", "files": files, "freed": format_size(freed)})

    if "logs" in categories:
        freed = 0
        files = 0
        for d in get_log_dirs():
            try:
                for root, dirs, log_files in os.walk(d):
                    for lf in log_files:
                        if lf.endswith((".log", ".old", ".bak")):
                            fp = os.path.join(root, lf)
                            try:
                                sz = os.path.getsize(fp)
                                os.remove(fp)
                                files += 1
                                freed += sz
                            except:
                                total_errors += 1
            except:
                pass
        total_freed += freed
        total_files += files
        details.append({"category": "Log fájlok", "files": files, "freed": format_size(freed)})

    if "trash" in categories:
        freed = 0
        files = 0
        try:
            if SYSTEM == "Linux":
                trash = os.path.expanduser("~/.local/share/Trash/files")
                if os.path.exists(trash):
                    f, e, b = clean_directory(trash, delete_subdirs=True)
                    files += f; freed += b; total_errors += e
                info = os.path.expanduser("~/.local/share/Trash/info")
                if os.path.exists(info):
                    clean_directory(info, delete_subdirs=True)
            elif SYSTEM == "Darwin":
                trash = os.path.expanduser("~/.Trash")
                if os.path.exists(trash):
                    f, e, b = clean_directory(trash, delete_subdirs=True)
                    files += f; freed += b; total_errors += e
            elif SYSTEM == "Windows":
                subprocess.run(["PowerShell", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"], 
                             capture_output=True)
                files = 1
        except:
            pass
        total_freed += freed
        total_files += files
        details.append({"category": "Lomtár", "files": files, "freed": format_size(freed)})

    return jsonify({
        "success": True,
        "total_freed": format_size(total_freed),
        "total_freed_bytes": total_freed,
        "total_files": total_files,
        "total_errors": total_errors,
        "details": details
    })

@app.route("/api/disk_usage")
def disk_usage():
    results = []
    home = os.path.expanduser("~")
    check_dirs = [
        ("Dokumentumok", os.path.join(home, "Documents")),
        ("Letöltések", os.path.join(home, "Downloads")),
        ("Képek", os.path.join(home, "Pictures")),
        ("Videók", os.path.join(home, "Videos")),
        ("Zene", os.path.join(home, "Music")),
        ("Asztal", os.path.join(home, "Desktop")),
        ("Ideiglenes", tempfile.gettempdir()),
    ]
    for name, path in check_dirs:
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
    }
    try:
        total, used, free = shutil.disk_usage("/")
        info["disk_total"] = format_size(total)
        info["disk_used"] = format_size(used)
        info["disk_free"] = format_size(free)
        info["disk_pct"] = round(used / total * 100, 1)
    except:
        pass
    return jsonify(info)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
