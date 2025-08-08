# -*- coding: utf-8 -*-
"""
NDisplay Console Bar
Single-row console command entry with history and autocomplete.
Delegates execution to the shared nDisplay monitor model.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton, QCompleter,
    QStyledItemDelegate, QSizePolicy
)


class NDisplayConsoleBar(QWidget):
    def __init__(self, monitor_model, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.monitor = monitor_model
        self.exec_history: Dict[str, str] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel('Console:'))

        self.cmb_console_exec = QComboBox()
        self.cmb_console_exec.setEditable(True)
        self.cmb_console_exec.setInsertPolicy(QComboBox.NoInsert)
        size = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        size.setHorizontalStretch(1)
        self.cmb_console_exec.setSizePolicy(size)
        self.cmb_console_exec.setMinimumWidth(220)

        # Autocomplete
        self.exec_model = QSortFilterProxyModel(self.cmb_console_exec)
        self.exec_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.exec_model.setSourceModel(self.cmb_console_exec.model())
        self.exec_completer = QCompleter(self.exec_model)
        self.exec_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.exec_completer.popup().setItemDelegate(QStyledItemDelegate())
        self.exec_completer.activated.connect(self.try_issue_console_exec, Qt.QueuedConnection)
        self.cmb_console_exec.setCompleter(self.exec_completer)
        self.cmb_console_exec.lineEdit().textEdited.connect(self.exec_model.setFilterFixedString)
        self.cmb_console_exec.lineEdit().returnPressed.connect(self.try_issue_console_exec)

        layout.addWidget(self.cmb_console_exec)

        self.btn_exec = QPushButton('Exec')
        self.btn_exec.setToolTip('Issue a console command via nDisplay cluster event')
        self.btn_exec.clicked.connect(self.try_issue_console_exec)
        layout.addWidget(self.btn_exec)

        layout.addStretch(1)

    # ----------------------------- Behavior -----------------------------
    def try_issue_console_exec(self):
        exec_str = self.cmb_console_exec.currentText().strip()
        if not exec_str:
            return

        self._update_exec_history(exec_str)
        try:
            issued = self.monitor.try_issue_console_exec(exec_str)
        except Exception:
            issued = False

        if issued:
            self.cmb_console_exec.clearEditText()
            self.cmb_console_exec.setCurrentIndex(-1)

    def _update_exec_history(self, exec_str: str):
        # Reinsert (case-insensitive) duplicates as most recent
        exec_str_lower = exec_str.lower()
        if exec_str_lower in self.exec_history:
            del self.exec_history[exec_str_lower]
        self.exec_history[exec_str_lower] = exec_str

        # Most recently used at the top
        self.cmb_console_exec.clear()
        self.cmb_console_exec.addItems(reversed(list(self.exec_history.values())))


