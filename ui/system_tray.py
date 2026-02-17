"""
System tray icon with quick-glance resource usage.
"""

import psutil
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction
from PyQt6.QtCore import Qt, QTimer


class SystemTrayIcon(QSystemTrayIcon):
    """System tray icon showing CPU usage with a context menu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._create_menu()
        self._update_icon(0)
        self.setToolTip("Enhanced Task Manager")

    def _create_menu(self):
        menu = QMenu()

        self.cpu_action = QAction("CPU: —%")
        self.cpu_action.setEnabled(False)
        menu.addAction(self.cpu_action)

        self.mem_action = QAction("RAM: —%")
        self.mem_action.setEnabled(False)
        menu.addAction(self.mem_action)

        self.disk_action = QAction("Disk: —%")
        self.disk_action.setEnabled(False)
        menu.addAction(self.disk_action)

        menu.addSeparator()

        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def update_stats(self, cpu: float, mem: float, disk: float):
        """Update tray icon and menu with current stats."""
        self._update_icon(cpu)
        self.cpu_action.setText(f"CPU: {cpu:.0f}%")
        self.mem_action.setText(f"RAM: {mem:.0f}%")
        self.disk_action.setText(f"Disk: {disk:.0f}%")
        self.setToolTip(f"CPU: {cpu:.0f}%  |  RAM: {mem:.0f}%  |  Disk: {disk:.0f}%")

    def _update_icon(self, cpu_percent: float):
        """Generate a tray icon showing CPU usage as a colored bar."""
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background circle
        painter.setBrush(QColor("#1e1e2e"))
        painter.setPen(QColor("#45475a"))
        painter.drawRoundedRect(2, 2, size - 4, size - 4, 8, 8)

        # Usage bar
        bar_height = int((size - 12) * min(cpu_percent, 100) / 100)
        if cpu_percent > 80:
            bar_color = QColor("#f38ba8")
        elif cpu_percent > 50:
            bar_color = QColor("#fab387")
        else:
            bar_color = QColor("#a6e3a1")

        painter.setBrush(bar_color)
        painter.setPen(Qt.PenStyle.NoPen)
        y_start = size - 6 - bar_height
        painter.drawRoundedRect(8, y_start, size - 16, bar_height, 3, 3)

        # Text
        painter.setPen(QColor("#cdd6f4"))
        painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        painter.drawText(0, 0, size, size, Qt.AlignmentFlag.AlignCenter, f"{cpu_percent:.0f}")

        painter.end()
        self.setIcon(QIcon(pixmap))

    def _show_window(self):
        parent = self.parent()
        if parent:
            parent.show()
            parent.raise_()
            parent.activateWindow()

    def _quit(self):
        parent = self.parent()
        if parent:
            parent.close()
