# -*- coding: utf-8 -*-
"""
Application settings initializer and helper.

This module creates a user-writable settings directory at:
  <Documents>/SwitchboardSync/settings

It ensures a placeholder INI file exists so future features can write/read
from a stable location. The default INI contains only a [switchboard]
section with a single key:

  auto_connect_device = false

Public API:
- ensure_settings_initialized() -> Path: creates directory and a default INI
- get_settings_dir() -> Path: returns the settings directory path
- get_settings_ini_path() -> Path: returns the INI file path
"""

from __future__ import annotations

from pathlib import Path
import configparser
from datetime import datetime
import os
import sys
import subprocess
from PySide6.QtCore import QTimer


def _documents_dir() -> Path:
    """Return the user's Documents directory if it exists, else the home dir."""
    home = Path.home()
    docs = home / "Documents"
    return docs if docs.exists() else home


def get_settings_dir() -> Path:
    """Return the SwitchboardSync settings directory path.

    Example: C:/Users/<name>/Documents/SwitchboardSync/settings
    """
    base = _documents_dir() / "SwitchboardSync" / "settings"
    return base


def get_settings_ini_path() -> Path:
    """Return the full path to the settings INI file."""
    return get_settings_dir() / "config.ini"


def ensure_settings_initialized() -> Path:
    """Ensure the settings directory and placeholder INI file exist.

    Returns the INI file path.
    """
    settings_dir = get_settings_dir()
    settings_dir.mkdir(parents=True, exist_ok=True)

    ini_path = get_settings_ini_path()
    if not ini_path.exists():
        _create_default_ini(ini_path)
    return ini_path


def _create_default_ini(ini_path: Path) -> None:
    """Create a minimal INI file focused on Switchboard-related settings."""
    config = configparser.ConfigParser()
    config["switchboard"] = {
        "auto_connect_device": "false",
        "auto_stop_muserver_on_stop_all": "false",
        "stop_all_devices_on_exit": "false",
        "start_on_windows_launch": "false",
    }
    with ini_path.open("w", encoding="utf-8") as fp:
        config.write(fp)


# --------- Convenience APIs for Switchboard settings ---------

def load_settings() -> configparser.ConfigParser:
    """Load and return the ConfigParser for the settings INI."""
    ensure_settings_initialized()
    parser = configparser.ConfigParser()
    parser.read(get_settings_ini_path(), encoding="utf-8")
    return parser


def get_switchboard_auto_connect() -> bool:
    """Return whether auto_connect_device is enabled."""
    cfg = load_settings()
    try:
        return cfg.getboolean("switchboard", "auto_connect_device", fallback=False)
    except Exception:
        return False


def set_switchboard_auto_connect(enabled: bool) -> None:
    """Persist the auto_connect_device flag into the INI file."""
    cfg = load_settings()
    if not cfg.has_section("switchboard"):
        cfg.add_section("switchboard")
    cfg.set("switchboard", "auto_connect_device", "true" if enabled else "false")
    with get_settings_ini_path().open("w", encoding="utf-8") as fp:
        cfg.write(fp)


def get_switchboard_auto_stop_muserver_on_stop_all() -> bool:
    """Return whether multi-user server should auto-stop on Stop All."""
    cfg = load_settings()
    try:
        return cfg.getboolean("switchboard", "auto_stop_muserver_on_stop_all", fallback=False)
    except Exception:
        return False


def set_switchboard_auto_stop_muserver_on_stop_all(enabled: bool) -> None:
    cfg = load_settings()
    if not cfg.has_section("switchboard"):
        cfg.add_section("switchboard")
    cfg.set("switchboard", "auto_stop_muserver_on_stop_all", "true" if enabled else "false")
    with get_settings_ini_path().open("w", encoding="utf-8") as fp:
        cfg.write(fp)


def get_switchboard_stop_all_on_exit() -> bool:
    """Return whether Stop All Devices on application exit is enabled."""
    cfg = load_settings()
    try:
        return cfg.getboolean("switchboard", "stop_all_devices_on_exit", fallback=False)
    except Exception:
        return False


def set_switchboard_stop_all_on_exit(enabled: bool) -> None:
    cfg = load_settings()
    if not cfg.has_section("switchboard"):
        cfg.add_section("switchboard")
    cfg.set("switchboard", "stop_all_devices_on_exit", "true" if enabled else "false")
    with get_settings_ini_path().open("w", encoding="utf-8") as fp:
        cfg.write(fp)


# ----- Windows startup management -----
def _windows_startup_dir() -> Path:
    appdata = os.getenv('APPDATA', '')
    if appdata:
        return Path(appdata) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup'
    # Fallback
    return Path.home() / 'AppData' / 'Roaming' / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup'


def _startup_shortcut_path() -> Path:
    # Shortcut name per requirement
    return _windows_startup_dir() / 'SwitchboardMultiUserMonitor.lnk'


def _app_launch_target() -> tuple[str, str, str, str]:
    """Return (target, args, working_dir, icon_path)."""
    # Project root: UnrealEngineSwitchboardSync
    root = Path(__file__).resolve().parents[2]
    icon = str((root / 'src' / 'ui' / 'multiusersync' / 'images' / 'switchboard.ico').resolve())
    if getattr(sys, 'frozen', False):
        exe = sys.executable
        return exe, '', str(Path(exe).parent), icon
    # Prefer run.bat when not frozen
    run_bat = (root / 'run.bat').resolve()
    if run_bat.exists():
        return str(run_bat), '', str(root.resolve()), icon
    # Fallback to python -m src.main
    py = sys.executable
    args = f"-m src.main"
    return py, args, str(root.resolve()), icon


