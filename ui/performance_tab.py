"""
Performance Dashboard tab — real-time graphs for CPU, RAM, Disk, Network, GPU.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QGroupBox, QSplitter, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QPainterPath
import time
import psutil

from core.process_manager import PerformanceCollector


def format_bytes_speed(bps: float) -> str:
    """Format bytes/sec to human-readable."""
    if bps >= 1024 * 1024 * 1024:
        return f"{bps / (1024**3):.1f} GB/s"
    elif bps >= 1024 * 1024:
        return f"{bps / (1024**2):.1f} MB/s"
    elif bps >= 1024:
        return f"{bps / 1024:.1f} KB/s"
    return f"{bps:.0f} B/s"


class MiniGraph(QWidget):
    """A small real-time line graph widget."""

    def __init__(self, color: str = "#89b4fa", max_val: float = 100.0,
                 label: str = "", parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.max_val = max_val
        self.label = label
        self.data: list[float] = []
        self.max_points = 120  # ~4 minutes at 2s interval
        self.setMinimumHeight(100)
        self.setMinimumWidth(200)

    def add_point(self, value: float):
        self.data.append(value)
        if len(self.data) > self.max_points:
            self.data = self.data[-self.max_points:]
        self.update()

    def paintEvent(self, event):
        if not self.data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor("#181825"))

        # Grid lines
        painter.setPen(QPen(QColor("#313244"), 1))
        for i in range(1, 4):
            y = int(h * i / 4)
            painter.drawLine(0, y, w, y)

        # Data line
        if len(self.data) < 2:
            return

        pen = QPen(self.color, 2)
        painter.setPen(pen)

        # Fill under line
        fill_color = QColor(self.color)
        fill_color.setAlpha(30)

        path = QPainterPath()
        points_count = len(self.data)
        x_step = w / max(self.max_points - 1, 1)

        start_x = w - (points_count - 1) * x_step

        first_y = h - (self.data[0] / max(self.max_val, 0.001)) * h
        path.moveTo(start_x, h)
        path.lineTo(start_x, first_y)

        for i, val in enumerate(self.data):
            x = start_x + i * x_step
            y = h - (val / max(self.max_val, 0.001)) * h
            y = max(0, min(h, y))
            path.lineTo(x, y)

        path.lineTo(start_x + (points_count - 1) * x_step, h)
        path.closeSubpath()

        painter.fillPath(path, QBrush(fill_color))

        # Draw line on top
        painter.setPen(pen)
        for i in range(1, points_count):
            x1 = start_x + (i - 1) * x_step
            y1 = h - (self.data[i - 1] / max(self.max_val, 0.001)) * h
            x2 = start_x + i * x_step
            y2 = h - (self.data[i] / max(self.max_val, 0.001)) * h
            y1 = max(0, min(h, y1))
            y2 = max(0, min(h, y2))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Current value text
        current = self.data[-1] if self.data else 0
        painter.setPen(QPen(QColor("#cdd6f4")))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(5, 15, f"{self.label}: {current:.1f}%")

        painter.end()


class DualMiniGraph(QWidget):
    """A mini graph with two data series (e.g., read/write, send/recv)."""

    def __init__(self, color1: str = "#89b4fa", color2: str = "#a6e3a1",
                 label1: str = "", label2: str = "", parent=None):
        super().__init__(parent)
        self.color1 = QColor(color1)
        self.color2 = QColor(color2)
        self.label1 = label1
        self.label2 = label2
        self.data1: list[float] = []
        self.data2: list[float] = []
        self.max_val = 1.0
        self.max_points = 120
        self.setMinimumHeight(100)
        self.setMinimumWidth(200)

    def add_points(self, val1: float, val2: float):
        self.data1.append(val1)
        self.data2.append(val2)
        if len(self.data1) > self.max_points:
            self.data1 = self.data1[-self.max_points:]
            self.data2 = self.data2[-self.max_points:]
        # Auto-scale
        all_vals = self.data1 + self.data2
        if all_vals:
            self.max_val = max(max(all_vals) * 1.2, 1.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#181825"))

        painter.setPen(QPen(QColor("#313244"), 1))
        for i in range(1, 4):
            y = int(h * i / 4)
            painter.drawLine(0, y, w, y)

        for data, color in [(self.data1, self.color1), (self.data2, self.color2)]:
            if len(data) < 2:
                continue
            pen = QPen(color, 2)
            painter.setPen(pen)
            points_count = len(data)
            x_step = w / max(self.max_points - 1, 1)
            start_x = w - (points_count - 1) * x_step

            for i in range(1, points_count):
                x1 = start_x + (i - 1) * x_step
                y1 = h - (data[i - 1] / max(self.max_val, 0.001)) * h
                x2 = start_x + i * x_step
                y2 = h - (data[i] / max(self.max_val, 0.001)) * h
                y1 = max(0, min(h, y1))
                y2 = max(0, min(h, y2))
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Labels
        painter.setFont(QFont("Segoe UI", 9))
        cur1 = self.data1[-1] if self.data1 else 0
        cur2 = self.data2[-1] if self.data2 else 0
        painter.setPen(QPen(self.color1))
        painter.drawText(5, 15, f"{self.label1}: {format_bytes_speed(cur1)}")
        painter.setPen(QPen(self.color2))
        painter.drawText(5, 30, f"{self.label2}: {format_bytes_speed(cur2)}")

        painter.end()


class MetricCard(QFrame):
    """A card showing a single metric with label and value."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("subtitle")
        layout.addWidget(self.title_label)

        self.value_label = QLabel("—")
        self.value_label.setObjectName("metricValue")
        layout.addWidget(self.value_label)

        self.detail_label = QLabel("")
        self.detail_label.setObjectName("subtitle")
        layout.addWidget(self.detail_label)

    def set_value(self, value: str, detail: str = ""):
        self.value_label.setText(value)
        if detail:
            self.detail_label.setText(detail)


