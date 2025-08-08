# -*- coding: utf-8 -*-
"""
NDisplay Monitor Grid
Grid/tile view UI bound to Switchboard's nDisplay monitor model.

This widget presents each nDisplay device as a modern card in a responsive
grid. It listens to the shared nDisplay monitor (QStandardItemModel) used by
Switchboard and reflects live updates without modifying Switchboard internals.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple
from pathlib import Path

from PySide6.QtCore import Qt, QModelIndex, QSize, QEvent, QTimer
from PySide6.QtGui import QIcon, QFont, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QGridLayout,
    QPushButton,
    QCheckBox,
    QSizePolicy,
)

from utils.logger import get_logger


class NDisplayMonitorGrid(QWidget):
    """Grid/tile view for Switchboard nDisplay monitor."""

    def __init__(self, monitor_model, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.monitor = monitor_model  # QStandardItemModel (nDisplayMonitor)

        # Map row index -> card widgets for quick updates
        self.row_to_card: Dict[int, QFrame] = {}
        self._card_min_width = 320
        self._max_columns = 8
        self._current_columns = 0

        self._setup_ui()
        self._load_custom_icons()
        self._connect_model_signals()
        self.rebuild_cards()

        # Default: enable GPU stats to be shown
        try:
            self.chk_gpu.setChecked(True)
            self._on_gpu_toggled(Qt.Checked.value)
        except Exception:
            pass

        # Initial full refresh so static fields like Driver appear immediately
        self._full_refresh()
        self._update_connect_toggle_button()

    # ----------------------------- UI -----------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setToolTip("Request full status update from all devices")
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        toolbar.addWidget(self.btn_refresh)

        # Single toggle button: Connect All / Disconnect All
        self.btn_connect_toggle = QPushButton("Connect All")
        self.btn_connect_toggle.setToolTip("Connect all nDisplay devices")
        self.btn_connect_toggle.clicked.connect(self._on_connect_toggle)
        toolbar.addWidget(self.btn_connect_toggle)

        self.chk_gpu = QCheckBox("GPU Stats")
        self.chk_gpu.setToolTip("Enable/disable GPU stats polling (can cause hitches)")
        self.chk_gpu.stateChanged.connect(self._on_gpu_toggled)
        toolbar.addWidget(self.chk_gpu)

        toolbar.addStretch(1)

        layout.addLayout(toolbar)

        # Scrollable grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Watch viewport resize to recompute column count
        self.scroll.viewport().installEventFilter(self)

        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)

        self.scroll.setWidget(self.content)
        layout.addWidget(self.scroll)

    def _load_custom_icons(self) -> None:
        """Load optional custom icons placed under ui/ndisplaymonitor/images.
        Falls back to Switchboard icons if not present."""
        try:
            images_dir = Path(__file__).parent / "images"
            connect_path = images_dir / "icon_connect.png"
            connected_path = images_dir / "icon_connected.png"

            self.icon_connect_custom: Optional[QIcon] = QIcon(str(connect_path)) if connect_path.exists() else None
            self.icon_connected_custom: Optional[QIcon] = QIcon(str(connected_path)) if connected_path.exists() else None
        except Exception:
            self.icon_connect_custom = None
            self.icon_connected_custom = None

    # ----------------------------- Signals -----------------------------
    def _connect_model_signals(self):
        # Rebuild grid when rows change
        self.monitor.rowsInserted.connect(lambda *_: self.rebuild_cards())
        self.monitor.rowsRemoved.connect(lambda *_: self.rebuild_cards())
        self.monitor.modelReset.connect(lambda: self.rebuild_cards())

        # Update tiles on data changes
        self.monitor.dataChanged.connect(self._on_data_changed)

    # ----------------------------- Actions -----------------------------
    def _on_refresh_clicked(self):
        self._full_refresh()

    def _full_refresh(self):
        try:
            from switchboard.message_protocol import SyncStatusRequestFlags
            self.monitor.poll_sync_status(SyncStatusRequestFlags.all(), all=True)
        except Exception as exc:
            self.logger.error(f"Full refresh failed: {exc}")

    def _iter_ndisplay_devices(self):
        # Devices tracked by this monitor are nDisplay, but we still guard
        try:
            from switchboard.devices.ndisplay.plugin_ndisplay import DevicenDisplay
            for dd in self.monitor.devicedatas.values():
                device = dd.get("device")
                if device is not None and isinstance(device, DevicenDisplay):
                    yield device
        except Exception:
            # Fallback to string type check
            for dd in self.monitor.devicedatas.values():
                device = dd.get("device")
                if device is not None and getattr(device, "device_type", "") == "nDisplay":
                    yield device

    def _on_connect_all(self):
        any_called = False
        for device in self._iter_ndisplay_devices():
            try:
                # Only connect if disconnected
                if hasattr(device, "is_disconnected"):
                    if device.is_disconnected:
                        device.connect_listener()
                        any_called = True
                else:
                    device.connect_listener()
                    any_called = True
            except Exception as exc:
                self.logger.warning(f"Connect failed on {getattr(device, 'name', '?')}: {exc}")
        if any_called:
            # give listeners a moment then refresh
            self._full_refresh()
            QTimer.singleShot(500, self._update_connect_toggle_button)

    def _on_disconnect_all(self):
        any_called = False
        for device in self._iter_ndisplay_devices():
            try:
                # Only disconnect if connected
                if hasattr(device, 'is_connected_and_authenticated'):
                    if device.is_connected_and_authenticated():
                        device.disconnect_listener()
                        any_called = True
                else:
                    device.disconnect_listener()
                    any_called = True
            except Exception as exc:
                self.logger.warning(f"Disconnect failed on {getattr(device, 'name', '?')}: {exc}")
        if any_called:
            self._full_refresh()
            QTimer.singleShot(500, self._update_connect_toggle_button)

    def _any_devices(self) -> bool:
        try:
            return len(self.monitor.devicedatas) > 0
        except Exception:
            return False

    def _any_connected(self) -> bool:
        try:
            for dd in self.monitor.devicedatas.values():
                device = dd.get("device")
                if device and hasattr(device, 'is_connected_and_authenticated') and device.is_connected_and_authenticated():
                    return True
        except Exception:
            pass
        return False

    def _update_connect_toggle_button(self):
        # Disable if no nDisplay devices shown
        if not self._any_devices():
            self.btn_connect_toggle.setEnabled(False)
            self.btn_connect_toggle.setText("Connect All")
            self.btn_connect_toggle.setToolTip("Connect all nDisplay devices")
            return

        self.btn_connect_toggle.setEnabled(True)
        if self._any_connected():
            self.btn_connect_toggle.setText("Disconnect All")
            self.btn_connect_toggle.setToolTip("Disconnect all nDisplay devices")
        else:
            self.btn_connect_toggle.setText("Connect All")
            self.btn_connect_toggle.setToolTip("Connect all nDisplay devices")

    def _on_connect_toggle(self):
        if self._any_connected():
            self._on_disconnect_all()
        else:
            self._on_connect_all()

    def _on_gpu_toggled(self, state: int):
        try:
            from PySide6.QtCore import Qt as _Qt
            self.monitor.on_gpu_stats_toggled(state)
            # After toggling, force a refresh of variable sync status
            if state == _Qt.Checked.value:
                self._on_refresh_clicked()
        except Exception as exc:
            self.logger.error(f"GPU toggle failed: {exc}")

    # ----------------------------- Grid -----------------------------
    def rebuild_cards(self):
        # Clear grid
        for i in reversed(range(self.grid.count())):
            item = self.grid.itemAt(i)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self.row_to_card.clear()

        row_count = getattr(self.monitor, "get_row_count", lambda: self.monitor.rowCount())()
        if row_count == 0:
            placeholder = self._make_placeholder("No nDisplay devices detected")
            self.grid.addWidget(placeholder, 0, 0)
            return

        # Create or recreate cards
        for r in range(row_count):
            card = self._create_card_for_row(r)
            self.row_to_card[r] = card

        # Lay out according to current viewport width
        self._apply_layout(self._calculate_columns())

    def _on_data_changed(self, top_left: QModelIndex, bottom_right: QModelIndex, roles=None):
        # Update affected rows
        for r in range(top_left.row(), bottom_right.row() + 1):
            card = self.row_to_card.get(r)
            if card:
                self._populate_card(card, r)
        self._update_connect_toggle_button()

    # ----------------------------- Responsive layout -----------------------------
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
        # Clear all widgets from grid (but keep existing card instances)
        for i in reversed(range(self.grid.count())):
            item = self.grid.itemAt(i)
            w = item.widget()
            if w is not None:
                self.grid.removeWidget(w)
        # Add back in new positions
        ordered_cards = [self.row_to_card[i] for i in range(len(self.row_to_card))]
        for idx, card in enumerate(ordered_cards):
            grid_row = idx // columns
            grid_col = idx % columns
            self.grid.addWidget(card, grid_row, grid_col)
        # Stretch last column to fill
        for c in range(columns + 1):
            self.grid.setColumnStretch(c, 1 if c == columns else 0)
        self._current_columns = columns
        # Also update toolbar button state when layout changes
        self._update_connect_toggle_button()

    # ----------------------------- Cards -----------------------------
    def _make_placeholder(self, text: str) -> QWidget:
        frame = QFrame()
        frame.setObjectName("placeholder")
        frame.setStyleSheet(
            """
            QFrame#placeholder {
                background-color: #2b2b2b;
                border: 1px dashed #444;
                border-radius: 10px;
            }
            QLabel {
                color: #b0b0b0;
                padding: 24px;
            }
            """
        )
        lay = QVBoxLayout(frame)
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lay.addWidget(lbl)
        return frame

    def _create_card_for_row(self, row_index: int) -> QFrame:
        card = QFrame()
        card.setObjectName("deviceCard")
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        card.setMinimumSize(QSize(320, 220))
        card.setStyleSheet(
            """
            QFrame#deviceCard {
                background-color: #1f1f1f;
                border: 1px solid #2a2a2a;
                border-radius: 12px;
            }
            QLabel[role="title"] {
                color: #ffffff;
                font-size: 14px;
                font-weight: 600;
            }
            QLabel[role="subtitle"] {
                color: #a0a0a0;
                font-size: 11px;
            }
            QLabel[role="key"] {
                color: #c8c8c8;
                font-size: 10px;
            }
            QLabel[role="value"] {
                color: #e8e8e8;
                font-size: 11px;
            }
            """
        )

        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)

        self._add_header_widgets(card, header, row_index)
        v.addLayout(header)

        # Key metrics grid
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        keys = [
            ("Driver", "Driver"),
            ("PresentMode", "Present"),
            ("Gpus", "GPUs"),
            ("Displays", "Displays"),
            ("HouseSync", "House"),
            ("SyncSource", "Source"),
            ("CpuUtilization", "CPU"),
            ("MemUtilization", "Memory"),
            ("GpuUtilization", "GPU"),
            ("GpuTemperature", "Temp"),
            ("FSO", "FSO"),
            ("OsVer", "OS"),
        ]

        # Attach placeholders; populate later
        row = 0
        for key, label in keys:
            k = QLabel(label)
            k.setProperty("role", "key")
            vlabel = QLabel("-")
            vlabel.setProperty("role", "value")
            vlabel.setObjectName(f"val_{key}")
            vlabel.setWordWrap(True)
            grid.addWidget(k, row, 0, alignment=Qt.AlignLeft)
            grid.addWidget(vlabel, row, 1)
            row += 1

        v.addLayout(grid)

        # Footer spacing
        footer = QHBoxLayout()
        footer.addStretch(1)
        v.addLayout(footer)

        # Populate with current model data
        self._populate_card(card, row_index)

        return card

    def _add_header_widgets(self, card: QFrame, header_layout: QHBoxLayout, row_index: int):
        # Status icon
        icon_label = QLabel()
        icon_label.setFixedSize(18, 18)
        icon_label.setObjectName("statusIcon")
        header_layout.addWidget(icon_label)

        # Title and subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(0)

        title = QLabel("Node")
        title.setProperty("role", "title")
        subtitle = QLabel("Host")
        subtitle.setProperty("role", "subtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header_layout.addLayout(title_box, stretch=1)

        # Per-card connect/disconnect toggle button (top-right)
        connect_btn = QPushButton()
        connect_btn.setFixedSize(22, 22)
        connect_btn.setFlat(True)
        connect_btn.setCursor(Qt.PointingHandCursor)
        connect_btn.setIconSize(QSize(16, 16))
        header_layout.addWidget(connect_btn)

        # Save references on card for quick updates
        card._icon_label = icon_label  # type: ignore[attr-defined]
        card._title_label = title       # type: ignore[attr-defined]
        card._subtitle_label = subtitle # type: ignore[attr-defined]
        card._connect_btn = connect_btn # type: ignore[attr-defined]
        # capture row index for toggle handler
        card._row_index = row_index     # type: ignore[attr-defined]
        connect_btn.clicked.connect(lambda: self._on_card_connect_toggle(card._row_index))

        # Initial fill
        self._fill_header(card, row_index)

    def _fill_header(self, card: QFrame, row_index: int):
        col_index = {name: i for i, name in enumerate(self.monitor.colnames)}

        def text_at(col: str) -> str:
            try:
                item = self.monitor.item(row_index, col_index[col])
                return item.text() if item else ""
            except Exception:
                return ""

        node = text_at("Node") or "Node"
        host = text_at("Host") or "Host"
        # IMPORTANT: the model clears text for 'Connected' column and only shows an icon,
        # so we must read the backing data, not the item's text.
        def connected_from_data() -> bool:
            try:
                dd = list(self.monitor.devicedatas.values())[row_index]
                return str(dd.get("data", {}).get("Connected", "no")).lower() == "yes"
            except Exception:
                return False

        connected = connected_from_data()

        card._title_label.setText(node)
        card._subtitle_label.setText(host)

        # Choose icon (prefer custom, otherwise monitor icons)
        icon: Optional[QIcon] = None
        try:
            if connected:
                # Determine if program is running for orange icon
                device = list(self.monitor.devicedatas.values())[row_index]["device"]
                is_running = self.monitor.program_id_from_device(device) != self.monitor.default_program_id()
                if self.icon_connected_custom is not None:
                    icon = self.icon_connected_custom
                else:
                    icon = self.monitor.icon_running if is_running else self.monitor.icon_connected
            else:
                if self.icon_connect_custom is not None:
                    icon = self.icon_connect_custom
                else:
                    icon = self.monitor.icon_unconnected
        except Exception:
            pass

        # Status dot on the left: prefer red/green pngs
        try:
            if connected and self.status_green_png is not None:
                card._icon_label.setPixmap(self.status_green_png.scaled(11, 11, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            elif (not connected) and self.status_red_png is not None:
                card._icon_label.setPixmap(self.status_red_png.scaled(11, 11, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            elif icon is not None:
                card._icon_label.setPixmap(icon.pixmap(18, 18))
        except Exception:
            if icon is not None:
                card._icon_label.setPixmap(icon.pixmap(18, 18))

        # Update per-card connect button icon and tooltip
        try:
            if connected:
                # Use green icon to indicate connected
                if self.icon_connected_custom is not None:
                    card._connect_btn.setIcon(self.icon_connected_custom)
                else:
                    card._connect_btn.setIcon(self.monitor.icon_connected)
                card._connect_btn.setToolTip("Disconnect this device")
            else:
                if self.icon_connect_custom is not None:
                    card._connect_btn.setIcon(self.icon_connect_custom)
                else:
                    card._connect_btn.setIcon(self.monitor.icon_unconnected)
                card._connect_btn.setToolTip("Connect this device")
        except Exception:
            pass

    def _populate_card(self, card: QFrame, row_index: int):
        # Header texts and icon
        self._fill_header(card, row_index)

        # Fill all values and apply background highlights
        col_index = {name: i for i, name in enumerate(self.monitor.colnames)}

        def value_of(col: str) -> str:
            try:
                item = self.monitor.item(row_index, col_index[col])
                return item.text() if item else ""
            except Exception:
                return ""

        # Keys we display
        keys = [
            "Driver",
            "PresentMode",
            "Gpus",
            "Displays",
            "HouseSync",
            "SyncSource",
            "CpuUtilization",
            "MemUtilization",
            "GpuUtilization",
            "GpuTemperature",
            "FSO",
            "OsVer",
        ]

        # Determine running state for background decision
        is_program_running = False
        try:
            device = list(self.monitor.devicedatas.values())[row_index]["device"]
            is_program_running = self.monitor.program_id_from_device(device) != self.monitor.default_program_id()
        except Exception:
            pass

        # Apply values and subtle background accents using monitor's color logic
        for key in keys:
            label: QLabel = card.findChild(QLabel, f"val_{key}")  # type: ignore[assignment]
            if not label:
                continue
            val = value_of(key)
            label.setText(val if val else "-")

            try:
                bg = self.monitor.color_for_column(key, val, list(self.monitor.devicedatas.values())[row_index]["data"], is_program_running)
                # Convert QColor to rgba css
                rgba = f"rgba({bg.red()},{bg.green()},{bg.blue()},40%)"
                label.setStyleSheet(f"QLabel[role=\"value\"]#val_{key} {{ background-color: {rgba}; border-radius: 6px; padding: 4px 6px; }}")
                label.setObjectName(f"val_{key}")
            except Exception:
                # Fallback style
                label.setStyleSheet("")

    # ----------------------------- Per-card connect toggle -----------------------------
    def _on_card_connect_toggle(self, row_index: int):
        try:
            device = list(self.monitor.devicedatas.values())[row_index]["device"]
        except Exception:
            return

        try:
            is_connected = False
            if hasattr(device, 'is_connected_and_authenticated'):
                is_connected = device.is_connected_and_authenticated()

            if is_connected:
                device.disconnect_listener()
            else:
                # If device has attribute is_disconnected prefer that branch
                if hasattr(device, 'is_disconnected') and device.is_disconnected:
                    device.connect_listener()
                else:
                    device.connect_listener()

            # Force a quick UI refresh of rows and the toolbar button state
            self._refresh_rows_then_update_toolbar()
        except Exception as exc:
            self.logger.warning(f"Card connect toggle failed for {getattr(device, 'name', '?')}: {exc}")

    def _refresh_rows_then_update_toolbar(self):
        try:
            row_count = getattr(self.monitor, 'get_row_count', lambda: self.monitor.rowCount())()
            for r in range(row_count):
                try:
                    self.monitor.refresh_display_for_row(r)
                except Exception:
                    pass
        except Exception:
            pass
        # also schedule a poll to pick up latest states from listeners
        self._full_refresh()
        # force cards to re-evaluate connection state
        try:
            row_count = getattr(self.monitor, 'get_row_count', lambda: self.monitor.rowCount())()
            for r in range(row_count):
                try:
                    self._fill_header(self.row_to_card[r], r)
                except Exception:
                    pass
        except Exception:
            pass
        QTimer.singleShot(300, self._update_connect_toggle_button)

    def _load_custom_icons(self) -> None:
        """Load optional custom icons placed under ui/ndisplaymonitor/images and
        status dots from ui/multiusersync/images."""
        try:
            images_dir = Path(__file__).parent / "images"
            connect_path = images_dir / "icon_connect.png"
            connected_path = images_dir / "icon_connected.png"

            self.icon_connect_custom: Optional[QIcon] = QIcon(str(connect_path)) if connect_path.exists() else None
            self.icon_connected_custom: Optional[QIcon] = QIcon(str(connected_path)) if connected_path.exists() else None
        except Exception:
            self.icon_connect_custom = None
            self.icon_connected_custom = None

        # Load status red/green from multiusersync images
        try:
            base_dir = Path(__file__).parent.parent / "multiusersync" / "images"
            red_path = base_dir / "status_red.png"
            green_path = base_dir / "status_green.png"
            self.status_red_png: Optional[QPixmap] = QPixmap(str(red_path)) if red_path.exists() else None
            self.status_green_png: Optional[QPixmap] = QPixmap(str(green_path)) if green_path.exists() else None
        except Exception:
            self.status_red_png = None
            self.status_green_png = None


