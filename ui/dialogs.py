"""
Dialog windows for the Enhanced Task Manager.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGroupBox, QSpinBox, QComboBox, QTextEdit,
    QDialogButtonBox, QWidget, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.safety_tiers import SafetyTier, SafetyInfo, get_tier_color


class KillConfirmDialog(QDialog):
    """Confirmation dialog for terminating processes."""

    def __init__(self, proc_name: str, pid: int, safety: SafetyInfo, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Process Termination")
        self.setMinimumWidth(450)
        self.confirmed = False
        self._build_ui(proc_name, pid, safety)

    def _build_ui(self, proc_name: str, pid: int, safety: SafetyInfo):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        tier_color = get_tier_color(safety.tier)
        header = QLabel(f"Terminate: {proc_name} (PID {pid})")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(header)

        # Safety tier indicator
        tier_label = QLabel(f"Safety Level: {safety.label}")
        tier_label.setStyleSheet(f"color: {tier_color}; font-weight: bold; font-size: 14px;")
        layout.addWidget(tier_label)

        if safety.tier == SafetyTier.RED:
            # Red tier: hard block with override
            warning_box = QGroupBox("System Critical Process")
            warning_box.setStyleSheet(f"QGroupBox {{ border-color: {tier_color}; }}")
            wl = QVBoxLayout(warning_box)

            warning_text = QLabel(safety.warning)
            warning_text.setWordWrap(True)
            warning_text.setStyleSheet("color: #f38ba8; font-size: 13px;")
            wl.addWidget(warning_text)

            warning2 = QLabel(
                "Terminating this process WILL cause system instability, "
                "data loss, or a system crash (BSOD). This action is blocked by default."
            )
            warning2.setWordWrap(True)
            warning2.setStyleSheet("color: #fab387;")
            wl.addWidget(warning2)

            layout.addWidget(warning_box)

            # Override checkbox
            self.override_check = QCheckBox(
                "I understand the risks and want to force-terminate this process"
            )
            self.override_check.setStyleSheet("color: #f38ba8;")
            layout.addWidget(self.override_check)

            # Buttons
            btn_layout = QHBoxLayout()
            cancel_btn = QPushButton("Cancel (Recommended)")
            cancel_btn.setObjectName("primaryBtn")
            cancel_btn.clicked.connect(self.reject)
            btn_layout.addWidget(cancel_btn)

            self.force_btn = QPushButton("Force Terminate")
            self.force_btn.setObjectName("dangerBtn")
            self.force_btn.setEnabled(False)
            self.force_btn.clicked.connect(self._on_force)
            btn_layout.addWidget(self.force_btn)

            self.override_check.toggled.connect(self.force_btn.setEnabled)
            layout.addLayout(btn_layout)

        elif safety.tier == SafetyTier.YELLOW:
            # Yellow tier: caution with explanation
            warning_box = QGroupBox("Caution")
            warning_box.setStyleSheet(f"QGroupBox {{ border-color: {tier_color}; }}")
            wl = QVBoxLayout(warning_box)

            if safety.warning:
                warning_text = QLabel(safety.warning)
                warning_text.setWordWrap(True)
                warning_text.setStyleSheet("color: #fab387;")
                wl.addWidget(warning_text)

            consequence = QLabel(
                "Terminating this process may affect system functionality. "
                "The process may restart automatically."
            )
            consequence.setWordWrap(True)
            wl.addWidget(consequence)
            layout.addWidget(warning_box)

            # Buttons
            btn_layout = QHBoxLayout()
            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(self.reject)
            btn_layout.addWidget(cancel_btn)

            confirm_btn = QPushButton("End Task")
            confirm_btn.setObjectName("dangerBtn")
            confirm_btn.clicked.connect(self.accept)
            btn_layout.addWidget(confirm_btn)
            layout.addLayout(btn_layout)

        else:
            # Green tier: simple confirmation
            msg = QLabel(f"Are you sure you want to end '{proc_name}'?")
            msg.setWordWrap(True)
            layout.addWidget(msg)

            btn_layout = QHBoxLayout()
            cancel_btn = QPushButton("Cancel")
            cancel_btn.clicked.connect(self.reject)
            btn_layout.addWidget(cancel_btn)

            confirm_btn = QPushButton("End Task")
            confirm_btn.setObjectName("dangerBtn")
            confirm_btn.clicked.connect(self.accept)
            btn_layout.addWidget(confirm_btn)
            layout.addLayout(btn_layout)

    def _on_force(self):
        self.confirmed = True
        self.accept()


class PriorityDialog(QDialog):
    """Dialog for setting process priority."""

    PRIORITIES = [
        ("Realtime", 256),
        ("High", 128),
        ("Above Normal", 32768),
        ("Normal", 32),
        ("Below Normal", 16384),
        ("Low (Idle)", 64),
    ]

    def __init__(self, proc_name: str, current_nice: int = 32, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Set Priority — {proc_name}")
        self.setMinimumWidth(350)
        self.selected_priority = None
        self._build_ui(current_nice)

    def _build_ui(self, current_nice: int):
        layout = QVBoxLayout(self)

        label = QLabel("Select priority level:")
        layout.addWidget(label)

        self.combo = QComboBox()
        for name, value in self.PRIORITIES:
            self.combo.addItem(name, value)

        # Map psutil nice values to our combo indices
        nice_map = {256: 0, 128: 1, 32768: 2, 32: 3, 16384: 4, 64: 5}
        idx = nice_map.get(current_nice, 3)
        self.combo.setCurrentIndex(idx)
        layout.addWidget(self.combo)

        warning = QLabel("Setting priority to Realtime may make the system unresponsive.")
        warning.setStyleSheet("color: #fab387; font-size: 11px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("Set Priority")
        ok_btn.setObjectName("primaryBtn")
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _on_ok(self):
        self.selected_priority = self.combo.currentData()
        self.accept()


class AffinityDialog(QDialog):
    """Dialog for setting CPU affinity."""

    def __init__(self, proc_name: str, cpu_count: int,
                 current_affinity: list[int], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Set Affinity — {proc_name}")
        self.setMinimumWidth(300)
        self.selected_cpus = []
        self._build_ui(cpu_count, current_affinity)

    def _build_ui(self, cpu_count: int, current_affinity: list[int]):
        layout = QVBoxLayout(self)

        label = QLabel("Select which CPUs this process can use:")
        layout.addWidget(label)

        # Select all / deselect all
        btn_row = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(self._select_all)
        btn_row.addWidget(select_all)
        deselect_all = QPushButton("Deselect All")
        deselect_all.clicked.connect(self._deselect_all)
        btn_row.addWidget(deselect_all)
        layout.addLayout(btn_row)

        # CPU checkboxes in a grid
        grid = QGridLayout()
        self.cpu_checks = []
        cols = 4
        for i in range(cpu_count):
            cb = QCheckBox(f"CPU {i}")
            cb.setChecked(i in current_affinity)
            self.cpu_checks.append(cb)
            grid.addWidget(cb, i // cols, i % cols)
        layout.addLayout(grid)

        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("Set Affinity")
        ok_btn.setObjectName("primaryBtn")
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _select_all(self):
        for cb in self.cpu_checks:
            cb.setChecked(True)

    def _deselect_all(self):
        for cb in self.cpu_checks:
            cb.setChecked(False)

    def _on_ok(self):
        self.selected_cpus = [i for i, cb in enumerate(self.cpu_checks) if cb.isChecked()]
        if not self.selected_cpus:
            return  # Must select at least one
        self.accept()


class SuppressionDialog(QDialog):
    """Dialog for choosing how to suppress a process."""

    def __init__(self, proc_name: str, exe_path: str = "",
                 services: list = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Suppress Process — {proc_name}")
        self.setMinimumWidth(450)
        self.proc_name = proc_name
        self.selected_methods = []
        self._build_ui(exe_path, services or [])

    def _build_ui(self, exe_path: str, services: list):
        layout = QVBoxLayout(self)

        header = QLabel(f"Prevent '{self.proc_name}' from respawning")
        header.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        layout.addWidget(header)

        desc = QLabel("Select suppression methods:")
        layout.addWidget(desc)

        self.checks = {}

        if services:
            for svc in services:
                cb = QCheckBox(f"Disable Windows Service: {svc}")
                self.checks[f"service:{svc}"] = cb
                layout.addWidget(cb)

        cb_startup = QCheckBox("Disable startup entry (if exists)")
        self.checks["startup"] = cb_startup
        layout.addWidget(cb_startup)

        cb_task = QCheckBox("Disable scheduled task (if exists)")
        self.checks["task"] = cb_task
        layout.addWidget(cb_task)

        if exe_path:
            cb_ifeo = QCheckBox(f"Block via IFEO (prevents {self.proc_name} from launching)")
            self.checks["ifeo"] = cb_ifeo
            layout.addWidget(cb_ifeo)

            warning = QLabel(
                "IFEO blocking prevents the executable from running entirely. "
                "Use with caution."
            )
            warning.setWordWrap(True)
            warning.setStyleSheet("color: #fab387; font-size: 11px;")
            layout.addWidget(warning)

        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply Suppression")
        apply_btn.setObjectName("dangerBtn")
        apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(apply_btn)
        layout.addLayout(btn_layout)

    def _on_apply(self):
        self.selected_methods = [k for k, cb in self.checks.items() if cb.isChecked()]
        if self.selected_methods:
            self.accept()


class RespawnAlertDialog(QDialog):
    """Alert when a killed process respawns."""

    def __init__(self, proc_name: str, new_pid: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Process Respawned")
        self.setMinimumWidth(400)
        self.action = None  # "suppress", "kill", None
        self._build_ui(proc_name, new_pid)

    def _build_ui(self, proc_name: str, new_pid: int):
        layout = QVBoxLayout(self)

        header = QLabel(f"'{proc_name}' has respawned!")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #fab387;")
        layout.addWidget(header)

        info = QLabel(f"The process was detected running again with PID {new_pid}.")
        info.setWordWrap(True)
        layout.addWidget(info)

        btn_layout = QHBoxLayout()

        ignore_btn = QPushButton("Ignore")
        ignore_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ignore_btn)

        kill_btn = QPushButton("Kill Again")
        kill_btn.setObjectName("dangerBtn")
        kill_btn.clicked.connect(lambda: self._set_action("kill"))
        btn_layout.addWidget(kill_btn)

        suppress_btn = QPushButton("Suppress Permanently")
        suppress_btn.setObjectName("dangerBtn")
        suppress_btn.clicked.connect(lambda: self._set_action("suppress"))
        btn_layout.addWidget(suppress_btn)

        layout.addLayout(btn_layout)

    def _set_action(self, action: str):
        self.action = action
        self.accept()
