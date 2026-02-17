"""
Theme styles for the Enhanced Task Manager — dark mode and light mode.
"""

DARK_THEME = """
QMainWindow, QDialog {
    background-color: #1e1e2e;
    color: #cdd6f4;
}

QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #1e1e2e;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #181825;
    color: #a6adc8;
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #313244;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border-bottom: 2px solid #89b4fa;
}

QTabBar::tab:hover:!selected {
    background-color: #313244;
}

QTableWidget, QTreeWidget, QListWidget {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 4px;
    gridline-color: #313244;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
}

QHeaderView::section {
    background-color: #181825;
    color: #a6adc8;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #313244;
    border-bottom: 1px solid #313244;
    font-weight: bold;
}

QHeaderView::section:hover {
    background-color: #313244;
}

QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 6px 16px;
    border-radius: 6px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #45475a;
    border-color: #585b70;
}

QPushButton:pressed {
    background-color: #585b70;
}

QPushButton#dangerBtn {
    background-color: #45273a;
    border-color: #f38ba8;
    color: #f38ba8;
}

QPushButton#dangerBtn:hover {
    background-color: #5c2d42;
}

QPushButton#primaryBtn {
    background-color: #1e3a5f;
    border-color: #89b4fa;
    color: #89b4fa;
}

QPushButton#primaryBtn:hover {
    background-color: #274b75;
}

QPushButton#successBtn {
    background-color: #1e3b2e;
    border-color: #a6e3a1;
    color: #a6e3a1;
}

QPushButton#successBtn:hover {
    background-color: #274d39;
}

QLineEdit, QSpinBox, QComboBox {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    padding: 6px 10px;
    border-radius: 6px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #89b4fa;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    selection-background-color: #45475a;
}

QScrollBar:vertical {
    background-color: #181825;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #181825;
    height: 10px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 5px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #585b70;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
}

QMenuBar::item:selected {
    background-color: #313244;
}

QMenu {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #45475a;
}

QMenu::separator {
    height: 1px;
    background: #313244;
    margin: 4px 8px;
}

QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 4px 8px;
    border-radius: 4px;
}

QProgressBar {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 3px;
}

QGroupBox {
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

QCheckBox {
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #45475a;
    background-color: #181825;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    border-top: 1px solid #313244;
}

QLabel#sectionTitle {
    font-size: 16px;
    font-weight: bold;
    color: #cdd6f4;
    padding: 4px 0;
}

QLabel#subtitle {
    color: #a6adc8;
    font-size: 12px;
}

QLabel#metricValue {
    font-size: 24px;
    font-weight: bold;
    color: #89b4fa;
}

QLabel#warningLabel {
    color: #fab387;
    font-weight: bold;
}

QLabel#dangerLabel {
    color: #f38ba8;
    font-weight: bold;
}

QLabel#successLabel {
    color: #a6e3a1;
}

QFrame#separator {
    background-color: #313244;
    max-height: 1px;
}

QFrame#card {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 12px;
}
"""

LIGHT_THEME = """
QMainWindow, QDialog {
    background-color: #eff1f5;
    color: #4c4f69;
}

QWidget {
    background-color: #eff1f5;
    color: #4c4f69;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #ccd0da;
    background-color: #eff1f5;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #e6e9ef;
    color: #6c6f85;
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid #ccd0da;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #eff1f5;
    color: #4c4f69;
    border-bottom: 2px solid #1e66f5;
}

QTabBar::tab:hover:!selected {
    background-color: #dce0e8;
}

QTableWidget, QTreeWidget, QListWidget {
    background-color: #ffffff;
    alternate-background-color: #f5f5f9;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 4px;
    gridline-color: #e6e9ef;
    selection-background-color: #bcc0cc;
    selection-color: #4c4f69;
}

QHeaderView::section {
    background-color: #e6e9ef;
    color: #5c5f77;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #ccd0da;
    border-bottom: 1px solid #ccd0da;
    font-weight: bold;
}

QPushButton {
    background-color: #e6e9ef;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    padding: 6px 16px;
    border-radius: 6px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #ccd0da;
}

QPushButton#dangerBtn {
    background-color: #fde2e8;
    border-color: #d20f39;
    color: #d20f39;
}

QPushButton#primaryBtn {
    background-color: #dce5fd;
    border-color: #1e66f5;
    color: #1e66f5;
}

QPushButton#successBtn {
    background-color: #d5f0d5;
    border-color: #40a02b;
    color: #40a02b;
}

QLineEdit, QSpinBox, QComboBox {
    background-color: #ffffff;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    padding: 6px 10px;
    border-radius: 6px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #1e66f5;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    selection-background-color: #dce0e8;
}

QScrollBar:vertical {
    background-color: #eff1f5;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #bcc0cc;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #eff1f5;
    height: 10px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #bcc0cc;
    border-radius: 5px;
    min-width: 30px;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QMenuBar {
    background-color: #e6e9ef;
    color: #4c4f69;
    border-bottom: 1px solid #ccd0da;
}

QMenu {
    background-color: #eff1f5;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #ccd0da;
}

QToolTip {
    background-color: #e6e9ef;
    color: #4c4f69;
    border: 1px solid #ccd0da;
    padding: 4px 8px;
    border-radius: 4px;
}

QProgressBar {
    background-color: #e6e9ef;
    border: 1px solid #ccd0da;
    border-radius: 4px;
    text-align: center;
    color: #4c4f69;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #1e66f5;
    border-radius: 3px;
}

QGroupBox {
    border: 1px solid #ccd0da;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #ccd0da;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #1e66f5;
    border-color: #1e66f5;
}

QStatusBar {
    background-color: #e6e9ef;
    color: #5c5f77;
    border-top: 1px solid #ccd0da;
}

QLabel#sectionTitle {
    font-size: 16px;
    font-weight: bold;
    color: #4c4f69;
}

QLabel#subtitle {
    color: #6c6f85;
    font-size: 12px;
}

QLabel#metricValue {
    font-size: 24px;
    font-weight: bold;
    color: #1e66f5;
}

QLabel#warningLabel {
    color: #df8e1d;
    font-weight: bold;
}

QLabel#dangerLabel {
    color: #d20f39;
    font-weight: bold;
}

QLabel#successLabel {
    color: #40a02b;
}

QFrame#separator {
    background-color: #ccd0da;
    max-height: 1px;
}

QFrame#card {
    background-color: #ffffff;
    border: 1px solid #ccd0da;
    border-radius: 8px;
    padding: 12px;
}
"""
