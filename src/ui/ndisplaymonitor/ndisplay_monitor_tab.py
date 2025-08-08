# -*- coding: utf-8 -*-
"""
NDisplay Monitor Tab
Creates a safe, self-contained tab that renders the nDisplay monitor grid.
This module locates the Switchboard package dynamically and binds to the
shared nDisplay monitor without requiring changes to the main app logic.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSplitter
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

from utils.logger import get_logger


def _ensure_switchboard_path() -> bool:
    """Best-effort attempt to add Switchboard to sys.path.

    Returns True if a path was added or already available.
    """
    current_dir = Path(__file__).parent.parent.parent
    possible_switchboard_paths = [
        # Workspace sibling: <repo_root>/Switchboard
        current_dir.parent.parent / "Switchboard",
        # Fallback (if repo was nested differently): <project_root>/Switchboard
        current_dir.parent / "Switchboard",
        Path("D:/UE_5.6/Engine/Plugins/VirtualProduction/Switchboard/Source/Switchboard"),
        Path("C:/Program Files/Epic Games/UE_5.6/Engine/Plugins/VirtualProduction/Switchboard/Source/Switchboard"),
    ]

    for path in possible_switchboard_paths:
        if path.exists():
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
            return True
    return False


class NDisplayMonitorTab(QWidget):
    """Wrapper tab that hosts the nDisplay grid, with graceful fallback."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self._init_attempts = 0
        self.monitor = None
        self._init_ui()

        # Delay init slightly to let Switchboard main tab initialize too
        QTimer.singleShot(1500, self._initialize_grid)

    def _init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Splitter: top = grid, bottom = logger
        self.splitter = QSplitter(Qt.Vertical)
        self.layout.addWidget(self.splitter)

        self.loading_label = QLabel("Initializing nDisplay Monitor...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setFont(QFont("Segoe UI", 12))
        self.loading_label.setStyleSheet(
            """
            QLabel { color: #7f8c8d; padding: 40px; background-color: #222222; }
            """
        )
        self.splitter.addWidget(self.loading_label)

    def _initialize_grid(self):
        try:
            if not _ensure_switchboard_path():
                raise RuntimeError("Switchboard path not found")

            monitor = None
            # Preferred: Use plugin classmethod to get the shared monitor
            try:
                from switchboard.devices.ndisplay.plugin_ndisplay import DevicenDisplay # type: ignore
                monitor = DevicenDisplay.create_monitor_if_necessary()
            except Exception as inner_exc:
                self.logger.info(f"DevicenDisplay monitor path failed, falling back: {inner_exc}")

            # Fallback: create a standalone monitor (will show empty until devices connect)
            if monitor is None:
                try:
                    from switchboard.devices.ndisplay.ndisplay_monitor import nDisplayMonitor # type: ignore
                    monitor = nDisplayMonitor(None)
                except Exception as inner2_exc:
                    raise RuntimeError(f"Could not create nDisplay monitor: {inner2_exc}")

            from .ndisplay_monitor_grid import NDisplayMonitorGrid
            grid_widget = NDisplayMonitorGrid(monitor, parent=self)

            from .ndisplay_logger_widget import NDisplayLoggerWidget
            from .ndisplay_console_bar import NDisplayConsoleBar
            logger_widget = NDisplayLoggerWidget(parent=self)
            console_bar = NDisplayConsoleBar(monitor, parent=self)

            self.loading_label.deleteLater()
            self.splitter.insertWidget(0, grid_widget)
            # Put a small composite under: console bar above logger panel
            from PySide6.QtWidgets import QWidget, QVBoxLayout
            bottom = QWidget()
            bl = QVBoxLayout(bottom)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(2)
            bl.addWidget(console_bar)
            bl.addWidget(logger_widget)


            self.splitter.insertWidget(1, bottom)
            self.splitter.setSizes([500, 400])
            self.monitor = monitor

        except Exception as exc:
            self._init_attempts += 1
            # Keep retrying until Switchboard is ready; show waiting message
            self.logger.info(f"Waiting for Switchboard (attempt {self._init_attempts}): {exc}")
            self.loading_label.setText("Waiting for Switchboard initialization...")
            self.loading_label.setStyleSheet(
                """
                QLabel { color: #f0ad4e; padding: 40px; background-color: #2b2b2b; }
                """
            )
            QTimer.singleShot(1000, self._initialize_grid)

    def closeEvent(self, event):
        """Ensure all nDisplay devices disconnect before app exit."""
        try:
            mon = self.monitor
            if mon is not None and hasattr(mon, 'devicedatas'):
                for dd in list(mon.devicedatas.values()):
                    device = dd.get('device') if isinstance(dd, dict) else None
                    try:
                        if device and hasattr(device, 'is_connected_and_authenticated') and device.is_connected_and_authenticated():
                            device.disconnect_listener()
                    except Exception as exc:
                        self.logger.warning(f"Disconnect on close failed for {getattr(device, 'name', '?')}: {exc}")
        except Exception:
            pass
        event.accept()


