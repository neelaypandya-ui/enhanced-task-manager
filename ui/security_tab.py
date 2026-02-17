"""
Security tab — process trust verification, unsigned process detection.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QAbstractItemView, QProgressBar, QLineEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QFont

import psutil
from core.security_checker import SecurityChecker


RISK_COLORS = {
    "safe": "#a6e3a1",
    "low": "#f9e2af",
    "medium": "#fab387",
    "high": "#f38ba8",
    "unknown": "#a6adc8",
}

RISK_LABELS = {
    "safe": "Safe",
    "low": "Low Risk",
    "medium": "Medium Risk",
    "high": "High Risk",
    "unknown": "Unknown",
}


class SecurityScanWorker(QThread):
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(list)

    def __init__(self, checker: SecurityChecker):
        super().__init__()
        self.checker = checker

    def run(self):
        results = []
        processes = []
        seen_exes = set()

        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                exe = proc.info.get('exe')
                if exe and exe not in seen_exes:
                    seen_exes.add(exe)
                    processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        total = len(processes)
        for i, info in enumerate(processes):
            self.progress.emit(i + 1, total)
            exe = info.get('exe', '')
            name = info.get('name', '')
            pid = info.get('pid', 0)

            assessment = self.checker.assess_risk(exe, name)
            results.append({
                'pid': pid,
                'name': name,
                'exe': exe,
                'risk': assessment,
            })

        # Sort by risk level (high first)
        risk_order = {"high": 0, "medium": 1, "low": 2, "unknown": 3, "safe": 4}
        results.sort(key=lambda r: risk_order.get(r['risk'].risk_level, 5))

        self.finished.emit(results)


class SecurityTab(QWidget):
    """Process security analysis tab."""

    status_message = pyqtSignal(str)

    def __init__(self, security_checker: SecurityChecker, parent=None):
        super().__init__(parent)
        self.checker = security_checker
        self._results = []
        self._worker = None
        self._search = ""
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Process Security Scan")
        title.setObjectName("sectionTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter...")
        self.search_box.setMaximumWidth(200)
        self.search_box.textChanged.connect(self._on_search)
        header_layout.addWidget(self.search_box)

        self.scan_btn = QPushButton("Run Security Scan")
        self.scan_btn.setObjectName("primaryBtn")
        self.scan_btn.clicked.connect(self.run_scan)
        header_layout.addWidget(self.scan_btn)
        layout.addLayout(header_layout)

        # Progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel(
            "Click 'Run Security Scan' to check digital signatures and assess process trust."
        )
        self.status_label.setObjectName("subtitle")
        layout.addWidget(self.status_label)

        # Results table
        columns = ["Risk", "Process", "Signed", "Signer", "Location", "Reasons", "Path"]
        self.table = QTableWidget()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        widths = [80, 140, 60, 180, 70, 200, 300]
        for i, w in enumerate(widths):
            self.table.setColumnWidth(i, w)
        self.table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.table)

        # Summary
        self.summary_layout = QHBoxLayout()
        self.summary_labels = {}
        for risk in ["safe", "low", "medium", "high", "unknown"]:
            lbl = QLabel(f"● {RISK_LABELS[risk]}: 0")
            lbl.setStyleSheet(f"color: {RISK_COLORS[risk]}; font-weight: bold;")
            self.summary_layout.addWidget(lbl)
            self.summary_labels[risk] = lbl
        self.summary_layout.addStretch()
        layout.addLayout(self.summary_layout)

    def run_scan(self):
        if self._worker and self._worker.isRunning():
            return
        self.scan_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.status_label.setText("Scanning processes...")

        self._worker = SecurityScanWorker(self.checker)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_scan_done)
        self._worker.start()

    def _on_progress(self, current: int, total: int):
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        self.status_label.setText(f"Scanning... {current}/{total}")

    def _on_scan_done(self, results: list):
        self._results = results
        self.progress.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.status_label.setText(f"Scan complete. {len(results)} unique executables analyzed.")
        self._update_table()

    def _on_search(self, text: str):
        self._search = text.lower()
        self._update_table()

    def _update_table(self):
        filtered = self._results
        if self._search:
            filtered = [
                r for r in filtered
                if self._search in f"{r['name']} {r['exe']} {r['risk'].signer}".lower()
            ]

        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(filtered))

        counts = {"safe": 0, "low": 0, "medium": 0, "high": 0, "unknown": 0}

        for row, result in enumerate(filtered):
            risk = result['risk']
            level = risk.risk_level
            color = RISK_COLORS.get(level, "#a6adc8")
            counts[level] = counts.get(level, 0) + 1

            risk_item = QTableWidgetItem(RISK_LABELS.get(level, level))
            risk_item.setForeground(QBrush(QColor(color)))
            risk_item.setFont(QFont("Segoe UI", -1, QFont.Weight.Bold))
            self.table.setItem(row, 0, risk_item)

            self.table.setItem(row, 1, QTableWidgetItem(result['name']))

            signed_item = QTableWidgetItem("✓" if risk.is_signed else "✗")
            signed_color = "#a6e3a1" if risk.is_signed else "#f38ba8"
            signed_item.setForeground(QBrush(QColor(signed_color)))
            self.table.setItem(row, 2, signed_item)

            self.table.setItem(row, 3, QTableWidgetItem(risk.signer))

            loc_item = QTableWidgetItem("⚠ Suspicious" if risk.suspicious_location else "Normal")
            if risk.suspicious_location:
                loc_item.setForeground(QBrush(QColor("#f38ba8")))
            self.table.setItem(row, 4, loc_item)

            reasons = "; ".join(risk.risk_reasons) if risk.risk_reasons else ""
            self.table.setItem(row, 5, QTableWidgetItem(reasons))

            self.table.setItem(row, 6, QTableWidgetItem(result['exe']))

        self.table.setUpdatesEnabled(True)

        # Update summary
        for level, lbl in self.summary_labels.items():
            lbl.setText(f"● {RISK_LABELS[level]}: {counts.get(level, 0)}")
