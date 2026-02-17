"""
Enhanced Task Manager — Entry point with admin elevation.
"""

import sys
import os
import ctypes


def is_admin() -> bool:
    """Check if the current process has admin privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    """Re-launch the script with admin privileges via UAC prompt."""
    script = os.path.abspath(sys.argv[0])
    params = " ".join(f'"{a}"' for a in sys.argv[1:])

    try:
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {params}', None, 1
        )
        if ret <= 32:
            print("Failed to elevate privileges. Running without admin rights.")
            return False
        return True
    except Exception as e:
        print(f"Failed to elevate: {e}")
        return False


def main():
    # Request admin elevation for full process visibility
    if not is_admin():
        if run_as_admin():
            sys.exit(0)  # Elevated process launched, exit this one
        # If elevation failed/declined, continue without admin

    # Set up high DPI scaling
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon

    app = QApplication(sys.argv)
    app.setApplicationName("Enhanced Task Manager")
    app.setOrganizationName("EnhancedTaskManager")

    # Prevent quit on last window close (we use system tray)
    app.setQuitOnLastWindowClosed(False)

    from ui.main_window import MainWindow
    window = MainWindow()

    # Override close to allow actual quit from tray
    quit_action = None
    for action in window.tray_icon.contextMenu().actions():
        if action.text() == "Quit":
            action.triggered.disconnect()
            action.triggered.connect(window.force_quit)
            break

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