def _create_shortcut_via_win32(target: str, args: str, workdir: str, icon: str, link_path: str) -> bool:
    try:
        import win32com.client  # type: ignore
        shell = win32com.client.Dispatch('WScript.Shell')
        shortcut = shell.CreateShortcut(link_path)
        shortcut.TargetPath = target
        shortcut.Arguments = args
        shortcut.WorkingDirectory = workdir
        if os.path.exists(icon):
            shortcut.IconLocation = icon
        shortcut.Save()
        return True
    except Exception:
        return False


def _create_shortcut_via_powershell(target: str, args: str, workdir: str, icon: str, link_path: str) -> bool:
    try:
        def esc(s: str) -> str:
            return s.replace('`', '``').replace('"', '\"')
        ps = (
            f"$W=New-Object -ComObject WScript.Shell;"
            f"$S=$W.CreateShortcut(\"{esc(link_path)}\");"
            f"$S.TargetPath=\"{esc(target)}\";"
            f"$S.Arguments=\"{esc(args)}\";"
            f"$S.WorkingDirectory=\"{esc(workdir)}\";"
            f"$S.IconLocation=\"{esc(icon)}\";"
            f"$S.Save()"
        )
        subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return os.path.exists(link_path)
    except Exception:
        return False


def enable_start_on_windows_launch() -> bool:
    """Create startup shortcut; returns True on success."""
    link = str(_startup_shortcut_path())
    target, args, workdir, icon = _app_launch_target()
    # Try COM first, then PowerShell fallback
    if _create_shortcut_via_win32(target, args, workdir, icon, link):
        return True
    return _create_shortcut_via_powershell(target, args, workdir, icon, link)


def disable_start_on_windows_launch() -> None:
    try:
        p = _startup_shortcut_path()
        if p.exists():
            p.unlink()
    except Exception:
        pass


def get_start_on_windows_launch() -> bool:
    try:
        return _startup_shortcut_path().exists()
    except Exception:
        return False


def set_start_on_windows_launch(enabled: bool) -> bool:
    """Persist setting and apply startup shortcut state."""
    cfg = load_settings()
    if not cfg.has_section('switchboard'):
        cfg.add_section('switchboard')
    cfg.set('switchboard', 'start_on_windows_launch', 'true' if enabled else 'false')
    with get_settings_ini_path().open('w', encoding='utf-8') as fp:
        cfg.write(fp)
    if enabled:
        return enable_start_on_windows_launch()
    disable_start_on_windows_launch()
    return True


def _attempt_connect_all_devices() -> bool:
    """Try to call Switchboard's Connect All; return True on success."""
    try:
        # Local import to avoid import cycles at module load time
        from ui.switchboard.switchboard_widget import get_current_switchboard_dialog  # type: ignore
        dialog = get_current_switchboard_dialog()
        if dialog and hasattr(dialog, 'connect_all_button_clicked'):
            # Request connect all (state=True)
            dialog.connect_all_button_clicked(True)
            return True
    except Exception:
        pass
    return False


def connect_all_devices_if_enabled(max_attempts: int = 10, interval_ms: int = 800) -> None:
    """If auto_connect_device is enabled, attempt to connect all devices.

    Will retry a few times using QTimer if Switchboard dialog is not ready yet.
    """
    if not get_switchboard_auto_connect():
        return

    attempts = {"n": 0}

    def try_once():
        if _attempt_connect_all_devices():
            return
        attempts["n"] += 1
        if attempts["n"] < max_attempts:
            QTimer.singleShot(interval_ms, try_once)

    # Start first attempt (slightly delayed to allow UI to initialize)
    QTimer.singleShot(interval_ms, try_once)


def auto_stop_muserver_after_stop_all(delay_ms: int = 800) -> None:
    """If enabled, stop the multi-user server shortly after Stop All.

    The small delay allows device stop to propagate first.
    """
    if not get_switchboard_auto_stop_muserver_on_stop_all():
        return

    def try_stop():
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog  # type: ignore
            dialog = get_current_switchboard_dialog()
            if not dialog:
                return
            # Determine if MU server is currently running via the UI button
            if hasattr(dialog, 'window') and hasattr(dialog.window, 'muserver_start_stop_button'):
                btn = dialog.window.muserver_start_stop_button
                if btn.isChecked():
                    dialog.on_muserver_start_stop_click()
        except Exception:
            pass

    QTimer.singleShot(delay_ms, try_stop)


__all__ = [
    "ensure_settings_initialized",
    "get_settings_dir",
    "get_settings_ini_path",
    "load_settings",
    "get_switchboard_auto_connect",
    "set_switchboard_auto_connect",
    "connect_all_devices_if_enabled",
    "get_switchboard_auto_stop_muserver_on_stop_all",
    "set_switchboard_auto_stop_muserver_on_stop_all",
    "auto_stop_muserver_after_stop_all",
    "get_switchboard_stop_all_on_exit",
    "set_switchboard_stop_all_on_exit",
    "get_start_on_windows_launch",
    "set_start_on_windows_launch",
    "enable_start_on_windows_launch",
    "disable_start_on_windows_launch",
]


