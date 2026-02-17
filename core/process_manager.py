"""
Core process manager — collects detailed process information using psutil, WMI, and Win32 API.
"""

import os
import time
import threading
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

import psutil

from core.process_descriptions import (
    resolve_description, resolve_category, resolve_kill_impact,
    get_file_company, get_file_description
)
from core.safety_tiers import classify_process, SafetyInfo, SafetyTier


@dataclass
class ProcessInfo:
    pid: int = 0
    name: str = ""
    description: str = ""
    company: str = ""
    category: str = "unknown"
    safety: SafetyTier = SafetyTier.GREEN
    safety_info: Optional[SafetyInfo] = None
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    disk_read_speed: float = 0.0   # bytes/sec
    disk_write_speed: float = 0.0  # bytes/sec
    net_sent_bytes: int = 0
    net_recv_bytes: int = 0
    net_sent_speed: float = 0.0    # bytes/sec
    net_recv_speed: float = 0.0    # bytes/sec
    gpu_percent: float = 0.0
    threads: int = 0
    handles: int = 0
    status: str = ""
    username: str = ""
    start_time: Optional[datetime] = None
    exe_path: str = ""
    cmdline: str = ""
    services: list = field(default_factory=list)
    kill_impact: str = ""
    is_elevated: bool = False
    is_suspended: bool = False


