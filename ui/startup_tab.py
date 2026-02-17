"""
Startup Manager tab — list, enable/disable, and manage startup items.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QAbstractItemView, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont

from core.startup_manager import StartupManager, StartupItem


IMPACT_COLORS = {
    "High": "#f38ba8",
    "Medium": "#fab387",
    "Low": "#f9e2af",
    "None": "#a6adc8",
    "Unknown": "#a6adc8",
}

LOCATION_LABELS = {
    "registry_hkcu": "Registry (User)",
    "registry_hklm": "Registry (Machine)",
    "startup_folder": "Startup Folder",
    "task_scheduler": "Task Scheduler",
}


class StartupRefreshWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, manager: StartupManager):
        super().__init__()
        self.manager = manager

    def run(self):
        items = self.manager.get_all_items()
        self.finished.emit(items)


class StartupTab(QWidget):
    """Startup items management tab."""

    status_message = pyqtSignal(str)

    def __init__(self, startup_manager: StartupManager, parent=None):
        super().__init__(parent)
        self.sm = startup_manager
        self._items: list[StartupItem] = []
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Startup Items")
        title.setObjectName("sectionTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("primaryBtn")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)

        self.count_label = QLabel("Loading startup items...")
        self.count_label.setObjectName("subtitle")
        layout.addWidget(self.count_label)

        # Table
        self.table = QTableWidget()
        columns = ["Status", "Name", "Command", "Location", "Impact", "Description"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(1, 180)
        self.table.setColumnWidth(2, 300)
        self.table.setColumnWidth(3, 130)
        self.table.setColumnWidth(4, 80)
        self.table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.table)

        # Bottom bar
        bottom = QHBoxLayout()

        self.enable_btn = QPushButton("Enable")
        self.enable_btn.setObjectName("successBtn")
        self.enable_btn.setEnabled(False)
        self.enable_btn.clicked.connect(lambda: self._toggle_selected(True))
        bottom.addWidget(self.enable_btn)

        self.disable_btn = QPushButton("Disable")
        self.disable_btn.setObjectName("dangerBtn")
        self.disable_btn.setEnabled(False)
        self.disable_btn.clicked.connect(lambda: self._toggle_selected(False))
        bottom.addWidget(self.disable_btn)

        bottom.addStretch()

        # Legend
        legend = QLabel("Impact: ")
        bottom.addWidget(legend)
        for impact, color in IMPACT_COLORS.items():
            if impact == "None":
                continue
            lbl = QLabel(f"● {impact}")
            lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
            bottom.addWidget(lbl)

        layout.addLayout(bottom)

        self.table.selectionModel().selectionChanged.connect(self._on_selection)

    def refresh(self):
        if self._worker and self._worker.isRunning():
            return
        self._worker = StartupRefreshWorker(self.sm)
        self._worker.finished.connect(self._on_data_ready)
        self._worker.start()

    def _on_data_ready(self, items: list):
        self._items = items
        self._update_table()

    def _update_table(self):
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(self._items))

        for row, item in enumerate(self._items):
            # Status
            status_text = "✓ Enabled" if item.enabled else "✗ Disabled"
            status_color = "#a6e3a1" if item.enabled else "#a6adc8"
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QBrush(QColor(status_color)))
            self.table.setItem(row, 0, status_item)

            # Name
            self.table.setItem(row, 1, QTableWidgetItem(item.name))

            # Command
            self.table.setItem(row, 2, QTableWidgetItem(item.command))

            # Location
            loc = LOCATION_LABELS.get(item.location, item.location)
            self.table.setItem(row, 3, QTableWidgetItem(loc))

            # Impact
            impact_item = QTableWidgetItem(item.impact or "Unknown")
            impact_color = IMPACT_COLORS.get(item.impact, "#a6adc8")
            impact_item.setForeground(QBrush(QColor(impact_color)))
            impact_item.setFont(QFont("Segoe UI", -1, QFont.Weight.Bold))
            self.table.setItem(row, 4, impact_item)

            # Description
            self.table.setItem(row, 5, QTableWidgetItem(item.description))

        self.table.setUpdatesEnabled(True)
        self.count_label.setText(
            f"{len(self._items)} startup items "
            f"({sum(1 for i in self._items if i.enabled)} enabled)"
        )

    def _on_selection(self):
        rows = self.table.selectionModel().selectedRows()
        has_sel = bool(rows)
        self.enable_btn.setEnabled(has_sel)
        self.disable_btn.setEnabled(has_sel)

    def _toggle_selected(self, enable: bool):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._items):
            return

        item = self._items[idx]
        action = "enable" if enable else "disable"

        if not enable and item.impact == "High":
            reply = QMessageBox.question(
                self, "Confirm",
                f"'{item.name}' has HIGH startup impact. Are you sure you want to {action} it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        ok, msg = self.sm.toggle_item(item, enable)
        self.status_message.emit(msg)
        if ok:
            item.enabled = enable
            self._update_table()
