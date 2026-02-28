"""
PyCleaner v4.0 — Önálló indító
Ez a fájl kezeli az exe-ből való indítást:
  - Megkeresi a szabad portot
  - Megnyitja a böngészőt
  - Elindítja a Flask szervert
"""

import sys
import os
import socket
import threading
import webbrowser
import time

# PyInstaller _MEIPASS: kicsomagolt fájlok helye futáskor
if getattr(sys, 'frozen', False):
    # Futtatható exe-ből indítva
    BASE_DIR = sys._MEIPASS
    # Az adatfájlokat (config, history) az exe mellé írjuk
    DATA_BASE = os.path.dirname(sys.executable)
else:
    # Normál python futtatás
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_BASE = BASE_DIR

# Beállítjuk a Flask template és static könyvtárakat
os.environ['PYCLEANER_BASE'] = BASE_DIR
os.environ['PYCLEANER_DATA'] = DATA_BASE

def find_free_port(start=5000, end=5100):
    """Keres egy szabad portot."""
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return 5000

def open_browser(port, delay=1.5):
    """Vár egy kicsit, majd megnyitja a böngészőt."""
    time.sleep(delay)
    webbrowser.open(f'http://127.0.0.1:{port}')

def main():
    port = find_free_port()
    url  = f'http://127.0.0.1:{port}'

    print(f"""
  ██████╗ ██╗   ██╗ ██████╗██╗     ███████╗ █████╗ ███╗   ██╗███████╗██████╗
  ██╔══██╗╚██╗ ██╔╝██╔════╝██║     ██╔════╝██╔══██╗████╗  ██║██╔════╝██╔══██╗
  ██████╔╝ ╚████╔╝ ██║     ██║     █████╗  ███████║██╔██╗ ██║█████╗  ██████╔╝
  ██╔═══╝   ╚██╔╝  ██║     ██║     ██╔══╝  ██╔══██║██║╚██╗██║██╔══╝  ██╔══██╗
  ██║        ██║   ╚██████╗███████╗███████╗██║  ██║██║ ╚████║███████╗██║  ██║
  ╚═╝        ╚═╝    ╚═════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝
                                                                    v4.0

  Szerver indítása: {url}
  Adatok helye:     {DATA_BASE}
  Leállítás:        Ctrl+C vagy használd a Kilépés gombot a felületen
    """)

    # Böngésző megnyitása háttérszálon
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    # Flask importálása és indítása
    # (ide kell az import, hogy a frozen env beállítások érvényesüljenek)
    from app import app
    app.run(
        host='127.0.0.1',
        port=port,
        debug=False,        # exe-ben SOHA ne legyen True
        use_reloader=False, # exe-ben le kell tiltani
        threaded=True,
    )

if __name__ == '__main__':
    main()
