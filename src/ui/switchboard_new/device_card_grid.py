# -*- coding: utf-8 -*-
"""
Reusable device card grid for Switchboard devices (Unreal / nDisplay).
"""

from __future__ import annotations

from typing import Callable, Iterable, Optional
from pathlib import Path

from PySide6.QtCore import Qt, QEvent, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QGridLayout,
    QPushButton,
    QSizePolicy,
)

from utils.logger import get_logger


class DeviceCardGrid(QWidget):
    def __init__(
        self,
        *,
        fetch_devices: Callable[[], Iterable[object]],
        title_provider: Callable[[object], str],
        subtitle_provider: Callable[[object], str],
        connect_action: Optional[Callable[[object], None]] = None,
        disconnect_action: Optional[Callable[[object], None]] = None,
        is_connected: Optional[Callable[[object], bool]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.fetch_devices = fetch_devices
        self.title_provider = title_provider
        self.subtitle_provider = subtitle_provider
        self.connect_action = connect_action
        self.disconnect_action = disconnect_action
        self.is_connected = is_connected

        self.row_to_card: list[QFrame] = []
        self._card_min_width = 280
        self._max_columns = 6
        self._current_columns = 0
        
        # Load icons
        self._load_icons()

        self._setup_ui()
        self.rebuild_cards()

    def _load_icons(self):
        """Load connect/disconnect and start/stop icons."""
        try:
            images_dir = Path(__file__).parent / "images"
            
            # Connect/Disconnect icons
            connect_path = images_dir / "icon_connect.png"
            connected_path = images_dir / "icon_connected.png"
            
            self.icon_connect = QIcon(str(connect_path)) if connect_path.exists() else None
            self.icon_connected = QIcon(str(connected_path)) if connected_path.exists() else None
            
            # Start/Stop icons
            open_path = images_dir / "icon_open.png"
            open_disabled_path = images_dir / "icon_open_disabled.png"
            close_path = images_dir / "icon_close.png"
            
            self.icon_open = QIcon(str(open_path)) if open_path.exists() else None
            self.icon_open_disabled = QIcon(str(open_disabled_path)) if open_disabled_path.exists() else None
            self.icon_close = QIcon(str(close_path)) if close_path.exists() else None
            
            # Log missing icons
            for name, path in [
                ("Connect", connect_path), ("Connected", connected_path),
                ("Open", open_path), ("Open Disabled", open_disabled_path), ("Close", close_path)
            ]:
                if not path.exists():
                    self.logger.warning(f"{name} icon not found: {path}")
                
        except Exception as exc:
            self.logger.warning(f"Failed to load icons: {exc}")
            self.icon_connect = None
            self.icon_connected = None
            self.icon_open = None
            self.icon_open_disabled = None
            self.icon_close = None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Scrollable grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.viewport().installEventFilter(self)

        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)

        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)

    def eventFilter(self, obj, event):
        if obj is self.scroll.viewport() and event.type() == QEvent.Resize:
            self._apply_layout(self._calculate_columns())
        return super().eventFilter(obj, event)

    def _calculate_columns(self) -> int:
        try:
            available = self.scroll.viewport().width()
        except Exception:
            available = self.width()
        spacing = self.grid.horizontalSpacing() or 10
        unit = self._card_min_width + spacing
        columns = max(1, (available + spacing) // unit)
        columns = int(min(self._max_columns, max(1, columns)))
        return columns

    def _apply_layout(self, columns: int):
        if columns == self._current_columns and self.grid.count() == len(self.row_to_card):
            return
        # Clear widgets from grid
        for i in reversed(range(self.grid.count())):
            item = self.grid.itemAt(i)
            w = item.widget()
            if w is not None:
                self.grid.removeWidget(w)
        # Add in new positions
        for idx, card in enumerate(self.row_to_card):
            grid_row = idx // columns
            grid_col = idx % columns
            self.grid.addWidget(card, grid_row, grid_col)
        for c in range(columns + 1):
            self.grid.setColumnStretch(c, 1 if c == columns else 0)
        self._current_columns = columns

    def rebuild_cards(self):
        # Clear grid
        for i in reversed(range(self.grid.count())):
            item = self.grid.itemAt(i)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self.row_to_card.clear()

        devices = list(self.fetch_devices() or [])
        if not devices:
            self.grid.addWidget(self._make_placeholder("No devices"), 0, 0)
            return

        for idx, device in enumerate(devices):
            card = self._create_card(device)
            self.row_to_card.append(card)

        self._apply_layout(self._calculate_columns())

    def _make_placeholder(self, text: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("placeholder")
        lay = QVBoxLayout(frame)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)
        return frame

    def _create_card(self, device: object) -> QFrame:
        card = QFrame()
        card.setObjectName("deviceCard")
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        card.setMinimumSize(QSize(280, 140))
        card.setMaximumSize(QSize(350, 180))
        card.setStyleSheet(
            """
            QFrame#deviceCard {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 8px;
                margin: 2px;
            }
            QFrame#deviceCard:hover {
                border: 1px solid #555555;
                background-color: #323232;
            }
            QLabel[role="title"] { 
                color: #ffffff; 
                font-size: 13px; 
                font-weight: 600; 
                padding: 2px;
            }
            QLabel[role="subtitle"] { 
                color: #999999; 
                font-size: 10px; 
                padding: 1px;
            }
            QLabel[role="key"] { 
                color: #bbbbbb; 
                font-size: 9px; 
                font-weight: 500;
                padding: 1px;
            }
            QLabel[role="value"] { 
                color: #dddddd; 
                font-size: 10px; 
                padding: 1px;
            }
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #ffffff;
                font-size: 9px;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #666666;
            }
            QPushButton:pressed {
                background-color: #555555;
            }
            """
        )

        v = QVBoxLayout(card)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)

        # Status dot
        icon_label = QLabel()
        icon_label.setFixedSize(8, 8)
        icon_label.setStyleSheet("background-color: #ff6b6b; border-radius: 4px;")  # Red for disconnected
        header.addWidget(icon_label)

        title = QLabel(self.title_provider(device) or "Device")
        title.setProperty("role", "title")
        subtitle = QLabel(self.subtitle_provider(device) or "")
        subtitle.setProperty("role", "subtitle")

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, stretch=1)

        # Start/Stop button (only enabled when connected)
        start_btn = QPushButton()
        start_btn.setFixedSize(24, 24)
        start_btn.setCursor(Qt.PointingHandCursor)
        start_btn.setIconSize(QSize(16, 16))
        start_btn.setToolTip("Start application")
        header.addWidget(start_btn)

        connect_btn = QPushButton()
        connect_btn.setFixedSize(24, 24)
        connect_btn.setCursor(Qt.PointingHandCursor)
        connect_btn.setIconSize(QSize(16, 16))
        connect_btn.setToolTip("Connect/Disconnect device")
        header.addWidget(connect_btn)

        v.addLayout(header)

        # Minimal kv pairs
        kv = QGridLayout()
        kv.setHorizontalSpacing(8)
        kv.setVerticalSpacing(3)

        def add_row(k: str, val: str):
            kl = QLabel(k)
            kl.setProperty("role", "key")
            vl = QLabel(val or "-")
            vl.setProperty("role", "value")
            r = kv.rowCount()
            kv.addWidget(kl, r, 0, alignment=Qt.AlignLeft)
            kv.addWidget(vl, r, 1)

        # Best-effort; these attributes exist on Device subclasses
        add_row("Type", getattr(device, "device_type", ""))
        add_row("Address", getattr(device, "address", ""))
        
        # Determine connection status for display
        is_connected = False
        try:
            # Use same logic as connection detection
            if self.is_connected:
                is_connected = bool(self.is_connected(device))
            elif hasattr(device, 'is_connected_and_authenticated'):
                is_connected = device.is_connected_and_authenticated()
            elif hasattr(device, 'is_disconnected'):
                is_connected = not device.is_disconnected
            elif hasattr(device, 'status'):
                status_val = getattr(device, 'status')
                if hasattr(status_val, 'name'):
                    is_connected = status_val.name.upper() in ['CONNECTED', 'OPEN', 'READY']
                elif hasattr(status_val, 'value'):
                    is_connected = status_val.value in [1, 2, 3]
        except Exception:
            is_connected = False
        
        # Display human-readable status
        status_display = "CONNECTED" if is_connected else "DISCONNECTED"
        add_row("Status", status_display)

        v.addLayout(kv)

        # Use the same connection state for button logic
        connected = is_connected
        
        # Check if application is running (for Unreal devices)
        is_app_running = False
        try:
            if hasattr(device, 'program_start_queue'):
                # For Unreal devices, check if Unreal is running
                if device.device_type == 'Unreal':
                    running_programs = device.program_start_queue.running_programs_named('Unreal')
                    is_app_running = len(running_programs) > 0
                    self.logger.debug(f"Device {getattr(device, 'name', '?')}: running_programs count = {len(running_programs)}")
            
            # Alternative check: look at device status
            if not is_app_running and hasattr(device, 'status'):
                from switchboard.devices.device_base import DeviceStatus  # type: ignore
                # DeviceStatus.OPEN means the application is running
                is_app_running = device.status >= DeviceStatus.OPEN
                self.logger.debug(f"Device {getattr(device, 'name', '?')}: status = {device.status}, is_running = {is_app_running}")
                
        except Exception as exc:
            self.logger.debug(f"App running check failed for {getattr(device, 'name', '?')}: {exc}")

        # Update Start/Stop button based on connection and running state
        if connected:
            start_btn.setEnabled(True)
            if is_app_running:
                # App is running - show close icon
                if self.icon_close:
                    start_btn.setIcon(self.icon_close)
                else:
                    start_btn.setText("⏹")  # Stop symbol fallback
                start_btn.setToolTip("Stop application")
            else:
                # App not running - show open icon
                if self.icon_open:
                    start_btn.setIcon(self.icon_open)
                else:
                    start_btn.setText("▶")  # Play symbol fallback
                start_btn.setToolTip("Start application")
        else:
            # Not connected - disable start button
            start_btn.setEnabled(False)
            if self.icon_open_disabled:
                start_btn.setIcon(self.icon_open_disabled)
            else:
                start_btn.setText("▶")  # Disabled play symbol
            start_btn.setToolTip("Connect device first to start application")

        # Update Connect button icon and status dot based on connection
        if connected:
            if self.icon_connected:
                connect_btn.setIcon(self.icon_connected)
            else:
                connect_btn.setText("✓")  # Fallback checkmark
            connect_btn.setToolTip("Disconnect device")
            icon_label.setStyleSheet("background-color: #51cf66; border-radius: 4px;")  # Green for connected
        else:
            if self.icon_connect:
                connect_btn.setIcon(self.icon_connect)
            else:
                connect_btn.setText("○")  # Fallback circle
            connect_btn.setToolTip("Connect device")
            icon_label.setStyleSheet("background-color: #ff6b6b; border-radius: 4px;")  # Red for disconnected
            
        def on_toggle():
            try:
                if connected:
                    if self.disconnect_action:
                        self.disconnect_action(device)
                    elif hasattr(device, 'disconnect_listener'):
                        device.disconnect_listener()
                else:
                    if self.connect_action:
                        self.connect_action(device)
                    elif hasattr(device, 'connect_listener'):
                        device.connect_listener()
                        
                # Schedule delayed refresh to allow connection state to update
                from PySide6.QtCore import QTimer
                def delayed_refresh():
                    self.rebuild_cards()
                
                QTimer.singleShot(500, delayed_refresh)  # 500ms delay
                QTimer.singleShot(1500, delayed_refresh)  # 1.5s delay for safety
                
            except Exception as exc:
                self.logger.warning(f"Device connect toggle failed: {exc}")

        connect_btn.clicked.connect(on_toggle)

        def on_start_stop():
            try:
                if not connected:
                    self.logger.warning("Cannot start/stop - device not connected")
                    return
                
                if is_app_running:
                    # Stop application - use the same method as SwitchboardDialog
                    if hasattr(device, 'close'):
                        device.close(force=True)
                        self.logger.info(f"Stopping application on {getattr(device, 'name', '?')}")
                    else:
                        self.logger.warning(f"Device {getattr(device, 'name', '?')} does not support stop")
                else:
                    # Start application - use the same method as SwitchboardDialog
                    if hasattr(device, 'launch'):
                        # Get current level like SwitchboardDialog does
                        try:
                            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
                            dialog = get_current_switchboard_dialog()
                            level = getattr(dialog, 'level', None) if dialog else None
                            device.launch(level)
                        except Exception:
                            # Fallback - launch without level
                            device.launch(None)
                        self.logger.info(f"Starting application on {getattr(device, 'name', '?')}")
                    else:
                        self.logger.warning(f"Device {getattr(device, 'name', '?')} does not support start")
                
                # Schedule delayed refresh to update button states
                from PySide6.QtCore import QTimer
                def delayed_refresh():
                    self.rebuild_cards()
                
                QTimer.singleShot(500, delayed_refresh)   # 0.5s delay
                QTimer.singleShot(1500, delayed_refresh)  # 1.5s delay  
                QTimer.singleShot(3000, delayed_refresh)  # 3s delay for safety
                
            except Exception as exc:
                self.logger.warning(f"Start/Stop failed: {exc}")

        start_btn.clicked.connect(on_start_stop)

        return card


