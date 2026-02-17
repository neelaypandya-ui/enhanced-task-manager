"""
Process Table widget — the main process list with sorting, filtering, and context menu.
"""

import os
import csv
import subprocess
import webbrowser
from datetime import datetime
from typing import Optional

import psutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenu, QLineEdit, QComboBox, QPushButton, QLabel,
    QAbstractItemView, QFileDialog, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QAction, QFont, QBrush

from core.process_manager import ProcessManager, ProcessInfo
from core.safety_tiers import SafetyTier, get_tier_color, classify_process
from core.suppression_manager import SuppressionManager
from ui.dialogs import (
    KillConfirmDialog, PriorityDialog, AffinityDialog,
    SuppressionDialog, RespawnAlertDialog
)


# Column definitions
COLUMNS = [
    ("", 30),                # Safety tier icon
    ("PID", 60),
    ("Name", 150),
    ("Description", 280),
    ("Safe to Kill?", 220),
    ("Publisher", 130),
    ("Category", 100),
    ("CPU %", 65),
    ("Memory (MB)", 95),
    ("Disk R (KB/s)", 95),
    ("Disk W (KB/s)", 95),
    ("Net S (KB/s)", 90),
    ("Net R (KB/s)", 90),
    ("Threads", 65),
    ("Status", 75),
    ("Start Time", 130),
    ("Path", 250),
]

CATEGORY_COLORS = {
    "system_critical": "#f38ba8",
    "windows_service": "#89b4fa",
    "user_app": "#a6e3a1",
    "background_app": "#cba6f7",
    "startup_item": "#f9e2af",
    "unknown": "#a6adc8",
}

CATEGORY_LABELS = {
    "system_critical": "System Critical",
    "windows_service": "Windows Service",
    "user_app": "User Application",
    "background_app": "Background App",
    "startup_item": "Startup Item",
    "unknown": "Unknown",
}


class ProcessRefreshWorker(QThread):
    """Worker thread for collecting process data."""
    finished = pyqtSignal(dict)

    def __init__(self, manager: ProcessManager):
        super().__init__()
        self.manager = manager

    def run(self):
        processes = self.manager.collect_processes()
        self.finished.emit(processes)


class RespawnCheckWorker(QThread):
    """Worker thread for checking if a process respawned."""
    respawned = pyqtSignal(str, int)  # proc_name, new_pid

    def __init__(self, proc_name: str, original_pid: int, manager: ProcessManager):
        super().__init__()
        self.proc_name = proc_name
        self.original_pid = original_pid
        self.manager = manager

    def run(self):
        new_pid = self.manager.check_respawn(self.proc_name, self.original_pid)
        if new_pid:
            self.respawned.emit(self.proc_name, new_pid)


