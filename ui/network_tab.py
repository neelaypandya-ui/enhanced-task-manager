"""
Network Activity Monitor tab — per-process connections, reverse DNS, suspicious detection.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QAbstractItemView, QComboBox, QLineEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont

from core.network_monitor import NetworkMonitor, ConnectionInfo


class NetworkRefreshWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, monitor: NetworkMonitor):
        super().__init__()
        self.monitor = monitor

    def run(self):
        connections = self.monitor.get_connections()
        self.finished.emit(connections)


class NetworkTab(QWidget):
    """Network activity monitor tab."""

    status_message = pyqtSignal(str)

    def __init__(self, network_monitor: NetworkMonitor, parent=None):
        super().__init__(parent)
        self.nm = network_monitor
        self._connections: list[ConnectionInfo] = []
        self._worker = None
        self._filter = "all"
        self._search = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Network Connections")
        title.setObjectName("sectionTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        # Filter
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("All Connections", "all")
        self.filter_combo.addItem("Established Only", "established")
        self.filter_combo.addItem("Listening Only", "listen")
        self.filter_combo.addItem("🚨 Suspicious Only", "suspicious")
        self.filter_combo.currentIndexChanged.connect(self._on_filter)
        header_layout.addWidget(self.filter_combo)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search connections...")
        self.search_box.setMaximumWidth(200)
        self.search_box.textChanged.connect(self._on_search)
        header_layout.addWidget(self.search_box)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("primaryBtn")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # Stats
        self.stats_label = QLabel("")
        self.stats_label.setObjectName("subtitle")
        layout.addWidget(self.stats_label)

        # Table
        columns = [
            "Process", "PID", "Protocol", "Local Address", "Local Port",
            "Remote Address", "Remote Port", "Hostname", "State", "⚠"
        ]
        self.table = QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        widths = [130, 60, 65, 130, 70, 130, 70, 180, 100, 30]
        for i, w in enumerate(widths):
            self.table.setColumnWidth(i, w)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(True)

        layout.addWidget(self.table)

    def refresh(self):
        if self._worker and self._worker.isRunning():
            return
        self._worker = NetworkRefreshWorker(self.nm)
        self._worker.finished.connect(self._on_data_ready)
        self._worker.start()

    def _on_data_ready(self, connections: list):
        self._connections = connections
        self._update_table()

    def _on_filter(self):
        self._filter = self.filter_combo.currentData()
        self._update_table()

    def _on_search(self, text: str):
        self._search = text.lower()
        self._update_table()

    def _update_table(self):
        filtered = self._connections

        # Apply filter
        if self._filter == "established":
            filtered = [c for c in filtered if c.state == "ESTABLISHED"]
        elif self._filter == "listen":
            filtered = [c for c in filtered if c.state == "LISTEN"]
        elif self._filter == "suspicious":
            filtered = [c for c in filtered if c.is_suspicious]

        # Apply search
        if self._search:
            filtered = [
                c for c in filtered
                if self._search in f"{c.process_name} {c.pid} {c.remote_addr} {c.remote_hostname} {c.local_addr}".lower()
            ]

        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))

        for row, conn in enumerate(filtered):
            items = [
                QTableWidgetItem(conn.process_name),
                QTableWidgetItem(str(conn.pid)),
                QTableWidgetItem(conn.protocol),
                QTableWidgetItem(conn.local_addr),
                QTableWidgetItem(str(conn.local_port)),
                QTableWidgetItem(conn.remote_addr),
                QTableWidgetItem(str(conn.remote_port)),
                QTableWidgetItem(conn.remote_hostname),
                QTableWidgetItem(conn.state),
                QTableWidgetItem("⚠" if conn.is_suspicious else ""),
            ]

            if conn.is_suspicious:
                for item in items:
                    item.setForeground(QBrush(QColor("#f38ba8")))
                    item.setToolTip(conn.suspicion_reason)

            for col, item in enumerate(items):
                self.table.setItem(row, col, item)

        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(True)

        # Stats
        total = len(self._connections)
        established = sum(1 for c in self._connections if c.state == "ESTABLISHED")
        listening = sum(1 for c in self._connections if c.state == "LISTEN")
        suspicious = sum(1 for c in self._connections if c.is_suspicious)

        stats = f"{total} connections ({established} established, {listening} listening"
        if suspicious:
            stats += f", {suspicious} suspicious"
        stats += f") — showing {len(filtered)}"
        self.stats_label.setText(stats)
