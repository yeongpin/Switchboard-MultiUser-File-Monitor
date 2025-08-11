# -*- coding: utf-8 -*-
"""
Switchboard New Tab
Shows Unreal and nDisplay devices in card grid layout.
"""

from __future__ import annotations

import sys
from typing import Optional, Iterable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QFont, QAction, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QSplitter, QFrame, QHBoxLayout,
    QCheckBox, QComboBox, QPushButton, QPlainTextEdit, QLineEdit, QSpacerItem, QSizePolicy,
    QCompleter, QStyledItemDelegate, QMenuBar, QMenu
)
from PySide6.QtCore import QSortFilterProxyModel

from utils.logger import get_logger
from .device_card_grid import DeviceCardGrid


class SwitchboardNewTab(QWidget):
    """Shows Unreal and nDisplay devices in card grids."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        # Bind guards
        self._mu_bound = False
        self._global_ctrls_bound = False
        self._init_ui()
        self._ensure_switchboard_path()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create menu bar at the top
        self.menu_bar = self._create_menu_bar()
        layout.addWidget(self.menu_bar)
        
        # Level row just under the menu
        self.level_row = self._create_level_row()
        layout.addLayout(self.level_row)
        
        # Create vertical splitter for device cards (top) and console/logger (bottom)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(self.splitter)
        
        # Top frame for device cards
        top_frame = QFrame()
        top_layout = QVBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)

        # Section: Unreal Devices
        lbl_unreal = QLabel("Unreal Devices")
        lbl_unreal.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl_unreal.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_unreal.setStyleSheet("color: #ddd; padding: 8px 8px 0 8px;")
        top_layout.addWidget(lbl_unreal)

        self.unreal_grid = DeviceCardGrid(
            fetch_devices=self._fetch_unreal_devices,
            title_provider=lambda d: getattr(d, 'name', 'Unreal'),
            subtitle_provider=lambda d: getattr(d, 'address', ''),
            is_connected=self._is_device_connected,  # Add connection checker
        )
        top_layout.addWidget(self.unreal_grid)

        # Section: nDisplay Devices
        lbl_ndisplay = QLabel("nDisplay Devices")
        lbl_ndisplay.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lbl_ndisplay.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lbl_ndisplay.setStyleSheet("color: #ddd; padding: 12px 8px 0 8px;")
        top_layout.addWidget(lbl_ndisplay)

        self.ndisplay_grid = DeviceCardGrid(
            fetch_devices=self._fetch_ndisplay_devices,
            title_provider=lambda d: getattr(d, 'name', 'nDisplay'),
            subtitle_provider=lambda d: getattr(d, 'address', ''),
            is_connected=self._is_device_connected,  # Add connection checker
        )
        top_layout.addWidget(self.ndisplay_grid)
        
        self.splitter.addWidget(top_frame)
        
        # Bottom frame for console/logger from Switchboard UI
        self._setup_console_logger_frame()
        
        # Set splitter proportions (65% top for devices, 35% bottom for console)
        self.splitter.setSizes([650, 350])

        # Initial refresh and periodic status updates
        QTimer.singleShot(400, self._refresh_grids)
        
        # Delayed logger connection to ensure Switchboard is fully initialized
        QTimer.singleShot(800, self._retry_logger_connection)
        # Repeatedly try to bind real Switchboard menus (in case SB initializes later)
        QTimer.singleShot(800, self._start_menu_sync_timer)
        # Repeatedly try to link level row to Switchboard
        QTimer.singleShot(800, self._start_level_sync_timer)
        
        # Set up periodic status refresh for connection state updates
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(2000)  # Check every 2 seconds
        self._status_timer.timeout.connect(self._refresh_device_status)
        self._status_timer.start()

    def closeEvent(self, event):
        """Handle close event - stop timers and cleanup handlers"""
        try:
            if hasattr(self, '_status_timer'):
                self._status_timer.stop()
            if hasattr(self, '_console_sync_timer'):
                self._console_sync_timer.stop()
            
            # Clean up logging handler if we created one
            if hasattr(self, 'console_handler'):
                import logging
                sb_logger = logging.getLogger('switchboard')
                if sb_logger:
                    sb_logger.removeHandler(self.console_handler)
                    
        except Exception:
            pass
        super().closeEvent(event)

    def _setup_console_logger_frame(self):
        """Setup console/logger frame similar to original Switchboard UI."""
        # Create the logger frame similar to switchboard_ui.py
        frame_logger = QFrame()
        frame_logger.setMinimumSize(0, 100)
        frame_logger.setFrameShape(QFrame.Shape.StyledPanel)
        frame_logger.setFrameShadow(QFrame.Shadow.Raised)
        
        logger_layout = QVBoxLayout(frame_logger)
        logger_layout.setSpacing(4)
        logger_layout.setContentsMargins(0, 0, 0, 0)
        
        # Console command section (similar to ndisplay_monitor_ui.py)
        console_command_layout = self._create_console_command_layout()
        logger_layout.addLayout(console_command_layout)
        
        # Logger options toolbar (copied from switchboard_ui.py)
        logger_options = QHBoxLayout()
        
        # Logger level combobox
        self.logger_level_comboBox = QComboBox()
        self.logger_level_comboBox.addItem("Message")
        self.logger_level_comboBox.addItem("OSC")
        self.logger_level_comboBox.addItem("Debug")
        self.logger_level_comboBox.addItem("Info")
        self.logger_level_comboBox.setCurrentIndex(2)  # Default to Debug
        
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        self.logger_level_comboBox.setSizePolicy(sizePolicy)
        logger_options.addWidget(self.logger_level_comboBox)
        
        # Spacer
        logger_options.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        # Line wrap checkbox
        self.logger_wrap_checkbox = QCheckBox()
        logger_options.addWidget(self.logger_wrap_checkbox)
        
        self.logger_wrap_label = QLabel("Line Wrap")
        logger_options.addWidget(self.logger_wrap_label)
        
        # Spacer
        logger_options.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        # Auto scroll checkbox
        self.logger_autoscroll_checkbox = QCheckBox()
        self.logger_autoscroll_checkbox.setChecked(True)
        logger_options.addWidget(self.logger_autoscroll_checkbox)
        
        self.logger_autoscroll_label = QLabel("Auto Scroll")
        logger_options.addWidget(self.logger_autoscroll_label)
        
        # Spacer
        logger_options.addItem(QSpacerItem(20, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        # Clear log button
        self.clear_log_button = QPushButton("Clear")
        self.clear_log_button.setToolTip("Clear the log window")
        logger_options.addWidget(self.clear_log_button)
        
        logger_layout.addLayout(logger_options)
        
        # Console text area (copied palette and styling from switchboard_ui.py)
        self.base_console = QPlainTextEdit()
        
        # Apply the same styling as original Switchboard
        self.base_console.setFont(QFont("DroidSansMono"))
        self.base_console.setUndoRedoEnabled(False)
        self.base_console.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.base_console.setReadOnly(True)
        self.base_console.setCenterOnScroll(False)
        
        # Set dark theme styling to match Switchboard
        self.base_console.setStyleSheet("""
            QPlainTextEdit {
                background-color: rgb(36, 36, 36);
                color: rgb(177, 177, 177);
                border: 1px solid rgb(60, 60, 60);
            }
        """)
        
        logger_layout.addWidget(self.base_console)
        
        # Bottom status bar
        bottom_layout = QHBoxLayout()
        
        # Spacer
        bottom_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        
        # Address label
        addr_label = QLabel("Address")
        addr_label.setStyleSheet("color: #dcdcdc")
        bottom_layout.addWidget(addr_label)

        # Current address (mirror Switchboard SETTINGS.ADDRESS)
        self.current_address_value = QLineEdit()
        self.current_address_value.setStyleSheet("border: 0px; background-color: rgba(0, 0, 0, 0)")
        self.current_address_value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.current_address_value.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.current_address_value.setReadOnly(True)
        self.current_address_value.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Set an initial value immediately
        try:
            self.current_address_value.setText(self._get_local_ip())
        except Exception:
            pass
        bottom_layout.addWidget(self.current_address_value)
        
        # Separator line
        line_separator = QFrame()
        line_separator.setFrameShape(QFrame.Shape.VLine)
        line_separator.setFrameShadow(QFrame.Shadow.Sunken)
        bottom_layout.addWidget(line_separator)
        
        # Current config file
        self.current_config_file_value = QLabel()
        bottom_layout.addWidget(self.current_config_file_value)
        
        logger_layout.addLayout(bottom_layout)
        
        # Multi-user Session controls under logger
        self._setup_multiuser_session_bar(logger_layout)
        
        # Add to splitter
        self.splitter.addWidget(frame_logger)
        
        # Mirror Address and Config text from Switchboard
        self._mirror_address_and_config_text()
        # Connect console to actual Switchboard logging if available
        self._connect_to_switchboard_logger()

    def _setup_multiuser_session_bar(self, parent_layout: QVBoxLayout):
        """Create Multi-user server header and controls row mirroring Switchboard."""
        # Header label: "Multi-user Server (Name endpoint)"
        self.mu_server_label = QLabel("Multi-user Server")
        self.mu_server_label.setStyleSheet("color: #dcdcdc")
        parent_layout.addWidget(self.mu_server_label)

        # Controls row
        mu_layout = QHBoxLayout()
        mu_layout.setContentsMargins(8, 4, 8, 4)
        mu_layout.setSpacing(8)

        # Start/Stop button (mirrors Switchboard behavior)
        self.mu_start_stop_btn = QPushButton()
        self.mu_start_stop_btn.setCheckable(True)
        # Load icons (prefer local images, fallback to Switchboard resources)
        self._icon_open = self._get_local_icon('icon_open.png') or QIcon(':/icons/images/icon_open.png')
        self._icon_close = self._get_local_icon('icon_close.png') or QIcon(':/icons/images/icon_close.png')
        self._icon_open_disabled = self._get_local_icon('icon_open_disabled.png') or QIcon(':/icons/images/icon_open_disabled.png')
        self.mu_start_stop_btn.setIcon(self._icon_open)
        self.mu_start_stop_btn.setIconSize(QSize(21, 21))
        self.mu_start_stop_btn.setFixedSize(28, 28)
        self.mu_start_stop_btn.setToolTip("Start / stop Unreal Multi-user Server")
        self.mu_start_stop_btn.setStyleSheet("QPushButton { background: transparent; border: 0px; }")
        mu_layout.addWidget(self.mu_start_stop_btn)

        # Auto-join checkbox
        self.mu_autojoin_checkbox = QCheckBox("Auto-join")
        # Default to checked (same as original Switchboard)
        self.mu_autojoin_checkbox.setChecked(True)
        mu_layout.addWidget(self.mu_autojoin_checkbox)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        mu_layout.addWidget(sep)

        # Session label + editor + increment button
        mu_label = QLabel("Session:")
        mu_label.setStyleSheet("color: #cccccc")
        mu_layout.addWidget(mu_label)

        self.mu_session_lineedit = QLineEdit()
        self.mu_session_lineedit.setMinimumWidth(180)
        self.mu_session_lineedit.setPlaceholderText("SessionName")
        mu_layout.addWidget(self.mu_session_lineedit, 1)

        self.mu_inc_btn = QPushButton("+")
        self.mu_inc_btn.setToolTip("Increment the multi-user server session name")
        self.mu_inc_btn.setFixedSize(22, 22)
        self.mu_inc_btn.setStyleSheet("QPushButton { background-color: transparent; border: 1px solid #555; border-radius: 3px; color:#dcdcdc } QPushButton:pressed { background-color: rgba(255,255,255,0.07); }")
        mu_layout.addWidget(self.mu_inc_btn)

        parent_layout.addLayout(mu_layout)

        # Bind to Switchboard
        self._bind_multiuser_session(mu_layout)

    def _bind_multiuser_session(self, layout_ref=None):
        try:
            # Prevent duplicate bindings which would cause + to increment multiple times
            if getattr(self, '_mu_bound', False):
                return
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            if not dialog:
                # Fallback to SETTINGS for initial value and retry binding later
                try:
                    from switchboard.config import SETTINGS  # type: ignore
                    self.mu_session_lineedit.setText(f"{SETTINGS.MUSERVER_SESSION_NAME}")
                except Exception:
                    pass
                # Retry bind shortly
                self._schedule_mu_bind_retry()
                return

            # Initialize current value from SB
            try:
                current = dialog.multiuser_session_name()
                if current:
                    self.mu_session_lineedit.blockSignals(True)
                    self.mu_session_lineedit.setText(current)
                    self.mu_session_lineedit.blockSignals(False)
            except Exception:
                # Fallback to SETTINGS if available
                try:
                    from switchboard.config import SETTINGS  # type: ignore
                    self.mu_session_lineedit.blockSignals(True)
                    self.mu_session_lineedit.setText(f"{SETTINGS.MUSERVER_SESSION_NAME}")
                    self.mu_session_lineedit.blockSignals(False)
                except Exception:
                    pass

            # When edited locally, forward to SB
            def on_local_changed(text: str):
                try:
                    if hasattr(dialog, 'set_multiuser_session_name'):
                        dialog.set_multiuser_session_name(text)
                except Exception:
                    pass

            self.mu_session_lineedit.textChanged.connect(on_local_changed)

            # Increment button forwards to SB increment logic
            if hasattr(dialog, 'on_multiuser_session_inc'):
                self.mu_inc_btn.clicked.connect(lambda: dialog.on_multiuser_session_inc())

            # Auto-join checkbox sync
            try:
                from switchboard.config import CONFIG  # type: ignore
                self.mu_autojoin_checkbox.setChecked(CONFIG.MUSERVER_AUTO_JOIN.get_value())
                def on_autojoin_toggled(state: bool):
                    try:
                        dialog.on_device_autojoin_changed()
                    except Exception:
                        pass
                self.mu_autojoin_checkbox.toggled.connect(on_autojoin_toggled)
            except Exception:
                pass

            # Start/Stop button behavior
            self.mu_start_stop_btn.clicked.connect(lambda: dialog.on_muserver_start_stop_click())
            # Also change icon immediately on toggle for instant feedback
            self.mu_start_stop_btn.toggled.connect(lambda checked: self.mu_start_stop_btn.setIcon(self._icon_close if checked else self._icon_open))

            # Periodically mirror SB value into our line edit to stay in sync
            def mirror_from_sb():
                try:
                    value = dialog.multiuser_session_name()
                    if value and self.mu_session_lineedit.text() != value:
                        self.mu_session_lineedit.blockSignals(True)
                        self.mu_session_lineedit.setText(value)
                        self.mu_session_lineedit.blockSignals(False)
                    # Mirror label and start/stop checked state
                    if hasattr(dialog, 'window') and hasattr(dialog.window, 'muserver_label'):
                        self.mu_server_label.setText(dialog.window.muserver_label.text())
                    if hasattr(dialog, 'window') and hasattr(dialog.window, 'muserver_start_stop_button'):
                        self.mu_start_stop_btn.setChecked(dialog.window.muserver_start_stop_button.isChecked())
                        # Update icon according to state
                        self.mu_start_stop_btn.setIcon(self._icon_close if self.mu_start_stop_btn.isChecked() else self._icon_open)
                    # Auto-join
                    if hasattr(dialog, 'window') and hasattr(dialog.window, 'use_device_autojoin_setting_checkbox'):
                        self.mu_autojoin_checkbox.setChecked(dialog.window.use_device_autojoin_setting_checkbox.isChecked())
                except Exception:
                    pass

            self._mu_sync_timer = QTimer(self)
            self._mu_sync_timer.setInterval(1000)
            self._mu_sync_timer.timeout.connect(mirror_from_sb)
            self._mu_sync_timer.start()
            
            # Mark as bound and stop any retry timer
            self._mu_bound = True
            if hasattr(self, '_mu_bind_timer'):
                try:
                    self._mu_bind_timer.stop()
                except Exception:
                    pass
        except Exception:
            pass

    def _schedule_mu_bind_retry(self):
        try:
            if hasattr(self, '_mu_bind_timer') and self._mu_bind_timer.isActive():
                return
            self._mu_bind_attempts = 0
            self._mu_bind_timer = QTimer(self)
            self._mu_bind_timer.setInterval(1000)
            def try_bind():
                self._mu_bind_attempts += 1
                self._bind_multiuser_session()
                if self._mu_bind_attempts >= 10:
                    self._mu_bind_timer.stop()
            self._mu_bind_timer.timeout.connect(try_bind)
            self._mu_bind_timer.start()
        except Exception:
            pass

    def _create_menu_bar(self) -> QMenuBar:
        """Create menu bar by reusing Switchboard's own menus when available."""
        menu_bar = QMenuBar(self)
        # Ensure the menubar is visible and consistent with dark theme
        menu_bar.setMinimumHeight(28)
        menu_bar.setMaximumHeight(28)
        size_policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        menu_bar.setSizePolicy(size_policy)
        menu_bar.setStyleSheet(
            """
            QMenuBar { background-color: #2e2e2e; border-bottom: 1px solid #444; }
            QMenuBar::item { padding: 6px 12px; color: #dcdcdc; background: transparent; }
            QMenuBar::item:disabled { color: #6c6c6c; }
            QMenuBar::item:selected { background: #3a3a3a; }
            QMenu { background-color: #2e2e2e; border: 1px solid #444; }
            QMenu::item { padding: 6px 18px; color: #dcdcdc; }
            QMenu::item:disabled { color: #6c6c6c; background: transparent; }
            QMenu::item:disabled:selected { background: transparent; }
            QMenu::separator { height: 1px; background: #444; margin: 4px 8px; }
            QMenu::item:selected { background: #3a3a3a; }
            """
        )

        # Try to mirror menus from embedded Switchboard UI so behavior is identical
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            if dialog and hasattr(dialog, 'window') and hasattr(dialog.window, 'menu_bar'):
                source_bar: QMenuBar = dialog.window.menu_bar  # type: ignore
                if source_bar:
                    for action in source_bar.actions():
                        src_menu = action.menu()
                        if src_menu is not None:
                            # Create a local menu and attach the same actions so they call SB logic
                            cloned_menu = QMenu(src_menu.title().replace('&', ''), menu_bar)
                            for a in src_menu.actions():
                                cloned_menu.addAction(a)
                            menu_bar.addMenu(cloned_menu)
                        else:
                            # Top-level action without submenu
                            menu_bar.addAction(action)
                    # Done – return fully mirrored menubar
                    return menu_bar
        except Exception as exc:
            # Fall back to minimal local menus below
            self.logger.debug(f"Switchboard menu mirror failed, using local menu: {exc}")
        
        # Configs Menu
        configs_menu = QMenu("Configs", menu_bar)
        
        # New Config action
        new_config_action = QAction("New Config", self)
        new_config_action.setToolTip("Create a new Switchboard configuration")
        new_config_action.triggered.connect(self._on_new_config)
        configs_menu.addAction(new_config_action)
        
        # Save Config As action
        save_config_as_action = QAction("Save Config As...", self)
        save_config_as_action.setToolTip("Save current configuration with a new name")
        save_config_as_action.triggered.connect(self._on_save_config_as)
        configs_menu.addAction(save_config_as_action)
        
        # Delete Config action
        delete_config_action = QAction("Delete Current Config", self)
        delete_config_action.setToolTip("Delete the currently loaded configuration")
        delete_config_action.triggered.connect(self._on_delete_config)
        configs_menu.addAction(delete_config_action)
        
        configs_menu.addSeparator()
        
        # Load Config submenu
        load_config_menu = QMenu("Load Config", configs_menu)
        self._populate_load_config_menu(load_config_menu)
        configs_menu.addMenu(load_config_menu)
        
        menu_bar.addMenu(configs_menu)
        
        # Settings Menu
        settings_menu = QMenu("Settings", menu_bar)
        
        settings_action = QAction("Settings", self)
        settings_action.setToolTip("Open Switchboard settings")
        settings_action.triggered.connect(self._on_settings)
        settings_menu.addAction(settings_action)
        
        menu_bar.addMenu(settings_menu)
        
        # Tools Menu
        tools_menu = QMenu("Tools", menu_bar)
        
        # Collect Logs action
        collect_logs_action = QAction("Collect Logs", self)
        collect_logs_action.setToolTip("Collect diagnostic logs")
        collect_logs_action.triggered.connect(self._on_collect_logs)
        tools_menu.addAction(collect_logs_action)
        
        # Launcher Tools submenu
        launcher_menu = QMenu("Launcher Tools", tools_menu)
        
        listener_launcher_action = QAction("Listener Launcher", self)
        listener_launcher_action.triggered.connect(self._on_listener_launcher)
        launcher_menu.addAction(listener_launcher_action)
        
        application_launcher_action = QAction("Application Launcher", self)
        application_launcher_action.triggered.connect(self._on_application_launcher)
        launcher_menu.addAction(application_launcher_action)
        
        tools_menu.addMenu(launcher_menu)
        
        menu_bar.addMenu(tools_menu)
        
        return menu_bar

    def _style_toolbar_button(self, btn: QPushButton):
        """Apply unified small-toolbar button styling."""
        btn.setStyleSheet(
            "QPushButton { background-color: transparent; border: 0px; padding: 2px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.06); }"
            "QPushButton:pressed { background: rgba(255,255,255,0.10); }"
            "QPushButton:disabled { background: transparent; }"
        )
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedSize(22, 22)

    def _start_menu_sync_timer(self):
        """Start a short-lived timer to attempt syncing menus from Switchboard."""
        self._menu_sync_attempts = 0
        self._menu_synced = False
        self._menu_sync_timer = QTimer(self)
        self._menu_sync_timer.setInterval(1000)
        self._menu_sync_timer.timeout.connect(self._sync_menu_from_switchboard)
        self._menu_sync_timer.start()

    def _sync_menu_from_switchboard(self):
        """Try to rebuild our menu bar using Switchboard's real QActions."""
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            self._menu_sync_attempts += 1
            if dialog and hasattr(dialog, 'window') and hasattr(dialog.window, 'menu_bar'):
                source_bar: QMenuBar = dialog.window.menu_bar  # type: ignore
                if source_bar and source_bar.actions():
                    # Clear current menus and mirror again
                    self.menu_bar.clear()
                    for action in source_bar.actions():
                        src_menu = action.menu()
                        if src_menu is not None:
                            cloned_menu = QMenu(src_menu.title().replace('&', ''), self.menu_bar)
                            for a in src_menu.actions():
                                cloned_menu.addAction(a)
                            self.menu_bar.addMenu(cloned_menu)
                        else:
                            self.menu_bar.addAction(action)
                    self._menu_synced = True
                    self._menu_sync_timer.stop()
                    return
            # Stop retrying after 10 attempts (~10s)
            if self._menu_sync_attempts >= 10:
                self._menu_sync_timer.stop()
        except Exception:
            # Keep trying until attempts exhausted
            if self._menu_sync_attempts >= 10:
                self._menu_sync_timer.stop()

    # ----- Level row (mirror Switchboard's level selector) -----
    def _create_level_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(8)
        
        label = QLabel("Level:")
        label.setStyleSheet("color: #cccccc;")
        row.addWidget(label)
        
        # Non-editable combo; only selection allowed and no focus
        self.level_combo_box_local = QComboBox()
        self.level_combo_box_local.setEditable(False)
        self.level_combo_box_local.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Inherit app theme; avoid overriding color/background to keep consistent look
        self.level_combo_box_local.setStyleSheet("QComboBox::drop-down { border: 0px; }")
        self.level_combo_box_local.setMinimumWidth(220)
        row.addWidget(self.level_combo_box_local, 1)
        
        # Refresh button
        self.level_refresh_btn = QPushButton()
        self.level_refresh_btn.setToolTip("Refresh level list")
        try:
            refresh_icon_path = Path(__file__).parent / 'images' / 'icon_refresh.png'
            self.level_refresh_btn.setIcon(QIcon(str(refresh_icon_path)))
            self.level_refresh_btn.setIconSize(QSize(18, 18))
        except Exception:
            pass
        self._style_toolbar_button(self.level_refresh_btn)
        row.addWidget(self.level_refresh_btn)

        # Add Start/Stop All and Connect/Disconnect All to the right of refresh
        # Start/Stop All (left of the two)
        self.start_all_button = QPushButton()
        self.start_all_button.setCheckable(True)
        self.start_all_button.setIcon(self._get_local_icon('icon_open.png') or QIcon(':/icons/images/icon_open.png'))
        self.start_all_button.setIconSize(QSize(18, 18))
        self._style_toolbar_button(self.start_all_button)
        self.start_all_button.setToolTip("Start all connected devices")
        row.addWidget(self.start_all_button)

        # Connect/Disconnect All (right)
        self.connect_all_button = QPushButton()
        self.connect_all_button.setCheckable(True)
        self.connect_all_button.setIcon(self._get_local_icon('icon_connect.png') or QIcon(':/icons/images/icon_connect.png'))
        self.connect_all_button.setIconSize(QSize(18, 18))
        self._style_toolbar_button(self.connect_all_button)
        self.connect_all_button.setToolTip("Connect all devices")
        row.addWidget(self.connect_all_button)

        # Bind these global controls to Switchboard behavior
        self._bind_global_device_controls()
        
        return row

    def _start_level_sync_timer(self):
        self._level_sync_attempts = 0
        self._level_sync_timer = QTimer(self)
        self._level_sync_timer.setInterval(1000)
        self._level_sync_timer.timeout.connect(self._sync_level_row_from_switchboard)
        self._level_sync_timer.start()

    def _sync_level_row_from_switchboard(self):
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            self._level_sync_attempts += 1
            if dialog and hasattr(dialog, 'level_combo_box'):
                # Direct attribute on dialog
                sb_level_combo = dialog.level_combo_box
                self._bind_level_controls(sb_level_combo, dialog)
                self._level_sync_timer.stop()
                return
            if dialog and hasattr(dialog, 'window') and hasattr(dialog.window, 'level_combo_box'):
                # Through window UI
                sb_level_combo = dialog.window.level_combo_box
                self._bind_level_controls(sb_level_combo, dialog)
                self._level_sync_timer.stop()
                return
            if self._level_sync_attempts >= 10:
                self._level_sync_timer.stop()
        except Exception:
            if self._level_sync_attempts >= 10:
                self._level_sync_timer.stop()

    def _setup_global_device_controls(self, parent_layout: QVBoxLayout):
        controls = QHBoxLayout()
        controls.setContentsMargins(8, 2, 8, 6)
        controls.setSpacing(10)

        # Start/Stop All (left)
        self.start_all_button = QPushButton()
        self.start_all_button.setCheckable(True)
        self.start_all_button.setIcon(self._get_local_icon('icon_open.png') or QIcon(':/icons/images/icon_open.png'))
        self.start_all_button.setIconSize(QSize(21, 21))
        self.start_all_button.setStyleSheet("QPushButton { background: transparent; border: 0px; }")
        self.start_all_button.setToolTip("Start all connected devices")
        controls.addWidget(self.start_all_button)

        # Connect/Disconnect All (right)
        self.connect_all_button = QPushButton()
        self.connect_all_button.setCheckable(True)
        self.connect_all_button.setIcon(self._get_local_icon('icon_connect.png') or QIcon(':/icons/images/icon_connect.png'))
        self.connect_all_button.setIconSize(QSize(21, 21))
        self.connect_all_button.setStyleSheet("QPushButton { background: transparent; border: 0px; }")
        self.connect_all_button.setToolTip("Connect all devices")
        controls.addWidget(self.connect_all_button)

        # Stretch between buttons
        controls.insertStretch(1, 1)

        parent_layout.addLayout(controls)

        # Bind to Switchboard actions and keep states mirrored
        self._bind_global_device_controls()

    def _bind_global_device_controls(self):
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            if not dialog:
                # Default states before Switchboard is ready
                self.connect_all_button.setEnabled(True)
                self.start_all_button.setEnabled(False)
                self.start_all_button.setIcon(self._get_local_icon('icon_open_disabled.png') or QIcon(':/icons/images/icon_open_disabled.png'))
                self._schedule_global_ctrls_bind_retry()
                return

            # If already bound, don't re-bind
            if getattr(self, '_global_ctrls_bound', False):
                return

            # Click handlers forward to Switchboard
            self.start_all_button.clicked.connect(lambda state: dialog.launch_all_button_clicked(state))
            self.connect_all_button.clicked.connect(lambda state: dialog.connect_all_button_clicked(state))

            # Mirror state periodically
            def mirror_states():
                try:
                    if hasattr(dialog, 'window'):
                        # start
                        checked_start = dialog.window.launch_all_button.isChecked()
                        enabled_start = dialog.window.launch_all_button.isEnabled()
                        any_connected = any(getattr(d, 'is_connected_and_authenticated', lambda: False)() for d in dialog.device_manager.devices())
                        self.start_all_button.setChecked(checked_start)
                        is_enabled = enabled_start and any_connected
                        self.start_all_button.setEnabled(is_enabled)
                        if not is_enabled:
                            self.start_all_button.setIcon(self._get_local_icon('icon_open_disabled.png') or QIcon(':/icons/images/icon_open_disabled.png'))
                        else:
                            self.start_all_button.setIcon(self._get_local_icon('icon_close.png') or QIcon(':/icons/images/icon_close.png') if checked_start else self._get_local_icon('icon_open.png') or QIcon(':/icons/images/icon_open.png'))
                        self.start_all_button.setToolTip("Stop all running devices" if checked_start else ("Start all connected devices" if is_enabled else "Start disabled: no connected devices"))

                        # connect
                        checked_conn = dialog.window.connect_all_button.isChecked()
                        enabled_conn = dialog.window.connect_all_button.isEnabled()
                        self.connect_all_button.setChecked(checked_conn)
                        self.connect_all_button.setEnabled(enabled_conn)
                        self.connect_all_button.setIcon(self._get_local_icon('icon_connected.png') or QIcon(':/icons/images/icon_connected.png') if checked_conn else self._get_local_icon('icon_connect.png') or QIcon(':/icons/images/icon_connect.png'))
                        self.connect_all_button.setToolTip("Disconnect all connected devices" if checked_conn else "Connect all devices")
                except Exception:
                    pass

            if not hasattr(self, '_global_ctrls_timer'):
                self._global_ctrls_timer = QTimer(self)
                self._global_ctrls_timer.setInterval(1000)
                self._global_ctrls_timer.timeout.connect(mirror_states)
                self._global_ctrls_timer.start()

            self._global_ctrls_bound = True
        except Exception:
            pass

    def _schedule_global_ctrls_bind_retry(self):
        try:
            if hasattr(self, '_global_ctrls_bind_timer') and self._global_ctrls_bind_timer.isActive():
                return
            self._global_ctrls_bind_attempts = 0
            self._global_ctrls_bind_timer = QTimer(self)
            self._global_ctrls_bind_timer.setInterval(1000)
            def try_bind():
                self._global_ctrls_bind_attempts += 1
                self._bind_global_device_controls()
                if self._global_ctrls_bind_attempts >= 10:
                    self._global_ctrls_bind_timer.stop()
            self._global_ctrls_bind_timer.timeout.connect(try_bind)
            self._global_ctrls_bind_timer.start()
        except Exception:
            pass

    def _bind_level_controls(self, sb_level_combo, dialog):
        """Bind our local level controls to Switchboard's real widgets."""
        try:
            # Mirror items into local combo and keep in sync periodically
            def sync_items():
                try:
                    self.level_combo_box_local.blockSignals(True)
                    self.level_combo_box_local.clear()
                    for i in range(sb_level_combo.count()):
                        text = sb_level_combo.itemText(i)
                        self.level_combo_box_local.addItem(text)
                    # Select same index
                    self.level_combo_box_local.setCurrentIndex(sb_level_combo.currentIndex())
                finally:
                    self.level_combo_box_local.blockSignals(False)

            sync_items()

            # When user selects in our combo, forward to SB combo
            def on_local_changed(index: int):
                try:
                    if 0 <= index < sb_level_combo.count():
                        sb_level_combo.setCurrentIndex(index)
                except Exception:
                    pass

            self.level_combo_box_local.currentIndexChanged.connect(on_local_changed)

            # Hook SB refresh button if available, else call dialog.refresh_levels
            if hasattr(dialog, 'refresh_levels_button'):
                self.level_refresh_btn.clicked.connect(lambda: dialog.refresh_levels_incremental())
            else:
                self.level_refresh_btn.clicked.connect(lambda: dialog.refresh_levels())

            # Periodically reflect SB combo changes into our UI
            self._level_mirror_timer = QTimer(self)
            self._level_mirror_timer.setInterval(1000)
            self._level_mirror_timer.timeout.connect(sync_items)
            self._level_mirror_timer.start()
        except Exception:
            pass

    def _populate_load_config_menu(self, menu: QMenu):
        """Populate the Load Config submenu with available configs."""
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            
            if dialog and hasattr(dialog, 'config_files'):
                config_files = dialog.config_files
                for config_file in config_files:
                    action = QAction(config_file, self)
                    action.triggered.connect(lambda checked, f=config_file: self._on_load_config(f))
                    menu.addAction(action)
            else:
                # Fallback: add some placeholder items
                action = QAction("No configs available", self)
                action.setEnabled(False)
                menu.addAction(action)
                
        except Exception as exc:
            self.logger.debug(f"Failed to populate config menu: {exc}")

    # Menu action handlers
    def _on_new_config(self):
        """Handle new config action."""
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            if dialog and hasattr(dialog, 'on_new_config'):
                dialog.on_new_config()
            self.base_console.appendPlainText(f"[{self._get_timestamp()}] New config created")
        except Exception as exc:
            self.logger.error(f"New config failed: {exc}")

    def _on_save_config_as(self):
        """Handle save config as action."""
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            if dialog and hasattr(dialog, 'on_save_config_as'):
                dialog.on_save_config_as()
            self.base_console.appendPlainText(f"[{self._get_timestamp()}] Config saved")
        except Exception as exc:
            self.logger.error(f"Save config failed: {exc}")

    def _on_delete_config(self):
        """Handle delete config action."""
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            if dialog and hasattr(dialog, 'on_delete_config'):
                dialog.on_delete_config()
            self.base_console.appendPlainText(f"[{self._get_timestamp()}] Config deleted")
        except Exception as exc:
            self.logger.error(f"Delete config failed: {exc}")

    def _on_load_config(self, config_file: str):
        """Handle load config action."""
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            if dialog and hasattr(dialog, 'load_config'):
                dialog.load_config(config_file)
            self.base_console.appendPlainText(f"[{self._get_timestamp()}] Loaded config: {config_file}")
        except Exception as exc:
            self.logger.error(f"Load config failed: {exc}")

    def _on_settings(self):
        """Handle settings action."""
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            if dialog and hasattr(dialog, 'show_settings'):
                dialog.show_settings()
            self.base_console.appendPlainText(f"[{self._get_timestamp()}] Opening settings")
        except Exception as exc:
            self.logger.error(f"Settings failed: {exc}")

    def _on_collect_logs(self):
        """Handle collect logs action."""
        try:
            self.base_console.appendPlainText(f"[{self._get_timestamp()}] Collecting diagnostic logs...")
            # TODO: Implement log collection
        except Exception as exc:
            self.logger.error(f"Collect logs failed: {exc}")

    def _on_listener_launcher(self):
        """Handle listener launcher action."""
        try:
            self.base_console.appendPlainText(f"[{self._get_timestamp()}] Opening Listener Launcher...")
            # TODO: Implement listener launcher
        except Exception as exc:
            self.logger.error(f"Listener launcher failed: {exc}")

    def _on_application_launcher(self):
        """Handle application launcher action."""
        try:
            self.base_console.appendPlainText(f"[{self._get_timestamp()}] Opening Application Launcher...")
            # TODO: Implement application launcher
        except Exception as exc:
            self.logger.error(f"Application launcher failed: {exc}")

    def _create_console_command_layout(self) -> QHBoxLayout:
        """Create the console command layout similar to nDisplay monitor UI."""
        layout_console = QHBoxLayout()
        
        # Console exec combo entries; key is lowercased, value is as-entered.
        self.exec_history = {}
        
        # Console command label
        console_label = QLabel("Console:")
        console_label.setMinimumWidth(60)
        layout_console.addWidget(console_label)
        
        # Console command combo box (editable)
        self.cmb_console_exec = QComboBox()
        self.cmb_console_exec.setEditable(True)
        self.cmb_console_exec.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)  # done manually
        self.cmb_console_exec.lineEdit().returnPressed.connect(self._on_console_return_pressed)
        
        # Set size policy for the combo box
        size_policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        size_policy.setHorizontalStretch(3)
        self.cmb_console_exec.setSizePolicy(size_policy)
        self.cmb_console_exec.setMinimumWidth(200)
        
        # Set up auto-completion
        self.exec_model = QSortFilterProxyModel(self.cmb_console_exec)
        self.exec_completer = QCompleter(self.exec_model)
        self.exec_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.exec_model.setSourceModel(self.cmb_console_exec.model())
        self.exec_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.exec_completer.popup().setItemDelegate(QStyledItemDelegate())
        self.exec_completer.activated.connect(
            lambda: self._try_issue_console_exec(),
            Qt.ConnectionType.QueuedConnection)  # Queued to work around edit clear timing.
        self.cmb_console_exec.setCompleter(self.exec_completer)
        self.cmb_console_exec.lineEdit().textEdited.connect(
            self.exec_model.setFilterFixedString)
        
        layout_console.addWidget(self.cmb_console_exec)
        
        # Console Exec button
        btn_console_exec = QPushButton("Exec")
        btn_console_exec.setToolTip("Issues a console command to connected devices")
        btn_console_exec.clicked.connect(lambda: self._try_issue_console_exec())
        layout_console.addWidget(btn_console_exec)
        
        # Add stretch to push everything to the left
        layout_console.addStretch(1)
        
        return layout_console

    def _on_console_return_pressed(self):
        """Handle return key pressed in console command field."""
        # If accepting from the autocomplete popup, don't exec twice.
        is_completion = self.exec_completer.popup().currentIndex().isValid()
        if not is_completion:
            self._try_issue_console_exec()

    def _try_issue_console_exec(self, exec_str: Optional[str] = None):
        """Execute console command on connected devices."""
        if exec_str is None:
            exec_str = self.cmb_console_exec.currentText().strip()

        if not exec_str:
            return

        self._update_exec_history(exec_str)
        
        # Try to execute on connected devices
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            
            if dialog and hasattr(dialog, 'device_manager'):
                devices = dialog.device_manager.devices()
                executed_count = 0
                
                # Group devices by type for efficient execution
                unreal_devices = []
                ndisplay_devices = []
                
                for device in devices:
                    if self._is_device_connected(device):
                        device_type = getattr(device, 'device_type', '')
                        if device_type == 'Unreal':
                            unreal_devices.append(device)
                        elif device_type == 'nDisplay':
                            ndisplay_devices.append(device)
                
                # Execute on nDisplay cluster (most efficient for nDisplay devices)
                if ndisplay_devices:
                    try:
                        # Use cluster execution for nDisplay devices
                        ndisplay_devices[0].console_exec_cluster(ndisplay_devices, exec_str)
                        executed_count += len(ndisplay_devices)
                        self.base_console.appendPlainText(f"[{self._get_timestamp()}] nDisplay cluster exec: '{exec_str}' on {len(ndisplay_devices)} device(s)")
                    except Exception as e:
                        self.logger.warning(f"Failed to execute console command on nDisplay cluster: {e}")
                        self.base_console.appendPlainText(f"[{self._get_timestamp()}] nDisplay cluster exec failed: {e}")
                
                # Execute on individual Unreal devices  
                for device in unreal_devices:
                    try:
                        # Try different methods for Unreal devices
                        if hasattr(device, 'console_exec') and callable(device.console_exec):
                            device.console_exec(exec_str)
                            executed_count += 1
                        elif hasattr(device, 'send_unreal_command') and callable(device.send_unreal_command):
                            device.send_unreal_command(exec_str)
                            executed_count += 1
                        else:
                            self.logger.debug(f"Device {getattr(device, 'name', '?')} doesn't support console commands")
                    except Exception as e:
                        self.logger.warning(f"Failed to execute console command on {getattr(device, 'name', '?')}: {e}")
                
                if unreal_devices:
                    self.base_console.appendPlainText(f"[{self._get_timestamp()}] Unreal exec: '{exec_str}' on {len(unreal_devices)} device(s)")
                
                if executed_count > 0:
                    self.cmb_console_exec.clearEditText()
                    self.cmb_console_exec.setCurrentIndex(-1)
                else:
                    self.base_console.appendPlainText(f"[{self._get_timestamp()}] No connected devices found to execute: {exec_str}")
            else:
                self.base_console.appendPlainText(f"[{self._get_timestamp()}] Switchboard not connected - command logged: {exec_str}")
                
        except Exception as exc:
            self.logger.error(f"Console command execution failed: {exc}")
            self.base_console.appendPlainText(f"[{self._get_timestamp()}] Failed to execute: {exec_str}")

    def _update_exec_history(self, exec_str: str):
        """Update console command history."""
        # Reinsert (case-insensitive) duplicates as most recent.
        exec_str_lower = exec_str.lower()
        if exec_str_lower in self.exec_history:
            del self.exec_history[exec_str_lower]
        self.exec_history[exec_str_lower] = exec_str

        # Most recently used at the top.
        self.cmb_console_exec.clear()
        self.cmb_console_exec.addItems(
            reversed(list(self.exec_history.values())))

    def _get_timestamp(self) -> str:
        """Get current timestamp in HH:MM:SS format."""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")

    def _connect_to_switchboard_logger(self):
        """Connect the console to Switchboard's logging system."""
        try:
            # Connect the clear button
            self.clear_log_button.clicked.connect(lambda: self.base_console.clear())
            
            # Connect line wrap checkbox
            def toggle_line_wrap(checked):
                mode = QPlainTextEdit.LineWrapMode.WidgetWidth if checked else QPlainTextEdit.LineWrapMode.NoWrap
                self.base_console.setLineWrapMode(mode)
            
            self.logger_wrap_checkbox.stateChanged.connect(toggle_line_wrap)
            
            # Try to connect to Switchboard's actual logging
            self._setup_switchboard_log_connection()
            
        except Exception as exc:
            self.logger.warning(f"Failed to connect to Switchboard logger: {exc}")
    
    def _setup_switchboard_log_connection(self):
        """Try to connect to the actual Switchboard logging system."""
        try:
            # First try to connect to the embedded Switchboard's console
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            
            if dialog and hasattr(dialog, 'base_console'):
                # If Switchboard has a console, we can mirror its output
                original_console = dialog.base_console
                self.logger.info("Found Switchboard console, setting up mirroring...")
                
                # Create a custom handler to mirror output to our console
                def mirror_to_our_console():
                    try:
                        # Get text from original console and copy to ours
                        original_text = original_console.toPlainText()
                        current_text = self.base_console.toPlainText()
                        
                        # Only update if text has changed and original has content
                        if original_text and original_text != current_text:
                            self.base_console.setPlainText(original_text)
                            
                            # Auto-scroll to end
                            cursor = self.base_console.textCursor()
                            cursor.movePosition(cursor.MoveOperation.End)
                            self.base_console.setTextCursor(cursor)
                            self.base_console.ensureCursorVisible()
                                
                    except Exception as e:
                        pass  # Silently ignore errors
                
                # Set up timer to periodically sync the console
                self._console_sync_timer = QTimer(self)
                self._console_sync_timer.timeout.connect(mirror_to_our_console)
                self._console_sync_timer.start(500)  # Update every 500ms for better responsiveness
                
                # Try initial sync
                mirror_to_our_console()
                
                self.logger.info("Successfully connected to Switchboard console logging")
                return True
                
            # Try alternative approach: access Switchboard's logging directly
            self._try_direct_logging_connection()
                
        except Exception as exc:
            self.logger.warning(f"Could not connect to Switchboard console: {exc}")
            self._fallback_logger_init()
            
    def _try_direct_logging_connection(self):
        """Try to connect directly to Switchboard's logging system."""
        try:
            # Get the root logger that Switchboard uses
            import logging
            sb_logger = logging.getLogger('switchboard')
            
            if sb_logger:
                # Create a custom handler that writes to our console
                class ConsoleHandler(logging.Handler):
                    def __init__(self, console_widget):
                        super().__init__()
                        self.console = console_widget
                        
                    def emit(self, record):
                        try:
                            msg = self.format(record)
                            # Append to console on main thread
                            QTimer.singleShot(0, lambda: self.console.appendPlainText(msg))
                        except Exception:
                            pass
                
                # Create and add our handler
                self.console_handler = ConsoleHandler(self.base_console)
                self.console_handler.setLevel(logging.DEBUG)
                
                # Set format similar to Switchboard's format
                formatter = logging.Formatter('[%(asctime)s] [%(levelname)s]: %(message)s', 
                                            datefmt='%H:%M:%S')
                self.console_handler.setFormatter(formatter)
                
                sb_logger.addHandler(self.console_handler)
                
                self.base_console.appendPlainText("Connected to Switchboard logging system")
                self.logger.info("Successfully connected to Switchboard direct logging")
                return True
                
        except Exception as exc:
            self.logger.debug(f"Direct logging connection failed: {exc}")
            
        return False
            
    def _fallback_logger_init(self):
        """Fallback initialization when Switchboard connection fails."""
        self.base_console.clear()
        self.base_console.appendPlainText("Switchboard New Tab - Logger initialized")
        self.base_console.appendPlainText("Note: Connect to Switchboard for full logging integration")
        self.base_console.appendPlainText("")
        self.base_console.appendPlainText("Standalone logging active - device events will appear here")

    def _retry_logger_connection(self):
        """Retry connecting to Switchboard logging after delay."""
        try:
            # Clear fallback messages and try again
            if "Logger initialized" in self.base_console.toPlainText():
                self.base_console.clear()
                self._setup_switchboard_log_connection()
        except Exception as exc:
            self.logger.debug(f"Retry logger connection failed: {exc}")

    def _get_local_icon(self, filename: str) -> QIcon | None:
        try:
            path = Path(__file__).parent / 'images' / filename
            if path.exists():
                return QIcon(str(path))
        except Exception:
            pass
        return None

    def _mirror_address_and_config_text(self):
        """Mirror Switchboard's current address and config text values."""
        try:
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            if not dialog:
                # Try SETTINGS as fallback
                try:
                    from switchboard.config import SETTINGS, CONFIG  # type: ignore
                    fallback_addr = SETTINGS.ADDRESS.get_value() or self._get_local_ip()
                    if not fallback_addr or fallback_addr.strip().lower() in ('address', 'adress', 'ip', ''):
                        fallback_addr = self._get_local_ip()
                    self.current_address_value.setText(fallback_addr)
                    self.current_config_file_value.setText(str(getattr(CONFIG, 'file_path', '') or ''))
                except Exception:
                    # Last resort
                    self.current_address_value.setText(self._get_local_ip())
                return

            # Initial set
            try:
                if hasattr(dialog, 'window') and hasattr(dialog.window, 'current_address_value'):
                    addr_text = dialog.window.current_address_value.text().strip()
                    if not addr_text or addr_text.lower() in ('address', 'adress', 'ip', ''):
                        addr_text = self._get_local_ip()
                    self.current_address_value.setText(addr_text)
                if hasattr(dialog, 'window') and hasattr(dialog.window, 'current_config_file_value'):
                    self.current_config_file_value.setText(dialog.window.current_config_file_value.text())
            except Exception:
                pass

            # Keep syncing periodically
            def sync_labels():
                try:
                    if hasattr(dialog, 'window') and hasattr(dialog.window, 'current_address_value'):
                        text = dialog.window.current_address_value.text().strip()
                        if not text or text.lower() in ('address', 'adress', 'ip', ''):
                            text = self._get_local_ip()
                        self.current_address_value.setText(text)
                    if hasattr(dialog, 'window') and hasattr(dialog.window, 'current_config_file_value'):
                        self.current_config_file_value.setText(dialog.window.current_config_file_value.text())
                except Exception:
                    pass

            self._addr_cfg_timer = QTimer(self)
            self._addr_cfg_timer.setInterval(1000)
            self._addr_cfg_timer.timeout.connect(sync_labels)
            self._addr_cfg_timer.start()
        except Exception:
            # Last resort
            self.current_address_value.setText(self._get_local_ip())

    def _get_local_ip(self) -> str:
        try:
            import socket
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if ip.startswith("127."):
                for info in socket.getaddrinfo(hostname, None):
                    candidate = info[4][0]
                    if not candidate.startswith("127.") and ":" not in candidate:
                        return candidate
            return ip
        except Exception:
            return "127.0.0.1"

    # ----------------------------- Connection Detection -----------------------------
    
    def _is_device_connected(self, device) -> bool:
        """Check if a device is connected using multiple detection methods."""
        try:
            # Method 1: Authenticated connection (most reliable for nDisplay)
            if hasattr(device, 'is_connected_and_authenticated'):
                return device.is_connected_and_authenticated()
            
            # Method 2: Check disconnected flag
            if hasattr(device, 'is_disconnected'):
                return not device.is_disconnected
            
            # Method 3: Status enum check
            if hasattr(device, 'status'):
                status_val = getattr(device, 'status')
                if hasattr(status_val, 'name'):
                    return status_val.name.upper() in ['CONNECTED', 'OPEN', 'READY']
                elif hasattr(status_val, 'value'):
                    # DeviceStatus enum values: 0=CLOSED, 1=CONNECTED, 2=OPEN, 3=READY
                    return status_val.value in [1, 2, 3]
            
            # Method 4: String fallback
            status_str = str(getattr(device, 'status', '')).upper()
            return 'CONNECT' in status_str and 'DISCONNECT' not in status_str
            
        except Exception as exc:
            self.logger.debug(f"Connection check failed for {getattr(device, 'name', '?')}: {exc}")
            return False

    # ----------------------------- Data sources -----------------------------

    def _fetch_devices_from_config(self, type_check: str) -> Iterable[object]:
        """Get devices from Switchboard's device manager (existing instances)."""
        try:
            # First try to get existing devices from Switchboard's device manager
            from ui.switchboard.switchboard_widget import get_current_switchboard_dialog
            dialog = get_current_switchboard_dialog()
            
            if dialog and hasattr(dialog, 'device_manager'):
                existing_devices = dialog.device_manager.devices()
                filtered_devices = []
                
                for device in existing_devices:
                    device_type = getattr(device, 'device_type', '')
                    if type_check.lower() == 'unreal' and device_type == 'Unreal':
                        filtered_devices.append(device)
                        self.logger.debug(f"Using existing Unreal device: {getattr(device, 'name', '?')}")
                    elif type_check.lower() == 'ndisplay' and device_type == 'nDisplay':
                        filtered_devices.append(device)
                        self.logger.debug(f"Using existing nDisplay device: {getattr(device, 'name', '?')}")
                
                if filtered_devices:
                    return filtered_devices
            
            # Fallback: Create devices from config if no existing devices found
            from switchboard.config import CONFIG, CONFIG_MGR  # type: ignore
            
            if hasattr(CONFIG, '_device_data_from_config'):
                device_data = CONFIG._device_data_from_config
                self.logger.info(f"Found device config data: {list(device_data.keys())}")
                
                devices = []
                if type_check.lower() == 'unreal' and 'Unreal' in device_data:
                    from switchboard.devices.unreal.plugin_unreal import DeviceUnreal  # type: ignore
                    for device_config in device_data['Unreal']:
                        name = device_config['name']
                        address = device_config['address']
                        kwargs = device_config.get('kwargs', {})
                        device = DeviceUnreal(name, address, **kwargs)
                        devices.append(device)
                        self.logger.info(f"Created Unreal device: {name} @ {address}")
                
                elif type_check.lower() == 'ndisplay' and 'nDisplay' in device_data:
                    from switchboard.devices.ndisplay.plugin_ndisplay import DevicenDisplay  # type: ignore
                    for device_config in device_data['nDisplay']:
                        name = device_config['name']
                        address = device_config['address']
                        kwargs = device_config.get('kwargs', {})
                        device = DevicenDisplay(name, address, **kwargs)
                        devices.append(device)
                        self.logger.info(f"Created nDisplay device: {name} @ {address}")
                
                return devices
                
        except Exception as e:
            self.logger.error(f"Error loading devices: {e}")
        
        return []

    def _fetch_unreal_devices(self) -> Iterable[object]:
        return self._fetch_devices_from_config('unreal')

    def _fetch_ndisplay_devices(self) -> Iterable[object]:
        return self._fetch_devices_from_config('ndisplay')

    # ------------- Helpers -------------
    def _ensure_switchboard_path(self) -> bool:
        """Add Switchboard to Python path."""
        current_dir = Path(__file__).parent.parent.parent
        possible_switchboard_paths = [
            current_dir.parent.parent / "Switchboard",
            current_dir.parent / "Switchboard",
            Path("D:/UE_5.6/Engine/Plugins/VirtualProduction/Switchboard/Source/Switchboard"),
            Path("C:/Program Files/Epic Games/UE_5.6/Engine/Plugins/VirtualProduction/Switchboard/Source/Switchboard"),
        ]
        
        for path in possible_switchboard_paths:
            if path.exists():
                if str(path) not in sys.path:
                    sys.path.insert(0, str(path))
                    self.logger.info(f"Added Switchboard path: {path}")
                return True
        self.logger.warning("Switchboard path not found")
        return False

    def _refresh_grids(self):
        """Refresh both device grids."""
        try:
            self.logger.info("Refreshing device grids...")
            self.unreal_grid.rebuild_cards()
            self.ndisplay_grid.rebuild_cards()
        except Exception as e:
            self.logger.error(f"Error refreshing grids: {e}")
    
    def _refresh_device_status(self):
        """Periodically refresh device status without full rebuild."""
        try:
            # Light refresh - just update existing cards' connection states
            self.unreal_grid.rebuild_cards()
            self.ndisplay_grid.rebuild_cards()
        except Exception as exc:
            self.logger.debug(f"Device status refresh failed: {exc}")