class ProcessManager:
    """Collects and manages process information."""

    def __init__(self):
        self._processes: dict[int, ProcessInfo] = {}
        self._prev_io: dict[int, tuple] = {}  # pid -> (read_bytes, write_bytes, timestamp)
        self._prev_net: dict[int, tuple] = {}  # pid -> (sent, recv, timestamp)
        self._lock = threading.Lock()
        self._svchost_services: dict[int, list] = {}
        self._gpu_available = False
        self._init_gpu()

    def _init_gpu(self):
        """Check if GPU monitoring is available."""
        try:
            import pynvml
            pynvml.nvmlInit()
            self._gpu_available = True
        except Exception:
            self._gpu_available = False

    def _get_svchost_services(self) -> dict[int, list]:
        """Map svchost PIDs to their hosted service names using WMI."""
        result = {}
        try:
            import wmi
            c = wmi.WMI()
            for service in c.Win32_Service():
                pid = service.ProcessId
                if pid and pid > 0:
                    if pid not in result:
                        result[pid] = []
                    result[pid].append(service.Name)
        except Exception:
            pass
        return result

    def refresh_services_map(self):
        """Refresh the svchost-to-services mapping (call periodically, not every refresh)."""
        self._svchost_services = self._get_svchost_services()

    def collect_processes(self) -> dict[int, ProcessInfo]:
        """Collect information about all running processes."""
        now = time.time()
        new_processes = {}

        for proc in psutil.process_iter([
            'pid', 'name', 'cpu_percent', 'memory_info', 'memory_percent',
            'io_counters', 'num_threads', 'num_handles', 'status',
            'username', 'create_time', 'exe', 'cmdline', 'ppid'
        ]):
            try:
                pinfo = proc.info
                pid = pinfo['pid']
                name = pinfo['name'] or ""
                if not name:
                    continue  # Skip processes with no name
                exe_path = pinfo.get('exe') or ""

                # Build ProcessInfo
                pi = ProcessInfo()
                pi.pid = pid
                pi.name = name
                pi.exe_path = exe_path

                # CPU & Memory
                pi.cpu_percent = pinfo.get('cpu_percent') or 0.0
                mem_info = pinfo.get('memory_info')
                if mem_info:
                    pi.memory_mb = mem_info.rss / (1024 * 1024)
                pi.memory_percent = pinfo.get('memory_percent') or 0.0

                # Disk I/O with rate calculation
                io = pinfo.get('io_counters')
                if io:
                    pi.disk_read_bytes = io.read_bytes
                    pi.disk_write_bytes = io.write_bytes
                    prev = self._prev_io.get(pid)
                    if prev:
                        dt = now - prev[2]
                        if dt > 0:
                            pi.disk_read_speed = max(0, (io.read_bytes - prev[0]) / dt)
                            pi.disk_write_speed = max(0, (io.write_bytes - prev[1]) / dt)
                    self._prev_io[pid] = (io.read_bytes, io.write_bytes, now)

                # Thread/handle counts
                pi.threads = pinfo.get('num_threads') or 0
                pi.handles = pinfo.get('num_handles') or 0

                # Status
                pi.status = pinfo.get('status') or ""
                pi.is_suspended = pi.status == psutil.STATUS_STOPPED

                # Username
                pi.username = pinfo.get('username') or ""

                # Start time
                create_time = pinfo.get('create_time')
                if create_time:
                    try:
                        pi.start_time = datetime.fromtimestamp(create_time)
                    except (OSError, ValueError):
                        pass

                # Command line
                cmdline = pinfo.get('cmdline')
                if cmdline:
                    pi.cmdline = " ".join(cmdline)

                # Services (for svchost)
                if name.lower() == "svchost.exe" and pid in self._svchost_services:
                    pi.services = self._svchost_services[pid]

                # Get parent process name for context
                parent_name = ""
                ppid = pinfo.get('ppid')
                if ppid and ppid > 0:
                    try:
                        parent = psutil.Process(ppid)
                        parent_name = parent.name() or ""
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                # Resolve description, category, safety, kill impact
                pi.description = resolve_description(
                    name, exe_path, pi.services,
                    cmdline=pi.cmdline,
                    parent_name=parent_name,
                    parent_pid=ppid or 0,
                )
                pi.category = resolve_category(name)
                pi.kill_impact = resolve_kill_impact(name)
                pi.safety_info = classify_process(name, pid)
                pi.safety = pi.safety_info.tier

                # Company from exe metadata
                if exe_path:
                    company = get_file_company(exe_path)
                    if company:
                        pi.company = company

                # If category is unknown but we have a company, try to classify
                if pi.category == "unknown":
                    if pi.username and ("SYSTEM" in pi.username.upper() or
                                        "LOCAL SERVICE" in pi.username.upper() or
                                        "NETWORK SERVICE" in pi.username.upper()):
                        pi.category = "windows_service"
                    else:
                        pi.category = "user_app"

                new_processes[pid] = pi

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Clean up stale I/O tracking
        active_pids = set(new_processes.keys())
        stale = set(self._prev_io.keys()) - active_pids
        for pid in stale:
            del self._prev_io[pid]

        with self._lock:
            self._processes = new_processes

        return new_processes

    def get_processes(self) -> dict[int, ProcessInfo]:
        """Get the last collected process data."""
        with self._lock:
            return dict(self._processes)

    def kill_process(self, pid: int, force: bool = False) -> tuple[bool, str]:
        """Kill a process. Returns (success, message)."""
        try:
            proc = psutil.Process(pid)
            name = proc.name()

            safety = classify_process(name, pid)
            if safety.tier == SafetyTier.RED and not force:
                return False, f"BLOCKED: {name} is system critical. {safety.warning}"

            if force:
                proc.kill()
            else:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()

            return True, f"Successfully terminated {name} (PID {pid})"

        except psutil.NoSuchProcess:
            return True, "Process already terminated."
        except psutil.AccessDenied:
            return False, f"Access denied. Try running as Administrator."
        except Exception as e:
            return False, f"Failed to terminate process: {e}"

    def kill_process_tree(self, pid: int) -> tuple[bool, str]:
        """Kill a process and all its children."""
        try:
            parent = psutil.Process(pid)
            name = parent.name()
            children = parent.children(recursive=True)

            safety = classify_process(name, pid)
            if safety.tier == SafetyTier.RED:
                return False, f"BLOCKED: {name} is system critical. {safety.warning}"

            for child in children:
                try:
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            parent.terminate()

            gone, alive = psutil.wait_procs(children + [parent], timeout=3)
            for p in alive:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            return True, f"Terminated {name} and {len(children)} child processes."

        except psutil.NoSuchProcess:
            return True, "Process already terminated."
        except psutil.AccessDenied:
            return False, "Access denied. Try running as Administrator."
        except Exception as e:
            return False, f"Failed: {e}"

    def set_priority(self, pid: int, priority: int) -> tuple[bool, str]:
        """Set process priority. priority is a psutil constant."""
        try:
            proc = psutil.Process(pid)
            proc.nice(priority)
            return True, f"Priority set for {proc.name()}"
        except psutil.AccessDenied:
            return False, "Access denied."
        except Exception as e:
            return False, str(e)

    def set_affinity(self, pid: int, cpus: list[int]) -> tuple[bool, str]:
        """Set CPU affinity for a process."""
        try:
            proc = psutil.Process(pid)
            proc.cpu_affinity(cpus)
            return True, f"Affinity set for {proc.name()}"
        except psutil.AccessDenied:
            return False, "Access denied."
        except Exception as e:
            return False, str(e)

    def get_process_by_pid(self, pid: int) -> Optional[ProcessInfo]:
        """Get a specific process info."""
        with self._lock:
            return self._processes.get(pid)

    def check_respawn(self, name: str, original_pid: int, delay: float = 3.0) -> Optional[int]:
        """Check if a process respawns after being killed. Returns new PID if found."""
        time.sleep(delay)
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if (proc.info['name'] and
                    proc.info['name'].lower() == name.lower() and
                    proc.info['pid'] != original_pid):
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None


