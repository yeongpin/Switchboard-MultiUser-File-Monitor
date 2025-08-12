# -*- coding: utf-8 -*-
"""
Switchboard Listener Tab

Launches SwitchboardListener.exe in background and streams its log file into
an in-app logger with syntax highlighting (same style as switchboard_new_tab).
On app close, attempts to terminate the launched listener process.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QCheckBox, QTextEdit
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor

from utils.logger import get_logger


class _LogHighlighter(QSyntaxHighlighter):
    """Colors log lines based on severity keywords."""
    def __init__(self, parent_doc):
        super().__init__(parent_doc)
        self.fmt_info = QTextCharFormat(); self.fmt_info.setForeground(QColor('#B1B1B1'))
        self.fmt_warning = QTextCharFormat(); self.fmt_warning.setForeground(QColor('#FFD166'))
        self.fmt_error = QTextCharFormat(); self.fmt_error.setForeground(QColor('#FF6B6B'))
        self.fmt_success = QTextCharFormat(); self.fmt_success.setForeground(QColor('#6FCF97'))
        self.fmt_debug = QTextCharFormat(); self.fmt_debug.setForeground(QColor('#7f8c8d'))

    def highlightBlock(self, text: str):
        up = text.upper()
        if 'SUCCESS' in up:
            self.setFormat(0, len(text), self.fmt_success)
        elif 'ERROR' in up or 'EXCEPTION' in up or 'TRACEBACK' in up:
            self.setFormat(0, len(text), self.fmt_error)
        elif 'WARN' in up:
            self.setFormat(0, len(text), self.fmt_warning)
        elif 'DEBUG' in up:
            self.setFormat(0, len(text), self.fmt_debug)
        else:
            self.setFormat(0, len(text), self.fmt_info)


class SwitchboardListenerTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self._process: Optional[subprocess.Popen] = None
        self._log_pos: int = 0
        self._build_ui()
        QTimer.singleShot(0, self._launch_and_start_tailing)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(5, 0, 5, 0)  # left/right padding = 5
        toolbar.setSpacing(12)
        self.wrap_cb = QCheckBox()
        self.wrap_cb.setChecked(True)
        self.wrap_label = QLabel("Wrap")
        self.wrap_cb.toggled.connect(self._apply_wrap)
        toolbar.addWidget(self.wrap_cb); toolbar.addWidget(self.wrap_label)
        toolbar.addSpacing(12)
        self.autoscroll_cb = QCheckBox(); self.autoscroll_cb.setChecked(True)
        self.autoscroll_label = QLabel("Auto-scroll")
        toolbar.addWidget(self.autoscroll_cb); toolbar.addWidget(self.autoscroll_label)
        toolbar.addStretch(1)
        clear_btn = QPushButton("Clear"); clear_btn.clicked.connect(lambda: self.text.clear())
        toolbar.addWidget(clear_btn)
        # small gap between Clear and right-side controls
        toolbar.addSpacing(12)
        # Right side controls: Stop/Start and Restart
        self.toggle_btn = QPushButton("Stop listener")
        self.toggle_btn.setToolTip("Start/Stop SwitchboardListener")
        self.toggle_btn.clicked.connect(self._on_toggle_listener)
        toolbar.addWidget(self.toggle_btn)
        # gap between Stop/Start and Restart
        toolbar.addSpacing(12)
        self.restart_btn = QPushButton("Restart listener")
        self.restart_btn.setToolTip("Restart SwitchboardListener")
        self.restart_btn.clicked.connect(self._on_restart_listener)
        toolbar.addWidget(self.restart_btn)
        layout.addLayout(toolbar)

        # Text area
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text.setStyleSheet("QTextEdit { background: #242424; color: #ddd; font: 11px Consolas, 'Courier New', monospace; }")
        layout.addWidget(self.text)

        # Highlighter
        try:
            self._highlighter = _LogHighlighter(self.text.document())
        except Exception:
            self._highlighter = None

    def _first_existing(self, candidates: list[Path]) -> Path | None:
        for p in candidates:
            if p.exists():
                return p
        return None

    def _listener_path(self) -> Path:
        # Try multiple locations
        candidates = [
            Path(r"D:\UE_5.6\Engine\Binaries\Win64\SwitchboardListener.exe"),
            Path(r"C:\Program Files\Epic Games\UE_5.6\Engine\Binaries\Win64\SwitchboardListener.exe"),
        ]
        found = self._first_existing(candidates)
        return found or candidates[0]

    def _log_path(self) -> Path:
        candidates = [
            Path(r"D:\UE_5.6\Engine\Programs\SwitchboardListener\Saved\Logs\SwitchboardListener.log"),
            Path(r"C:\Program Files\Epic Games\UE_5.6\Engine\Programs\SwitchboardListener\Saved\Logs\SwitchboardListener.log"),
        ]
        found = self._first_existing(candidates)
        return found or candidates[0]

    def _launch_and_start_tailing(self):
        try:
            exe = self._listener_path()
            if not exe.exists():
                self.text.append(f"Listener not found: {exe}")
                self.logger.error(f"Listener not found: {exe}")
                return

            # Launch hidden
            startupinfo = None
            creationflags = 0
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = subprocess.CREATE_NO_WINDOW
            self._process = subprocess.Popen([str(exe)], startupinfo=startupinfo, creationflags=creationflags)
            self.text.append("Switchboard Listener started. Tailing log...")
            self.logger.info("Switchboard Listener launched; start tailing log")

            # Tail timer
            self._log_timer = QTimer(self)
            self._log_timer.setInterval(700)
            self._log_timer.timeout.connect(self._read_new_log)
            self._log_timer.start()
        except Exception as exc:
            self.text.append(f"Failed to launch listener: {exc}")
            self.logger.error(f"Failed to launch listener: {exc}")
        finally:
            self._refresh_buttons()

    def closeEvent(self, event):
        try:
            # Stop log timer
            if hasattr(self, '_log_timer'):
                self._log_timer.stop()
            # Terminate process if still alive
            if self._process and self._process.poll() is None:
                self._process.terminate()
        except Exception:
            pass
        return super().closeEvent(event)

    # ---------------- Log tailing ----------------
    def _apply_wrap(self, enabled: bool):
        mode = QTextEdit.WidgetWidth if enabled else QTextEdit.NoWrap
        self.text.setLineWrapMode(mode)

    def _read_new_log(self):
        try:
            log_path = self._log_path()
            if not log_path.exists():
                return
            size = log_path.stat().st_size
            if size < self._log_pos:
                # Rotated/truncated
                self._log_pos = 0
            with log_path.open('r', encoding='utf-8', errors='ignore') as f:
                f.seek(self._log_pos)
                chunk = f.read()
                self._log_pos = f.tell()
                if chunk:
                    self.text.moveCursor(QTextCursor.MoveOperation.End)
                    self.text.insertPlainText(chunk)
                    if self.autoscroll_cb.isChecked():
                        self.text.moveCursor(QTextCursor.MoveOperation.End)
        except Exception:
            pass

    # ---------------- Controls ----------------
    def _is_running(self) -> bool:
        return bool(self._process and self._process.poll() is None)

    def _refresh_buttons(self):
        running = self._is_running()
        self.toggle_btn.setText("Stop listener" if running else "Start listener")
        self.restart_btn.setEnabled(True)

    def _on_toggle_listener(self):
        if self._is_running():
            self._stop_listener()
        else:
            self._start_listener()
        self._refresh_buttons()

    def _on_restart_listener(self):
        self._stop_listener()
        self._start_listener()
        self._refresh_buttons()

    def _stop_listener(self):
        try:
            if hasattr(self, '_log_timer'):
                self._log_timer.stop()
            if self._process and self._process.poll() is None:
                self._process.terminate()
            self._process = None
        except Exception:
            pass

    def _start_listener(self):
        try:
            self._log_pos = 0
            self._launch_and_start_tailing()
        except Exception as exc:
            self.text.append(f"Failed to start listener: {exc}")


