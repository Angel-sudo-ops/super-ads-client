import os
import sys
import requests
import tempfile
import subprocess
from tkinter import messagebox, Tk
from packaging import version

TIMEOUT = 5  # seconds for HTTP requests


def check_for_updates(current_version, version_url, download_url, app_name=None):
    try:
        latest_version = fetch_latest_version(version_url)
        if version.parse(latest_version) > version.parse(current_version):
            ask_and_update(current_version, latest_version, download_url, app_name)
    except Exception as e:
        print(f"[Updater] Update check failed: {e}")


def fetch_latest_version(version_url):
    response = requests.get(version_url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text.strip()


def ask_and_update(current_version, latest_version, download_url, app_name):
    root = Tk(); root.withdraw()
    display_name = app_name or os.path.splitext(os.path.basename(sys.executable))[0]
    answer = messagebox.askyesno(
        "Update Available",
        f"A new version ({latest_version}) of {display_name} is available.\nDo you want to update now?"
    )
    root.destroy()
    if answer:
        download_and_prepare_batch(current_version, latest_version, download_url, app_name)


def download_and_prepare_batch(current_version, latest_version, download_url, app_name):
    try:
        temp_dir = tempfile.mkdtemp()
        current_exe_path = os.path.abspath(sys.executable)
        current_dir = os.path.dirname(current_exe_path)
        current_exe_name = os.path.basename(current_exe_path)
        base_app_name = app_name or os.path.splitext(current_exe_name)[0]

        new_exe_name = f"{base_app_name}_{latest_version}.exe"
        new_exe_path = os.path.join(temp_dir, new_exe_name)

        print(f"[Updater] Downloading update to {new_exe_path}...")
        response = requests.get(download_url, timeout=TIMEOUT, stream=True)
        response.raise_for_status()
        with open(new_exe_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        old_version_name = f"{os.path.splitext(current_exe_name)[0]}_{current_version}.exe"
        batch_path = os.path.join(temp_dir, "run_updater.bat")
        with open(batch_path, 'w') as batch:
            batch.write("@echo off\n")
            batch.write("timeout /t 1 >nul\n")
            batch.write(f"cd /d \"{current_dir}\"\n")
            batch.write(f"rename \"{current_exe_name}\" \"{old_version_name}\"\n")
            batch.write(f"move \"{new_exe_path}\" \"{current_exe_name}\"\n")
            batch.write(f"start \"\" \"{current_exe_name}\"\n")
            batch.write("timeout /t 2 >nul\n")
            batch.write(f"del \"{old_version_name}\"\n")
            batch.write("cmd /c del \"%~f0\"\n")
        print("[Updater] Running updater batch...")
        subprocess.Popen([batch_path], shell=True)
        print("[Updater] Exiting current app...")
        sys.exit(0)
    except Exception as e:
        root = Tk(); root.withdraw()
        messagebox.showerror("Update Failed", f"Could not update {app_name or 'application'}:\n{e}")
        root.destroy()