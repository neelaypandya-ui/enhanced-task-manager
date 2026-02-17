"""
Suppression Manager tab — shows all blocked processes with one-click restore.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QAbstractItemView, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush

from core.suppression_manager import SuppressionManager, SuppressionEntry


METHOD_LABELS = {
    "service": "Windows Service (Disabled)",
    "startup": "Startup Entry (Removed)",
    "task": "Scheduled Task (Disabled)",
    "ifeo": "IFEO Block (Execution Blocked)",
}


class SuppressionTab(QWidget):
    """Suppression manager panel."""

    status_message = pyqtSignal(str)

    def __init__(self, suppression_manager: SuppressionManager, parent=None):
        super().__init__(parent)
        self.sm = suppression_manager
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Suppression Manager")
        title.setObjectName("sectionTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        restore_all_btn = QPushButton("Restore All")
        restore_all_btn.setObjectName("primaryBtn")
        restore_all_btn.clicked.connect(self._restore_all)
        header_layout.addWidget(restore_all_btn)
        layout.addLayout(header_layout)

        desc = QLabel(
            "Processes that have been suppressed to prevent respawning. "
            "Click 'Restore' to undo the suppression and allow the process to run again."
        )
        desc.setWordWrap(True)
        desc.setObjectName("subtitle")
        layout.addWidget(desc)

        # Table
        columns = ["Process", "Method", "Detail", "Created", "Actions"]
        self.table = QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        widths = [150, 200, 250, 150, 100]
        for i, w in enumerate(widths):
            self.table.setColumnWidth(i, w)
        self.table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.table)

        self.empty_label = QLabel("No suppression rules active. Processes you suppress will appear here.")
        self.empty_label.setObjectName("subtitle")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_label)

    def refresh(self):
        entries = self.sm.get_entries()
        self.table.setRowCount(len(entries))
        self.empty_label.setVisible(len(entries) == 0)
        self.table.setVisible(len(entries) > 0)

        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(entry.process_name))
            method_label = METHOD_LABELS.get(entry.method, entry.method)
            self.table.setItem(row, 1, QTableWidgetItem(method_label))
            self.table.setItem(row, 2, QTableWidgetItem(entry.detail))
            self.table.setItem(row, 3, QTableWidgetItem(entry.created[:19] if entry.created else ""))

            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("successBtn")
            restore_btn.clicked.connect(lambda checked, r=row: self._restore_entry(r))
            self.table.setCellWidget(row, 4, restore_btn)

    def _restore_entry(self, index: int):
        entry = self.sm.get_entries()[index]
        reply = QMessageBox.question(
            self, "Confirm Restore",
            f"Restore '{entry.process_name}'? This will undo the suppression "
            f"and allow the process to run again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = self.sm.restore_entry(index)
            self.status_message.emit(msg)
            self.refresh()

    def _restore_all(self):
        entries = self.sm.get_entries()
        if not entries:
            return
        reply = QMessageBox.question(
            self, "Confirm Restore All",
            f"Restore all {len(entries)} suppressed processes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            results = self.sm.restore_all()
            succeeded = sum(1 for ok, _ in results if ok)
            self.status_message.emit(f"Restored {succeeded} of {len(results)} entries.")
            self.refresh()
