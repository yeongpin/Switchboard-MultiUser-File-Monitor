# -*- coding: utf-8 -*-
"""
NDisplay Logger Widget
Bottom panel logger with level control, wrap and autoscroll.
Attaches to the root application logger so all module logs stream here.
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QTextCursor, QSyntaxHighlighter, QTextCharFormat, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QComboBox,
    QCheckBox, QLabel, QPushButton
)

from utils.logger import get_logger


class _QtLogEmitter(QObject):
    sig_record = Signal(str)


class QtLogHandler(logging.Handler):
    """Logging handler that forwards formatted records to a Qt signal."""

    def __init__(self):
        super().__init__()
        self.emitter = _QtLogEmitter()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        self.emitter.sig_record.emit(msg)


class NDisplayLoggerWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._attached = False
        self._handler: Optional[QtLogHandler] = None
        self._root_logger: Optional[logging.Logger] = None

        self._build_ui()
        self.attach()

    # ----------------------------- UI -----------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 6)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()

        self.level_combo = QComboBox()
        self.level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.level_combo.setCurrentText("INFO")
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        toolbar.addWidget(self.level_combo)

        toolbar.addStretch(1)

        self.wrap_cb = QCheckBox()
        self.wrap_cb.setChecked(True)
        self.wrap_label = QLabel("Wrap")
        self.wrap_cb.toggled.connect(self._apply_wrap)
        toolbar.addWidget(self.wrap_cb)
        toolbar.addWidget(self.wrap_label)

        toolbar.addStretch(1)

        self.autoscroll_cb = QCheckBox()
        self.autoscroll_cb.setChecked(True)
        self.autoscroll_label = QLabel("Auto-scroll")
        toolbar.addWidget(self.autoscroll_cb)
        toolbar.addWidget(self.autoscroll_label)

        toolbar.addStretch(1)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self.text.clear())
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text.setStyleSheet("QTextEdit { background: #242424; color: #ddd; font: 11px Consolas, 'Courier New', monospace; }")
        layout.addWidget(self.text)

        # Attach syntax highlighter to colorize by severity
        try:
            self._highlighter = _LogHighlighter(self.text.document())
        except Exception:
            self._highlighter = None

    # ----------------------------- Behavior -----------------------------
    def attach(self):
        if self._attached:
            return

        # Prepare handler and formatter
        handler = QtLogHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        # Start with DEBUG so UI選擇能向下收斂；之後用下拉控件動態改 handler level
        handler.setLevel(logging.DEBUG)
        handler.emitter.sig_record.connect(self._on_log_record)

        # Attach to Python root logger only;其他 logger 維持 propagate，
        # 避免重覆輸出並確保由本 handler 控制過濾等級
        root_logger = logging.getLogger()
        # 保證不重複添加一樣的 handler
        if not any(isinstance(h, QtLogHandler) for h in root_logger.handlers):
            root_logger.addHandler(handler)
        # 讓 root 接收所有層級，過濾交給 handler
        if root_logger.level == logging.NOTSET or root_logger.level > logging.DEBUG:
            root_logger.setLevel(logging.DEBUG)

        # Track root for completeness
        self._root_logger = root_logger
        self._handler = handler
        self._attached = True

    def detach(self):
        if not self._attached:
            return
        try:
            if self._root_logger and self._handler:
                self._root_logger.removeHandler(self._handler)
        finally:
            self._handler = None
            self._root_logger = None
            self._attached = False

    def _on_log_record(self, text: str):
        if not text:
            return
        # Append and optionally autoscroll
        self.text.append(text)
        if self.autoscroll_cb.isChecked():
            # Move to end using the correct enum for PySide6
            self.text.moveCursor(QTextCursor.MoveOperation.End)

    def _on_level_changed(self, level_name: str):
        # 只調整本 logger 控制台/檔案 handler 的等級，
        # 其他 logger 維持 DEBUG 以便 propagate；過濾由 handler 完成
        level = getattr(logging, level_name, logging.INFO)
        if self._handler is not None:
            self._handler.setLevel(level)

    def _apply_wrap(self, enabled: bool):
        mode = QTextEdit.WidgetWidth if enabled else QTextEdit.NoWrap
        self.text.setLineWrapMode(mode)

    def closeEvent(self, event):
        self.detach()
        return super().closeEvent(event)



class _LogHighlighter(QSyntaxHighlighter):
    """Colors log lines in QTextEdit based on severity keywords."""
    def __init__(self, parent_doc):
        super().__init__(parent_doc)
        self.fmt_info = QTextCharFormat(); self.fmt_info.setForeground(QColor('#B1B1B1'))
        self.fmt_warning = QTextCharFormat(); self.fmt_warning.setForeground(QColor('#FFD166'))
        self.fmt_error = QTextCharFormat(); self.fmt_error.setForeground(QColor('#FF6B6B'))
        self.fmt_success = QTextCharFormat(); self.fmt_success.setForeground(QColor('#6FCF97'))
        self.fmt_debug = QTextCharFormat(); self.fmt_debug.setForeground(QColor('#7f8c8d'))

    def highlightBlock(self, text: str):
        upper = text.upper()
        if 'SUCCESS' in upper:
            self.setFormat(0, len(text), self.fmt_success)
        elif 'ERROR' in upper or 'EXCEPTION' in upper or 'TRACEBACK' in upper:
            self.setFormat(0, len(text), self.fmt_error)
        elif 'WARN' in upper:
            self.setFormat(0, len(text), self.fmt_warning)
        elif 'DEBUG' in upper:
            self.setFormat(0, len(text), self.fmt_debug)
        else:
            self.setFormat(0, len(text), self.fmt_info)

