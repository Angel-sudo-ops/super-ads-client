import os
import sys
import requests
import subprocess
from tkinter import messagebox, Tk
from packaging import version
import threading
import time

TIMEOUT = 5  # seconds for HTTP requests

def check_for_updates_async(root, current_version, version_url, download_url, app_name=None):
    def worker():
        try:
            display_name = app_name or get_app_display_name()
            latest_version = fetch_latest_version(version_url)
            if version.parse(latest_version) > version.parse(current_version):
                # Messagebox must run in the main thread
                root.after(0, lambda: ask_and_update(root, current_version, latest_version, download_url, display_name))
        except Exception as e:
            print(f"[Updater] Update check failed: {e}")

    threading.Thread(target=worker, daemon=True).start()


def fetch_with_retries(url, retries=3, delay=1, stream=False):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=TIMEOUT, stream=stream)
            response.raise_for_status()
            return response
        except Exception as e:
            action = "download" if stream else "fetch version"
            print(f"[Updater] Failed to {action} (attempt {attempt + 1} of {retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise
            
def fetch_latest_version(version_url):
    response = fetch_with_retries(version_url)
    return response.text.strip()


def ask_and_update(root, current_version, latest_version, download_url, app_name):
    def ask():
        answer = messagebox.askyesno(
            "Update Available",
            f"A new version ({latest_version}) of {app_name} is available.\nDo you want to update now?",
            parent=root
        )
        if answer:
            if root:
                root.destroy()
            download_and_prepare_batch(current_version, latest_version, download_url, app_name)
            sys.exit(0)

    root.after(0, ask)


def download_and_prepare_batch(current_version, latest_version, download_url, app_name):
    try:
        if getattr(sys, 'frozen', False):
            # Running as a PyInstaller .exe
            current_exe_path = os.path.abspath(sys.executable)
        else:
            # Running as a .py file (script), fallback to main script
            current_exe_path = os.path.abspath(sys.argv[0])

        current_dir = os.path.dirname(current_exe_path)
        current_exe_name = os.path.basename(current_exe_path)
        # base_app_name = app_name or os.path.splitext(current_exe_name)[0]

        new_exe_name = f"{app_name}_{latest_version}.exe"
        new_exe_path = os.path.join(current_dir, new_exe_name)

        print(f"[Updater] Downloading update to {new_exe_path}...")

        response = fetch_with_retries(download_url, stream=True)

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        with open(new_exe_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        percent = int(downloaded * 100 / total_size)
                        bar_length = 30
                        filled_length = int(bar_length * percent // 100)
                        bar = "#" * filled_length + "-" * (bar_length - filled_length)
                        print(f"\rDownloading... [{bar}] {percent:3d}%", end="", flush=True)

        print("\n[Updater] Download complete.")

        old_version_name = f"{os.path.splitext(current_exe_name)[0]}_{current_version}.exe"
        batch_path = os.path.join(current_dir, "run_updater.bat")

        with open(batch_path, 'w', encoding='utf-8') as batch:
            batch.write("@echo off\n")
            batch.write("title Application Updater\n")
            batch.write("cls\n")
            batch.write("echo ==============================\n")
            batch.write(f"echo Updating {app_name}\n")
            batch.write("echo ==============================\n\n")

            # Show swap progress
            batch.write("echo Swapping applications...\n")
            batch.write("timeout /t 1 >nul\n")
            batch.write(f"rename \"{current_exe_name}\" \"{old_version_name}\"\n")
            batch.write(f"move \"{new_exe_name}\" \"{current_exe_name}\"\n")

            # Start new exe
            batch.write("echo Launching new version...\n")
            batch.write(f"start \"\" \"{current_exe_name}\" --updated\n")

            # Clean up
            batch.write("timeout /t 1 >nul\n")
            batch.write("echo Cleaning old files...\n")
            batch.write(f"del \"{old_version_name}\" >nul 2>&1\n")

            # Done message with auto-close
            batch.write("echo Update complete!\n")
            batch.write("echo This window will close automatically in 3 seconds...\n")
            batch.write("timeout /t 3 >nul\n")

            # Self-delete
            batch.write("del \"%~f0\" >nul 2>&1\n")

        print("[Updater] Running updater batch...")

        subprocess.Popen(["cmd.exe", "/c", batch_path])

    except Exception as e:
        if os.path.exists(new_exe_path):
            try:
                os.remove(new_exe_path)
            except Exception:
                pass
        temp_root = Tk()
        temp_root.withdraw()
        messagebox.showerror("Update Failed", f"Could not update {app_name or 'application'}:\n{e}")
        temp_root.destroy()

def get_app_display_name(app_name=None):
    if app_name:
        return app_name  # if manually provided

    if getattr(sys, 'frozen', False):
        # Running as .exe
        base_name = os.path.basename(sys.executable)
    else:
        # Running as script
        base_name = os.path.basename(sys.argv[0])

    display_name = os.path.splitext(base_name)[0]
    return display_name



def get_app_version():
    """Read version.txt whether running from source or PyInstaller .exe."""
    if hasattr(sys, '_MEIPASS'):  
        # Running from PyInstaller bundle
        base_path = sys._MEIPASS
    else:
        # Running from source - use current working directory
        base_path = os.getcwd()

    version_file = os.path.join(base_path, "version.txt")
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "Unknown"