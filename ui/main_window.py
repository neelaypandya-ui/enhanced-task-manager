"""
Main application window — ties all components together.
"""

import psutil
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QVBoxLayout, QWidget,
    QMenuBar, QToolBar, QLabel, QSpinBox, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import QTimer, Qt, QSettings
from PyQt6.QtGui import QAction, QKeySequence, QShortcut, QIcon

from core.process_manager import ProcessManager, PerformanceCollector
from core.suppression_manager import SuppressionManager
from core.startup_manager import StartupManager
from core.network_monitor import NetworkMonitor
from core.security_checker import SecurityChecker

from ui.process_table import ProcessTableWidget
from ui.performance_tab import PerformanceTab
from ui.startup_tab import StartupTab
from ui.network_tab import NetworkTab
from ui.suppression_tab import SuppressionTab
from ui.security_tab import SecurityTab
from ui.system_tray import SystemTrayIcon
from ui.styles import DARK_THEME, LIGHT_THEME


class MainWindow(QMainWindow):
    """Enhanced Task Manager main window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Enhanced Task Manager")
        self.setMinimumSize(1200, 750)
        self.resize(1400, 850)

        # Settings
        self.settings = QSettings("EnhancedTaskManager", "ETM")
        self._dark_mode = self.settings.value("dark_mode", True, type=bool)
        self._refresh_interval = self.settings.value("refresh_interval", 2000, type=int)
        self._service_refresh_counter = 0

        # Core managers
        self.process_manager = ProcessManager()
        self.perf_collector = PerformanceCollector()
        self.suppression_manager = SuppressionManager()
        self.startup_manager = StartupManager()
        self.network_monitor = NetworkMonitor()
        self.security_checker = SecurityChecker()

        # Initial service map load
        self.process_manager.refresh_services_map()

        # Build UI
        self._build_menu()
        self._build_tabs()
        self._build_statusbar()
        self._setup_shortcuts()
        self._setup_tray()

        # Apply theme
        self._apply_theme()

        # Timers
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_refresh_tick)
        self._refresh_timer.start(self._refresh_interval)

        # Initial data load
        self._on_refresh_tick()
        self.startup_tab.refresh()

    def _build_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        export_action = QAction("Export Process List...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(lambda: self.process_tab._export_csv())
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Alt+F4"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("View")

        theme_action = QAction("Toggle Dark/Light Mode", self)
        theme_action.setShortcut(QKeySequence("Ctrl+T"))
        theme_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(theme_action)

        view_menu.addSeparator()

        # Refresh interval submenu
        interval_menu = view_menu.addMenu("Refresh Interval")
        for label, ms in [("0.5s", 500), ("1s", 1000), ("2s (Default)", 2000),
                          ("5s", 5000), ("10s", 10000)]:
            action = QAction(label, self)
            action.triggered.connect(lambda checked, v=ms: self._set_refresh_interval(v))
            interval_menu.addAction(action)

        # Actions menu
        actions_menu = menubar.addMenu("Actions")

        refresh_action = QAction("Refresh Now", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self._on_refresh_tick)
        actions_menu.addAction(refresh_action)

        actions_menu.addSeparator()

        end_task_action = QAction("End Selected Task", self)
        end_task_action.setShortcut(QKeySequence("Delete"))
        end_task_action.triggered.connect(lambda: self.process_tab._on_end_task())
        actions_menu.addAction(end_task_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Processes tab
        self.process_tab = ProcessTableWidget(
            self.process_manager, self.suppression_manager
        )
        self.process_tab.status_message.connect(self._show_status)
        self.tabs.addTab(self.process_tab, "Processes")

        # Performance tab
        self.perf_tab = PerformanceTab(self.perf_collector)
        self.tabs.addTab(self.perf_tab, "Performance")

        # Startup tab
        self.startup_tab = StartupTab(self.startup_manager)
        self.startup_tab.status_message.connect(self._show_status)
        self.tabs.addTab(self.startup_tab, "Startup")

        # Network tab
        self.network_tab = NetworkTab(self.network_monitor)
        self.network_tab.status_message.connect(self._show_status)
        self.tabs.addTab(self.network_tab, "Network")

        # Security tab
        self.security_tab = SecurityTab(self.security_checker)
        self.security_tab.status_message.connect(self._show_status)
        self.tabs.addTab(self.security_tab, "Security")

        # Suppression tab
        self.suppression_tab = SuppressionTab(self.suppression_manager)
        self.suppression_tab.status_message.connect(self._show_status)
        self.tabs.addTab(self.suppression_tab, "Suppression")

        # Refresh tab-specific data on tab change
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _build_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label, 1)

        self.cpu_status = QLabel("CPU: —%")
        self.cpu_status.setMinimumWidth(100)
        self.status_bar.addPermanentWidget(self.cpu_status)

        self.mem_status = QLabel("RAM: —%")
        self.mem_status.setMinimumWidth(100)
        self.status_bar.addPermanentWidget(self.mem_status)

        self.proc_count_status = QLabel("Processes: —")
        self.proc_count_status.setMinimumWidth(100)
        self.status_bar.addPermanentWidget(self.proc_count_status)

    def _setup_shortcuts(self):
        # Ctrl+F = search
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(self._focus_search)

        # Del = end task (handled via menu action)
        # F5 = refresh (handled via menu action)

    def _setup_tray(self):
        self.tray_icon = SystemTrayIcon(self)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _apply_theme(self):
        theme = DARK_THEME if self._dark_mode else LIGHT_THEME
        self.setStyleSheet(theme)

    def _toggle_theme(self):
        self._dark_mode = not self._dark_mode
        self.settings.setValue("dark_mode", self._dark_mode)
        self._apply_theme()
        mode = "Dark" if self._dark_mode else "Light"
        self._show_status(f"Switched to {mode} mode")

    def _set_refresh_interval(self, ms: int):
        self._refresh_interval = ms
        self.settings.setValue("refresh_interval", ms)
        self._refresh_timer.setInterval(ms)
        self._show_status(f"Refresh interval set to {ms}ms")

    def _on_refresh_tick(self):
        """Called every refresh interval."""
        # Collect performance data
        self.perf_collector.collect()

        # Update status bar
        metrics = self.perf_collector.get_current()
        cpu = metrics['cpu_percent']
        mem = metrics['memory_percent']

        self.cpu_status.setText(f"CPU: {cpu:.0f}%")
        self.mem_status.setText(f"RAM: {mem:.0f}%")

        # Tray icon
        self.tray_icon.update_stats(cpu, mem, metrics['disk_percent'])

        # Refresh service map periodically (every 30 ticks ~ 1 minute at 2s)
        self._service_refresh_counter += 1
        if self._service_refresh_counter >= 30:
            self._service_refresh_counter = 0
            self.process_manager.refresh_services_map()

        # Refresh active tab
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:  # Processes
            self.process_tab.refresh()
            processes = self.process_manager.get_processes()
            self.proc_count_status.setText(f"Processes: {len(processes)}")
        elif current_tab == 1:  # Performance
            self.perf_tab.update_data()
        elif current_tab == 3:  # Network
            self.network_tab.refresh()

    def _on_tab_changed(self, index: int):
        """Handle tab switch — load data for newly active tab."""
        if index == 0:
            self.process_tab.refresh()
        elif index == 1:
            self.perf_tab.update_data()
        elif index == 2:
            self.startup_tab.refresh()
        elif index == 3:
            self.network_tab.refresh()
        elif index == 5:
            self.suppression_tab.refresh()

    def _focus_search(self):
        if self.tabs.currentIndex() == 0:
            self.process_tab.focus_search()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()

    def _show_status(self, msg: str):
        self.status_label.setText(msg)
        # Auto-clear after 5 seconds
        QTimer.singleShot(5000, lambda: self.status_label.setText("Ready"))

    def _show_about(self):
        QMessageBox.about(
            self,
            "About Enhanced Task Manager",
            "<h2>Enhanced Task Manager</h2>"
            "<p>A comprehensive Windows process manager with:</p>"
            "<ul>"
            "<li>Human-readable process descriptions</li>"
            "<li>Safety-tiered process termination</li>"
            "<li>Process respawn suppression</li>"
            "<li>Real-time performance dashboard</li>"
            "<li>Startup item management</li>"
            "<li>Network connection monitoring</li>"
            "<li>Digital signature verification</li>"
            "</ul>"
            "<p>Built with Python, PyQt6, and psutil.</p>"
        )

    def closeEvent(self, event):
        """Handle window close — minimize to tray instead."""
        self.hide()
        self.tray_icon.showMessage(
            "Enhanced Task Manager",
            "Running in system tray. Double-click to restore.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )
        event.ignore()

    def force_quit(self):
        """Actually quit the application."""
        self.tray_icon.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()