class PerformanceCollector:
    """Collects system-wide performance metrics."""

    def __init__(self, history_minutes: int = 60):
        self.history_minutes = history_minutes
        self.max_points = history_minutes * 30  # At 2s interval
        self.cpu_history: list[tuple[float, float]] = []  # (timestamp, percent)
        self.memory_history: list[tuple[float, float]] = []
        self.disk_history: list[tuple[float, tuple]] = []  # (timestamp, (read_speed, write_speed))
        self.net_history: list[tuple[float, tuple]] = []
        self.gpu_history: list[tuple[float, float]] = []
        self._prev_disk = None
        self._prev_net = None
        self._prev_time = None
        self._lock = threading.Lock()

    def collect(self):
        """Collect a single snapshot of system-wide performance."""
        now = time.time()

        # CPU
        cpu = psutil.cpu_percent(interval=0)

        # Memory
        mem = psutil.virtual_memory()

        # Disk I/O
        disk = psutil.disk_io_counters()
        disk_read_speed = 0.0
        disk_write_speed = 0.0
        if self._prev_disk and self._prev_time:
            dt = now - self._prev_time
            if dt > 0:
                disk_read_speed = max(0, (disk.read_bytes - self._prev_disk.read_bytes) / dt)
                disk_write_speed = max(0, (disk.write_bytes - self._prev_disk.write_bytes) / dt)

        # Network I/O
        net = psutil.net_io_counters()
        net_sent_speed = 0.0
        net_recv_speed = 0.0
        if self._prev_net and self._prev_time:
            dt = now - self._prev_time
            if dt > 0:
                net_sent_speed = max(0, (net.bytes_sent - self._prev_net.bytes_sent) / dt)
                net_recv_speed = max(0, (net.bytes_recv - self._prev_net.bytes_recv) / dt)

        self._prev_disk = disk
        self._prev_net = net
        self._prev_time = now

        with self._lock:
            self.cpu_history.append((now, cpu))
            self.memory_history.append((now, mem.percent))
            self.disk_history.append((now, (disk_read_speed, disk_write_speed)))
            self.net_history.append((now, (net_sent_speed, net_recv_speed)))

            # Trim history
            cutoff = now - (self.history_minutes * 60)
            self.cpu_history = [(t, v) for t, v in self.cpu_history if t > cutoff]
            self.memory_history = [(t, v) for t, v in self.memory_history if t > cutoff]
            self.disk_history = [(t, v) for t, v in self.disk_history if t > cutoff]
            self.net_history = [(t, v) for t, v in self.net_history if t > cutoff]

    def get_current(self) -> dict:
        """Get current system metrics."""
        cpu = psutil.cpu_percent(interval=0)
        cpu_freq = psutil.cpu_freq()
        cpu_count = psutil.cpu_count()
        cpu_count_phys = psutil.cpu_count(logical=False)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu_percent": cpu,
            "cpu_freq_mhz": cpu_freq.current if cpu_freq else 0,
            "cpu_count": cpu_count,
            "cpu_count_physical": cpu_count_phys,
            "memory_total_gb": mem.total / (1024 ** 3),
            "memory_used_gb": mem.used / (1024 ** 3),
            "memory_percent": mem.percent,
            "disk_total_gb": disk.total / (1024 ** 3),
            "disk_used_gb": disk.used / (1024 ** 3),
            "disk_percent": disk.percent,
        }

    def get_top_processes(self, metric: str = "cpu", n: int = 5) -> list:
        """Get top N processes by a given metric."""
        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            try:
                info = proc.info
                if info['name']:
                    procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if metric == "cpu":
            procs.sort(key=lambda p: p.get('cpu_percent') or 0, reverse=True)
        elif metric == "memory":
            procs.sort(
                key=lambda p: p.get('memory_info').rss if p.get('memory_info') else 0,
                reverse=True,
            )

        return procs[:n]
