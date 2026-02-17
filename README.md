# Enhanced Task Manager

A powerful Windows task manager built with Python and PyQt6 that goes beyond the built-in Windows Task Manager. It provides human-readable process descriptions, safety-tiered termination, real-time performance graphs, startup management, network monitoring, and security analysis.

![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-brightgreen)
![Framework](https://img.shields.io/badge/framework-PyQt6-orange)

## Features

### Process Management
- **Human-readable descriptions** — Every process is described in plain English (e.g., "Google Chrome — Tab renderer displaying a web page")
- **Runtime context** — Descriptions are built from command-line analysis, parent process resolution, and file metadata, so you see *what* a process is actually doing
- **Kill safety ratings** — Color-coded "Safe to Kill?" column tells you the impact of terminating each process
- **17 sortable columns** — PID, name, description, safety tier, kill impact, CPU%, memory, status, priority, threads, handles, disk I/O, network I/O, company, path, command line, services
- **Process tree termination** — Kill a process and all its children
- **Priority & affinity control** — Adjust process priority and CPU core affinity

### Safety-Tiered Termination
| Tier | Color | Behavior |
|------|-------|----------|
| **Safe** | Green | Simple confirmation dialog |
| **Caution** | Yellow | Warning dialog explaining potential impact |
| **Critical** | Red | Hard-blocked with override checkbox for system-critical processes |

### Process Respawn Suppression
Prevent killed processes from coming back:
- Disable Windows services
- Remove startup registry entries
- Disable scheduled tasks
- Block execution via Image File Execution Options (IFEO)
- All suppressions are logged and reversible

### Performance Dashboard
- Real-time line graphs for CPU, RAM, Disk I/O, and Network throughput
- System info cards with core counts, frequency, total memory, and disk usage
- Top 5 resource consumers by CPU and memory
- 60-minute rolling history

### Startup Manager
- Lists startup items from Registry Run keys, Startup folder, and Task Scheduler
- Shows publisher, description, and estimated boot impact
- Enable/disable entries directly from the UI

### Network Monitor
- Per-process TCP/UDP connections with remote addresses and ports
- Reverse DNS lookups with caching
- Suspicious connection detection (uncommon ports, processes running from temp directories)

### Security Scanner
- Digital signature (Authenticode) verification
- Risk assessment based on signature status and file location
- Identifies unsigned or suspiciously located executables

### UI
- **Dark/Light themes** — Catppuccin-inspired color schemes
- **System tray** — Minimize to tray with live CPU usage indicator
- **Search & filter** — Filter by name, PID, description, company, or path
- **Quick presets** — High CPU, High Memory, Network Active, Unsigned
- **CSV export** — Export the filtered process list with all columns
- **Context menu** — Right-click for End Task, Suppress, Open File Location, Search Online, Properties

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+F` | Focus search box |
| `F5` | Refresh process list |
| `Delete` | End selected task |
| `Ctrl+T` | Toggle dark/light theme |
| `Ctrl+E` | Export to CSV |

## Installation

### Prerequisites
- Windows 10/11
- Python 3.10+

### Setup

```bash
git clone https://github.com/neelaypandya-ui/enhanced-task-manager.git
cd enhanced-task-manager
pip install -r requirements.txt
```

### Run

```bash
python main.py
```

The app will request administrator privileges on startup for full process visibility. If declined, it runs with limited access.

## Dependencies

| Package | Purpose |
|---------|---------|
| PyQt6 | GUI framework |
| psutil | Process and system monitoring |
| pywin32 | Windows API access |
| wmi | Windows Management Instrumentation |
| pyqtgraph | Real-time performance graphs |

## Project Structure

```
enhanced-task-manager/
├── main.py                       # Entry point with UAC elevation
├── requirements.txt
├── resources/
│   └── process_db.json           # 150+ process descriptions & safety data
├── core/
│   ├── process_manager.py        # Process collection & performance tracking
│   ├── process_descriptions.py   # Context-aware description resolver
│   ├── safety_tiers.py           # Green/Yellow/Red safety classification
│   ├── suppression_manager.py    # Service, registry, task, IFEO suppression
│   ├── startup_manager.py        # Startup item enumeration & control
│   ├── network_monitor.py        # Per-process connection & threat detection
│   └── security_checker.py       # Digital signature verification
└── ui/
    ├── main_window.py            # Main window with 6 tabs
    ├── process_table.py          # Process list with filtering & sorting
    ├── performance_tab.py        # Real-time graphs & system metrics
    ├── startup_tab.py            # Startup manager UI
    ├── network_tab.py            # Network connections UI
    ├── security_tab.py           # Security scanner UI
    ├── suppression_tab.py        # Suppression log UI
    ├── dialogs.py                # Kill confirm, priority, affinity dialogs
    ├── system_tray.py            # System tray icon with CPU indicator
    └── styles.py                 # Dark & light theme stylesheets
```

## License

MIT