class PerformanceTab(QWidget):
    """Performance dashboard with real-time graphs and metrics."""

    def __init__(self, perf_collector: PerformanceCollector, parent=None):
        super().__init__(parent)
        self.collector = perf_collector
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Top metrics row
        metrics_layout = QHBoxLayout()

        self.cpu_card = MetricCard("CPU Usage")
        metrics_layout.addWidget(self.cpu_card)

        self.mem_card = MetricCard("Memory Usage")
        metrics_layout.addWidget(self.mem_card)

        self.disk_card = MetricCard("Disk Usage")
        metrics_layout.addWidget(self.disk_card)

        self.net_card = MetricCard("Network")
        metrics_layout.addWidget(self.net_card)

        layout.addLayout(metrics_layout)

        # Graphs
        graphs_layout = QGridLayout()
        graphs_layout.setSpacing(8)

        # CPU graph
        cpu_group = QGroupBox("CPU")
        cpu_gl = QVBoxLayout(cpu_group)
        self.cpu_graph = MiniGraph(color="#89b4fa", label="CPU")
        cpu_gl.addWidget(self.cpu_graph)
        graphs_layout.addWidget(cpu_group, 0, 0)

        # Memory graph
        mem_group = QGroupBox("Memory")
        mem_gl = QVBoxLayout(mem_group)
        self.mem_graph = MiniGraph(color="#a6e3a1", label="RAM")
        mem_gl.addWidget(self.mem_graph)
        graphs_layout.addWidget(mem_group, 0, 1)

        # Disk graph
        disk_group = QGroupBox("Disk I/O")
        disk_gl = QVBoxLayout(disk_group)
        self.disk_graph = DualMiniGraph(
            color1="#89b4fa", color2="#f9e2af",
            label1="Read", label2="Write"
        )
        disk_gl.addWidget(self.disk_graph)
        graphs_layout.addWidget(disk_group, 1, 0)

        # Network graph
        net_group = QGroupBox("Network")
        net_gl = QVBoxLayout(net_group)
        self.net_graph = DualMiniGraph(
            color1="#89b4fa", color2="#a6e3a1",
            label1="Send", label2="Recv"
        )
        net_gl.addWidget(self.net_graph)
        graphs_layout.addWidget(net_group, 1, 1)

        layout.addLayout(graphs_layout)

        # Top processes section
        top_group = QGroupBox("Top Resource Consumers")
        top_layout = QHBoxLayout(top_group)

        # Top CPU
        cpu_top_layout = QVBoxLayout()
        cpu_top_label = QLabel("Top CPU")
        cpu_top_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        cpu_top_layout.addWidget(cpu_top_label)
        self.top_cpu_labels = []
        for i in range(5):
            lbl = QLabel("")
            lbl.setObjectName("subtitle")
            cpu_top_layout.addWidget(lbl)
            self.top_cpu_labels.append(lbl)
        cpu_top_layout.addStretch()
        top_layout.addLayout(cpu_top_layout)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #313244;")
        top_layout.addWidget(sep)

        # Top Memory
        mem_top_layout = QVBoxLayout()
        mem_top_label = QLabel("Top Memory")
        mem_top_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        mem_top_layout.addWidget(mem_top_label)
        self.top_mem_labels = []
        for i in range(5):
            lbl = QLabel("")
            lbl.setObjectName("subtitle")
            mem_top_layout.addWidget(lbl)
            self.top_mem_labels.append(lbl)
        mem_top_layout.addStretch()
        top_layout.addLayout(mem_top_layout)

        layout.addWidget(top_group)

    def update_data(self):
        """Update all performance displays."""
        metrics = self.collector.get_current()

        # Update cards
        self.cpu_card.set_value(
            f"{metrics['cpu_percent']:.0f}%",
            f"{metrics['cpu_count_physical']}C/{metrics['cpu_count']}T @ {metrics['cpu_freq_mhz']:.0f} MHz"
        )
        self.mem_card.set_value(
            f"{metrics['memory_percent']:.0f}%",
            f"{metrics['memory_used_gb']:.1f} / {metrics['memory_total_gb']:.1f} GB"
        )
        self.disk_card.set_value(
            f"{metrics['disk_percent']:.0f}%",
            f"{metrics['disk_used_gb']:.0f} / {metrics['disk_total_gb']:.0f} GB"
        )

        # Update graphs
        self.cpu_graph.add_point(metrics['cpu_percent'])
        self.mem_graph.add_point(metrics['memory_percent'])

        with self.collector._lock:
            if self.collector.disk_history:
                dr, dw = self.collector.disk_history[-1][1]
                self.disk_graph.add_points(dr, dw)

            if self.collector.net_history:
                ns, nr = self.collector.net_history[-1][1]
                self.net_graph.add_points(ns, nr)
                self.net_card.set_value(
                    f"↑ {format_bytes_speed(ns)}",
                    f"↓ {format_bytes_speed(nr)}"
                )

        # Update top processes
        top_cpu = self.collector.get_top_processes("cpu", 5)
        for i, proc in enumerate(top_cpu):
            if i < len(self.top_cpu_labels):
                cpu_val = proc.get('cpu_percent', 0) or 0
                self.top_cpu_labels[i].setText(
                    f"{proc['name']}: {cpu_val:.1f}%"
                )

        top_mem = self.collector.get_top_processes("memory", 5)
        for i, proc in enumerate(top_mem):
            if i < len(self.top_mem_labels):
                mem = proc.get('memory_info')
                mb = mem.rss / (1024 * 1024) if mem else 0
                self.top_mem_labels[i].setText(
                    f"{proc['name']}: {mb:.0f} MB"
                )
