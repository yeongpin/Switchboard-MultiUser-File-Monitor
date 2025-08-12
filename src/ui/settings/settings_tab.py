# -*- coding: utf-8 -*-
"""
Settings Tab (placeholder)

Currently shows "Work in progress" and ensures the app settings structure
exists by calling core.app_settings.ensure_settings_initialized().
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QCheckBox, QFrame

from core.app_settings import (
    ensure_settings_initialized,
    get_settings_ini_path,
    get_switchboard_auto_connect,
    set_switchboard_auto_connect,
    get_switchboard_auto_stop_muserver_on_stop_all,
    set_switchboard_auto_stop_muserver_on_stop_all,
    get_switchboard_stop_all_on_exit,
    set_switchboard_stop_all_on_exit,
    get_start_on_windows_launch,
    set_start_on_windows_launch,
)
from utils.logger import get_logger


class SettingsTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self._build_ui()
        self._init_settings_storage()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("Settings")
        title.setStyleSheet("QLabel { color: #ddd; font-size: 15px; font-weight: 600; }")
        layout.addWidget(title)

        # --- Collapsible section: General (default expanded) ---
        general_section = self._create_collapsible_section("General", expanded=True)
        self.general_content_layout: QVBoxLayout = general_section["content_layout"]
        layout.addWidget(general_section["frame"])

        # start on Windows launch (startup folder shortcut)
        self.start_on_launch_cb = QCheckBox("Start on Windows launch")
        try:
            self.start_on_launch_cb.setChecked(get_start_on_windows_launch())
        except Exception:
            self.start_on_launch_cb.setChecked(False)
        self.start_on_launch_cb.toggled.connect(lambda v: set_start_on_windows_launch(bool(v)))
        self.general_content_layout.addWidget(self.start_on_launch_cb)

        # --- Collapsible section: Switchboard (default expanded) ---
        section = self._create_collapsible_section("Switchboard", expanded=True)
        self.sb_content_layout: QVBoxLayout = section["content_layout"]
        layout.addWidget(section["frame"])

        # auto_connect_device checkbox inside content
        self.auto_connect_cb = QCheckBox("Auto connect device on startup")
        self.auto_connect_cb.setChecked(get_switchboard_auto_connect())
        self.auto_connect_cb.toggled.connect(lambda v: set_switchboard_auto_connect(bool(v)))
        self.sb_content_layout.addWidget(self.auto_connect_cb)

        # auto stop multi-user server on Stop All
        self.auto_stop_mu_cb = QCheckBox("Auto stop Multi-user server when Stop All")
        self.auto_stop_mu_cb.setChecked(get_switchboard_auto_stop_muserver_on_stop_all())
        self.auto_stop_mu_cb.toggled.connect(lambda v: set_switchboard_auto_stop_muserver_on_stop_all(bool(v)))
        self.sb_content_layout.addWidget(self.auto_stop_mu_cb)

        # stop all devices on application exit
        self.stop_all_on_exit_cb = QCheckBox("Stop all devices on exit")
        self.stop_all_on_exit_cb.setChecked(get_switchboard_stop_all_on_exit())
        self.stop_all_on_exit_cb.toggled.connect(lambda v: set_switchboard_stop_all_on_exit(bool(v)))
        self.sb_content_layout.addWidget(self.stop_all_on_exit_cb)

        # (moved start_on_launch to General section)

        # Spacer pushes footer to bottom
        layout.addStretch(1)

        # Footer: config file row + version row at absolute bottom
        footer = QVBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(6)

        cfg_row = QHBoxLayout()
        cfg_row.setContentsMargins(0, 0, 0, 0)
        cfg_row.setSpacing(8)
        self.path_label = QLabel("")
        self.path_label.setStyleSheet("QLabel { color: #b1b1b1; }")
        cfg_row.addWidget(QLabel("Config file:"))
        cfg_row.addWidget(self.path_label, 1)
        locate_btn = QPushButton("Locate")
        locate_btn.setToolTip("Open the settings file location in file explorer")
        locate_btn.clicked.connect(self._locate_settings_file)
        cfg_row.addWidget(locate_btn)
        footer.addLayout(cfg_row)

        version_row = QHBoxLayout()
        version_row.setContentsMargins(0, 0, 0, 0)
        version_row.addStretch(1)
        version_text = QLabel(f"v{self._get_version_string()}")
        version_text.setStyleSheet("QLabel { color: #888; font-size: 10px; }")
        version_row.addWidget(version_text)
        footer.addLayout(version_row)

        layout.addLayout(footer)

    def _init_settings_storage(self):
        try:
            ini_path = ensure_settings_initialized()
            self.path_label.setText(str(ini_path))
            self.logger.info(f"Settings initialized at {ini_path}")
        except Exception as exc:
            self.logger.error(f"Failed to initialize settings: {exc}")

    def _locate_settings_file(self):
        try:
            ini_path = ensure_settings_initialized()
            # Open and select the INI location cross-platform
            import platform, subprocess
            if platform.system() == "Windows":
                # Select the file in Explorer
                subprocess.run(["explorer", "/select,", str(ini_path)])
            elif platform.system() == "Darwin":
                # Reveal in Finder
                subprocess.run(["open", "-R", str(ini_path)])
            else:
                # Open the directory in Linux
                subprocess.run(["xdg-open", str(ini_path.parent)])
        except Exception as exc:
            self.logger.error(f"Failed to locate settings: {exc}")

    def _get_version_string(self) -> str:
        # Robust import like other modules
        try:
            from src import __version__  # type: ignore
            return __version__
        except Exception:
            try:
                import sys as _sys
                from pathlib import Path as _Path
                _sys.path.insert(0, str(_Path(__file__).parent.parent))
                from __init__ import __version__  # type: ignore
                return __version__
            except Exception:
                return "1.0.0"

    # --------- Collapsible section helpers (like changelog_widget) ---------
    def _create_collapsible_section(self, title: str, expanded: bool = True) -> dict:
        frame = QFrame()
        frame.setStyleSheet(
            """
            QFrame { background-color: #3d3d3d; border: none; border-radius: 4px; }
            """
        )
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(6)

        # Header
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)

        lbl = QLabel(title)
        lbl.setStyleSheet("color: #ffffff; font-weight: 600; font-size: 12px;")
        header.addWidget(lbl)
        header.addStretch(1)

        toggle_btn = QPushButton("▲" if expanded else "▼")
        toggle_btn.setFixedSize(16, 16)
        toggle_btn.setStyleSheet(
            """
            QPushButton { border: none; background: transparent; font-size: 9px; color: #666; font-weight: bold; }
            QPushButton:hover { color: #c5c5c5; }
            """
        )
        header.addWidget(toggle_btn)
        outer.addLayout(header)

        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(8)
        content_widget.setStyleSheet("QWidget { background-color: #242424; }")
        outer.addWidget(content_widget)

        # Initial state
        if expanded:
            content_widget.show()
        else:
            content_widget.hide()

        # Toggle behavior
        def on_toggle():
            if content_widget.isVisible():
                content_widget.hide()
                toggle_btn.setText("▼")
            else:
                content_widget.show()
                toggle_btn.setText("▲")

        toggle_btn.clicked.connect(on_toggle)

        return {"frame": frame, "content_widget": content_widget, "content_layout": content_layout}