class ProcessTableWidget(QWidget):
    """Main process list table with all features."""

    process_selected = pyqtSignal(int)  # PID
    status_message = pyqtSignal(str)

    def __init__(self, process_manager: ProcessManager,
                 suppression_manager: SuppressionManager, parent=None):
        super().__init__(parent)
        self.pm = process_manager
        self.sm = suppression_manager
        self._processes: dict[int, ProcessInfo] = {}
        self._sort_column = 6  # CPU% by default
        self._sort_order = Qt.SortOrder.DescendingOrder
        self._filter_text = ""
        self._filter_category = "all"
        self._filter_preset = "all"
        self._cpu_threshold = 50.0
        self._mem_threshold = 500.0  # MB
        self._worker = None
        self._respawn_workers: list[RespawnCheckWorker] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Toolbar row
        toolbar = QHBoxLayout()

        # Search
        search_icon = QLabel("🔍")
        toolbar.addWidget(search_icon)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by name, PID, description, company, or path... (Ctrl+F)")
        self.search_box.textChanged.connect(self._on_filter_changed)
        self.search_box.setMinimumWidth(300)
        toolbar.addWidget(self.search_box, 1)

        # Category filter
        self.category_combo = QComboBox()
        self.category_combo.addItem("All Categories", "all")
        self.category_combo.addItem("🔴 System Critical", "system_critical")
        self.category_combo.addItem("🔵 Windows Service", "windows_service")
        self.category_combo.addItem("🟢 User Application", "user_app")
        self.category_combo.addItem("🟣 Background App", "background_app")
        self.category_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.category_combo)

        # Quick filter presets
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("No Filter", "all")
        self.preset_combo.addItem("High CPU (>50%)", "high_cpu")
        self.preset_combo.addItem("High Memory (>500MB)", "high_mem")
        self.preset_combo.addItem("Network Active", "net_active")
        self.preset_combo.addItem("Unsigned Processes", "unsigned")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        toolbar.addWidget(self.preset_combo)

        layout.addLayout(toolbar)

        # Process count label
        self.count_label = QLabel("0 processes")
        self.count_label.setObjectName("subtitle")
        layout.addWidget(self.count_label)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in COLUMNS])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(False)  # We handle sorting manually
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Set column widths
        header = self.table.horizontalHeader()
        for i, (_, width) in enumerate(COLUMNS):
            self.table.setColumnWidth(i, width)
        header.setStretchLastSection(True)
        header.sectionClicked.connect(self._on_header_clicked)

        layout.addWidget(self.table)

        # Bottom bar
        bottom = QHBoxLayout()
        self.end_task_btn = QPushButton("End Task")
        self.end_task_btn.setObjectName("dangerBtn")
        self.end_task_btn.setEnabled(False)
        self.end_task_btn.clicked.connect(self._on_end_task)
        bottom.addWidget(self.end_task_btn)

        self.end_tree_btn = QPushButton("End Process Tree")
        self.end_tree_btn.setObjectName("dangerBtn")
        self.end_tree_btn.setEnabled(False)
        self.end_tree_btn.clicked.connect(self._on_end_tree)
        bottom.addWidget(self.end_tree_btn)

        bottom.addStretch()

        export_btn = QPushButton("Export CSV")
        export_btn.clicked.connect(self._export_csv)
        bottom.addWidget(export_btn)

        refresh_btn = QPushButton("Refresh (F5)")
        refresh_btn.setObjectName("primaryBtn")
        refresh_btn.clicked.connect(self.refresh)
        bottom.addWidget(refresh_btn)

        layout.addLayout(bottom)

    def refresh(self):
        """Start a background refresh of process data."""
        if self._worker and self._worker.isRunning():
            return
        self._worker = ProcessRefreshWorker(self.pm)
        self._worker.finished.connect(self._on_data_ready)
        self._worker.start()

    def _on_data_ready(self, processes: dict):
        """Called when process data collection completes."""
        self._processes = processes
        self._update_table()

    def _on_filter_changed(self):
        self._filter_text = self.search_box.text().lower()
        self._filter_category = self.category_combo.currentData()
        self._update_table()

    def _on_preset_changed(self):
        self._filter_preset = self.preset_combo.currentData()
        self._update_table()

    def _matches_filter(self, pi: ProcessInfo) -> bool:
        """Check if a process matches the current filters."""
        # Text filter
        if self._filter_text:
            searchable = f"{pi.pid} {pi.name} {pi.description} {pi.company} {pi.exe_path}".lower()
            if self._filter_text not in searchable:
                return False

        # Category filter
        if self._filter_category != "all" and pi.category != self._filter_category:
            return False

        # Preset filters
        if self._filter_preset == "high_cpu" and pi.cpu_percent < self._cpu_threshold:
            return False
        if self._filter_preset == "high_mem" and pi.memory_mb < self._mem_threshold:
            return False
        if self._filter_preset == "net_active":
            if pi.net_sent_speed <= 0 and pi.net_recv_speed <= 0:
                return False

        return True

    def _update_table(self):
        """Rebuild the table with current data and filters."""
        # Filter
        filtered = [pi for pi in self._processes.values() if self._matches_filter(pi)]

        # Sort
        sort_keys = {
            0: lambda p: p.safety.value,
            1: lambda p: p.pid,
            2: lambda p: p.name.lower(),
            3: lambda p: p.description.lower(),
            4: lambda p: p.kill_impact.lower(),
            5: lambda p: p.company.lower(),
            6: lambda p: p.category,
            7: lambda p: p.cpu_percent,
            8: lambda p: p.memory_mb,
            9: lambda p: p.disk_read_speed,
            10: lambda p: p.disk_write_speed,
            11: lambda p: p.net_sent_speed,
            12: lambda p: p.net_recv_speed,
            13: lambda p: p.threads,
            14: lambda p: p.status,
            15: lambda p: p.start_time or datetime.min,
            16: lambda p: p.exe_path.lower(),
        }
        key_fn = sort_keys.get(self._sort_column, sort_keys[6])
        reverse = self._sort_order == Qt.SortOrder.DescendingOrder
        filtered.sort(key=key_fn, reverse=reverse)

        # Update table
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)

        selected_pid = self._get_selected_pid()
        self.table.setRowCount(len(filtered))
        new_selected_row = -1

        for row, pi in enumerate(filtered):
            if pi.pid == selected_pid:
                new_selected_row = row

            tier_color = get_tier_color(pi.safety)
            cat_color = CATEGORY_COLORS.get(pi.category, "#a6adc8")
            cat_label = CATEGORY_LABELS.get(pi.category, "Unknown")

            # Determine kill impact color
            kill_text = pi.kill_impact or ("Safe" if pi.safety == SafetyTier.GREEN else "Unknown")
            if kill_text.startswith("DO NOT KILL"):
                kill_color = "#f38ba8"
            elif kill_text.startswith("DANGEROUS"):
                kill_color = "#f38ba8"
            elif kill_text.startswith("RISKY"):
                kill_color = "#fab387"
            elif kill_text.startswith("CAUTION"):
                kill_color = "#f9e2af"
            elif kill_text.startswith("Safe"):
                kill_color = "#a6e3a1"
            else:
                kill_color = "#a6adc8"

            items = [
                self._make_item("●", tier_color),
                self._make_item(str(pi.pid)),
                self._make_item(pi.name),
                self._make_item(pi.description),
                self._make_item(kill_text, kill_color),
                self._make_item(pi.company),
                self._make_item(cat_label, cat_color),
                self._make_num_item(pi.cpu_percent, fmt="{:.1f}",
                                    highlight=pi.cpu_percent > self._cpu_threshold),
                self._make_num_item(pi.memory_mb, fmt="{:.1f}",
                                    highlight=pi.memory_mb > self._mem_threshold),
                self._make_num_item(pi.disk_read_speed / 1024, fmt="{:.1f}"),
                self._make_num_item(pi.disk_write_speed / 1024, fmt="{:.1f}"),
                self._make_num_item(pi.net_sent_speed / 1024, fmt="{:.1f}"),
                self._make_num_item(pi.net_recv_speed / 1024, fmt="{:.1f}"),
                self._make_num_item(pi.threads, fmt="{:.0f}"),
                self._make_item(pi.status),
                self._make_item(pi.start_time.strftime("%Y-%m-%d %H:%M:%S") if pi.start_time else ""),
                self._make_item(pi.exe_path),
            ]

            # Store PID in first column's data
            items[0].setData(Qt.ItemDataRole.UserRole, pi.pid)

            for col, item in enumerate(items):
                self.table.setItem(row, col, item)

        # Restore selection
        if new_selected_row >= 0:
            self.table.selectRow(new_selected_row)

        self.table.setUpdatesEnabled(True)
        self.count_label.setText(
            f"{len(filtered)} of {len(self._processes)} processes"
        )

    def _make_item(self, text: str, color: str = "") -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        if color:
            item.setForeground(QBrush(QColor(color)))
        return item

    def _make_num_item(self, value: float, fmt: str = "{:.1f}",
                       highlight: bool = False) -> QTableWidgetItem:
        text = fmt.format(value) if value > 0 else ""
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setData(Qt.ItemDataRole.UserRole + 1, value)
        if highlight:
            item.setForeground(QBrush(QColor("#f38ba8")))
            item.setFont(QFont("Segoe UI", -1, QFont.Weight.Bold))
        return item

    def _on_header_clicked(self, col: int):
        if col == self._sort_column:
            self._sort_order = (
                Qt.SortOrder.AscendingOrder
                if self._sort_order == Qt.SortOrder.DescendingOrder
                else Qt.SortOrder.DescendingOrder
            )
        else:
            self._sort_column = col
            self._sort_order = Qt.SortOrder.DescendingOrder
        self._update_table()

    def _get_selected_pid(self) -> Optional[int]:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            item = self.table.item(rows[0].row(), 0)
            if item:
                return item.data(Qt.ItemDataRole.UserRole)
        return None

    def _get_selected_process(self) -> Optional[ProcessInfo]:
        pid = self._get_selected_pid()
        if pid is not None:
            return self._processes.get(pid)
        return None

    def _on_selection_changed(self):
        has_sel = self._get_selected_pid() is not None
        self.end_task_btn.setEnabled(has_sel)
        self.end_tree_btn.setEnabled(has_sel)
        pid = self._get_selected_pid()
        if pid:
            self.process_selected.emit(pid)

    def _show_context_menu(self, pos):
        pi = self._get_selected_process()
        if not pi:
            return

        menu = QMenu(self)

        # End Task
        end_action = QAction("End Task", self)
        end_action.triggered.connect(self._on_end_task)
        menu.addAction(end_action)

        # End Process Tree
        end_tree = QAction("End Process Tree", self)
        end_tree.triggered.connect(self._on_end_tree)
        menu.addAction(end_tree)

        menu.addSeparator()

        # Suppress
        suppress_action = QAction("Suppress (Prevent Respawn)...", self)
        suppress_action.triggered.connect(self._on_suppress)
        menu.addAction(suppress_action)

        menu.addSeparator()

        # Open File Location
        if pi.exe_path:
            open_loc = QAction("Open File Location", self)
            open_loc.triggered.connect(
                lambda: self._open_file_location(pi.exe_path)
            )
            menu.addAction(open_loc)

        # Search Online
        search_action = QAction("Search Online", self)
        search_action.triggered.connect(
            lambda: webbrowser.open(f"https://www.google.com/search?q={pi.name}+process")
        )
        menu.addAction(search_action)

        # Properties
        if pi.exe_path:
            props_action = QAction("Properties", self)
            props_action.triggered.connect(
                lambda: self._show_properties(pi.exe_path)
            )
            menu.addAction(props_action)

        menu.addSeparator()

        # Set Priority
        priority_action = QAction("Set Priority...", self)
        priority_action.triggered.connect(self._on_set_priority)
        menu.addAction(priority_action)

        # Set Affinity
        affinity_action = QAction("Set CPU Affinity...", self)
        affinity_action.triggered.connect(self._on_set_affinity)
        menu.addAction(affinity_action)

        menu.exec(self.table.mapToGlobal(pos))

    def _on_end_task(self):
        pi = self._get_selected_process()
        if not pi:
            return

        safety = pi.safety_info or classify_process(pi.name, pi.pid)

        if safety.tier == SafetyTier.GREEN:
            # Direct kill for green tier
            ok, msg = self.pm.kill_process(pi.pid)
            self.status_message.emit(msg)
            if ok:
                self._check_respawn(pi.name, pi.pid)
        else:
            # Show confirmation dialog
            dlg = KillConfirmDialog(pi.name, pi.pid, safety, parent=self)
            if dlg.exec() == KillConfirmDialog.DialogCode.Accepted:
                force = safety.tier == SafetyTier.RED
                ok, msg = self.pm.kill_process(pi.pid, force=force)
                self.status_message.emit(msg)
                if ok:
                    self._check_respawn(pi.name, pi.pid)

    def _on_end_tree(self):
        pi = self._get_selected_process()
        if not pi:
            return

        safety = pi.safety_info or classify_process(pi.name, pi.pid)
        if safety.tier == SafetyTier.RED:
            dlg = KillConfirmDialog(pi.name, pi.pid, safety, parent=self)
            if dlg.exec() != KillConfirmDialog.DialogCode.Accepted:
                return

        ok, msg = self.pm.kill_process_tree(pi.pid)
        self.status_message.emit(msg)
        if ok:
            self._check_respawn(pi.name, pi.pid)

    def _check_respawn(self, name: str, pid: int):
        """Start a background check for process respawn."""
        worker = RespawnCheckWorker(name, pid, self.pm)
        worker.respawned.connect(self._on_respawn_detected)
        worker.finished.connect(lambda: self._respawn_workers.remove(worker))
        self._respawn_workers.append(worker)
        worker.start()

    def _on_respawn_detected(self, name: str, new_pid: int):
        dlg = RespawnAlertDialog(name, new_pid, parent=self)
        if dlg.exec() == RespawnAlertDialog.DialogCode.Accepted:
            if dlg.action == "kill":
                ok, msg = self.pm.kill_process(new_pid)
                self.status_message.emit(msg)
            elif dlg.action == "suppress":
                self._suppress_process(name, new_pid)

    def _on_suppress(self):
        pi = self._get_selected_process()
        if not pi:
            return
        self._suppress_process(pi.name, pi.pid)

    def _suppress_process(self, name: str, pid: int):
        pi = self._processes.get(pid)
        exe_path = pi.exe_path if pi else ""
        services = pi.services if pi else []

        dlg = SuppressionDialog(name, exe_path, services, parent=self)
        if dlg.exec() == SuppressionDialog.DialogCode.Accepted:
            for method in dlg.selected_methods:
                if method.startswith("service:"):
                    svc = method.split(":", 1)[1]
                    ok, msg = self.sm.disable_service(svc, name)
                    self.status_message.emit(msg)
                elif method == "startup":
                    ok, msg = self.sm.disable_startup_entry(name, process_name=name)
                    self.status_message.emit(msg)
                elif method == "task":
                    ok, msg = self.sm.disable_scheduled_task(name, process_name=name)
                    self.status_message.emit(msg)
                elif method == "ifeo":
                    ok, msg = self.sm.block_via_ifeo(name, process_name=name)
                    self.status_message.emit(msg)

    def _on_set_priority(self):
        pi = self._get_selected_process()
        if not pi:
            return
        try:
            proc = psutil.Process(pi.pid)
            current = proc.nice()
        except Exception:
            current = 32

        dlg = PriorityDialog(pi.name, current, parent=self)
        if dlg.exec() == PriorityDialog.DialogCode.Accepted and dlg.selected_priority is not None:
            ok, msg = self.pm.set_priority(pi.pid, dlg.selected_priority)
            self.status_message.emit(msg)

    def _on_set_affinity(self):
        pi = self._get_selected_process()
        if not pi:
            return
        cpu_count = psutil.cpu_count()
        try:
            proc = psutil.Process(pi.pid)
            current = proc.cpu_affinity()
        except Exception:
            current = list(range(cpu_count))

        dlg = AffinityDialog(pi.name, cpu_count, current, parent=self)
        if dlg.exec() == AffinityDialog.DialogCode.Accepted:
            ok, msg = self.pm.set_affinity(pi.pid, dlg.selected_cpus)
            self.status_message.emit(msg)

    def _open_file_location(self, path: str):
        folder = os.path.dirname(path)
        if os.path.isdir(folder):
            subprocess.Popen(["explorer", "/select,", path])

    def _show_properties(self, path: str):
        if os.path.isfile(path):
            try:
                import win32api
                import win32con
                win32api.ShellExecute(0, "properties", path, None, None, win32con.SW_SHOW)
            except Exception:
                subprocess.Popen(["explorer", "/select,", path])

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Process List", "processes.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([c[0] for c in COLUMNS[1:]])  # Skip tier icon column
                for pi in self._processes.values():
                    writer.writerow([
                        pi.pid, pi.name, pi.description,
                        pi.kill_impact or "Unknown",
                        pi.company,
                        CATEGORY_LABELS.get(pi.category, ""),
                        f"{pi.cpu_percent:.1f}", f"{pi.memory_mb:.1f}",
                        f"{pi.disk_read_speed/1024:.1f}", f"{pi.disk_write_speed/1024:.1f}",
                        f"{pi.net_sent_speed/1024:.1f}", f"{pi.net_recv_speed/1024:.1f}",
                        pi.threads, pi.status,
                        pi.start_time.strftime("%Y-%m-%d %H:%M:%S") if pi.start_time else "",
                        pi.exe_path,
                    ])
            self.status_message.emit(f"Exported {len(self._processes)} processes to {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()
