"""
Network Activity Monitor — per-process network connections with reverse DNS and threat detection.
"""

import socket
import threading
from dataclasses import dataclass
from typing import Optional
from functools import lru_cache

import psutil


@dataclass
class ConnectionInfo:
    pid: int
    process_name: str
    local_addr: str
    local_port: int
    remote_addr: str
    remote_port: int
    protocol: str    # "TCP" or "UDP"
    state: str       # "ESTABLISHED", "LISTEN", etc.
    remote_hostname: str = ""
    is_suspicious: bool = False
    suspicion_reason: str = ""


# Ports commonly associated with malware / C2 communication
_SUSPICIOUS_PORTS = {
    4444, 5555, 6666, 7777, 8888, 9999,  # Common reverse shell ports
    1234, 31337,                           # Classic backdoor ports
    3389,                                   # RDP (suspicious if unexpected)
    445,                                    # SMB (suspicious if external)
    5900, 5901,                            # VNC
    8080, 8443, 8081,                      # Alt HTTP (suspicious for non-browsers)
    6667, 6697,                            # IRC (common for C2)
    1337, 1338,                            # Hacker convention
}

# Processes that legitimately use many network connections
_LEGIT_NETWORK_PROCS = {
    'chrome.exe', 'firefox.exe', 'msedge.exe', 'brave.exe', 'opera.exe',
    'svchost.exe', 'teams.exe', 'slack.exe', 'discord.exe', 'zoom.exe',
    'spotify.exe', 'steam.exe', 'onedrive.exe', 'dropbox.exe',
    'code.exe', 'outlook.exe', 'thunderbird.exe',
}

# Suspicious locations for executables
_SUSPICIOUS_PATHS = [
    '\\temp\\', '\\tmp\\', '\\appdata\\local\\temp\\',
    '\\downloads\\', '\\desktop\\',
    '\\programdata\\', '\\public\\',
]


class NetworkMonitor:
    """Monitors per-process network connections."""

    def __init__(self):
        self._dns_cache: dict[str, str] = {}
        self._lock = threading.Lock()

    def get_connections(self) -> list[ConnectionInfo]:
        """Get all active network connections with process info."""
        connections = []
        proc_names = {}

        # Cache process names
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc_names[proc.info['pid']] = proc.info['name'] or ""
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # TCP connections
        try:
            for conn in psutil.net_connections(kind='tcp'):
                if conn.pid and conn.pid > 0:
                    ci = self._build_connection(conn, proc_names, "TCP")
                    if ci:
                        connections.append(ci)
        except (psutil.AccessDenied, PermissionError):
            pass

        # UDP connections
        try:
            for conn in psutil.net_connections(kind='udp'):
                if conn.pid and conn.pid > 0:
                    ci = self._build_connection(conn, proc_names, "UDP")
                    if ci:
                        connections.append(ci)
        except (psutil.AccessDenied, PermissionError):
            pass

        return connections

    def _build_connection(self, conn, proc_names: dict, protocol: str) -> Optional[ConnectionInfo]:
        """Build a ConnectionInfo from a psutil connection."""
        pid = conn.pid
        name = proc_names.get(pid, "")

        local_addr = conn.laddr.ip if conn.laddr else ""
        local_port = conn.laddr.port if conn.laddr else 0
        remote_addr = conn.raddr.ip if conn.raddr else ""
        remote_port = conn.raddr.port if conn.raddr else 0
        state = conn.status if hasattr(conn, 'status') else ""

        ci = ConnectionInfo(
            pid=pid,
            process_name=name,
            local_addr=local_addr,
            local_port=local_port,
            remote_addr=remote_addr,
            remote_port=remote_port,
            protocol=protocol,
            state=state,
        )

        # Reverse DNS
        if remote_addr and remote_addr not in ("", "0.0.0.0", "::", "127.0.0.1", "::1"):
            ci.remote_hostname = self._resolve_dns(remote_addr)

        # Suspicious connection detection
        is_suspicious, reason = self._check_suspicious(ci)
        ci.is_suspicious = is_suspicious
        ci.suspicion_reason = reason

        return ci

    def _resolve_dns(self, ip: str) -> str:
        """Reverse DNS lookup with caching."""
        with self._lock:
            if ip in self._dns_cache:
                return self._dns_cache[ip]

        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror, OSError):
            hostname = ""

        with self._lock:
            self._dns_cache[ip] = hostname

        return hostname

    def _check_suspicious(self, conn: ConnectionInfo) -> tuple[bool, str]:
        """Check if a connection looks suspicious."""
        reasons = []

        # Check suspicious ports
        if conn.remote_port in _SUSPICIOUS_PORTS:
            name_lower = conn.process_name.lower()
            if name_lower not in _LEGIT_NETWORK_PROCS:
                reasons.append(f"Suspicious port {conn.remote_port}")

        # Check if process is running from suspicious location
        if conn.process_name:
            try:
                proc = psutil.Process(conn.pid)
                exe = proc.exe()
                if exe:
                    exe_lower = exe.lower()
                    for spath in _SUSPICIOUS_PATHS:
                        if spath in exe_lower:
                            reasons.append(f"Process running from suspicious location")
                            break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Non-browser process on IRC port
        if conn.remote_port in (6667, 6697):
            if conn.process_name.lower() not in ('hexchat.exe', 'mirc.exe', 'irssi.exe'):
                reasons.append("IRC port (commonly used for C2 communication)")

        if reasons:
            return True, "; ".join(reasons)
        return False, ""

    def get_connections_by_pid(self, pid: int) -> list[ConnectionInfo]:
        """Get connections for a specific process."""
        return [c for c in self.get_connections() if c.pid == pid]

    def get_suspicious_connections(self) -> list[ConnectionInfo]:
        """Get only suspicious connections."""
        return [c for c in self.get_connections() if c.is_suspicious]
