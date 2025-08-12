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
]


