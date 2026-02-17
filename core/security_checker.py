"""
Process Trust & Security — verifies digital signatures, detects suspicious processes.
"""

import os
import subprocess
from dataclasses import dataclass
from typing import Optional
from functools import lru_cache

import psutil


@dataclass
class SecurityInfo:
    is_signed: bool = False
    signer: str = ""
    is_trusted: bool = False
    suspicious_location: bool = False
    risk_level: str = "unknown"  # "safe", "low", "medium", "high", "unknown"
    risk_reasons: list = None

    def __post_init__(self):
        if self.risk_reasons is None:
            self.risk_reasons = []


# Normal locations for executables
_NORMAL_PATHS = [
    r"c:\windows",
    r"c:\program files",
    r"c:\program files (x86)",
]

# Suspicious locations
_SUSPICIOUS_PATHS = [
    r"\temp",
    r"\tmp",
    r"\appdata\local\temp",
    r"\downloads",
    r"\desktop",
    r"\public",
    r"\recycler",
    r"\$recycle.bin",
]


class SecurityChecker:
    """Checks process security and trustworthiness."""

    def __init__(self, virustotal_api_key: str = ""):
        self.vt_api_key = virustotal_api_key

    @lru_cache(maxsize=512)
    def check_signature(self, exe_path: str) -> tuple[bool, str]:
        """
        Verify if an executable is digitally signed.
        Returns (is_signed, signer_name).
        """
        if not exe_path or not os.path.isfile(exe_path):
            return False, ""

        try:
            # Use PowerShell to check Authenticode signature
            ps_cmd = (
                f'(Get-AuthenticodeSignature "{exe_path}").Status -eq "Valid"'
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=10
            )
            is_signed = result.stdout.strip().lower() == "true"

            signer = ""
            if is_signed:
                ps_cmd2 = (
                    f'(Get-AuthenticodeSignature "{exe_path}").SignerCertificate.Subject'
                )
                result2 = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd2],
                    capture_output=True, text=True, timeout=10
                )
                raw = result2.stdout.strip()
                # Extract CN=... from the subject
                if "CN=" in raw:
                    cn_start = raw.index("CN=") + 3
                    cn_end = raw.find(",", cn_start)
                    if cn_end == -1:
                        cn_end = len(raw)
                    signer = raw[cn_start:cn_end].strip().strip('"')

            return is_signed, signer

        except Exception:
            return False, ""

    def check_location(self, exe_path: str) -> tuple[bool, str]:
        """Check if executable is in a suspicious location."""
        if not exe_path:
            return False, ""

        path_lower = exe_path.lower()
        for spath in _SUSPICIOUS_PATHS:
            if spath in path_lower:
                return True, f"Running from suspicious location: {os.path.dirname(exe_path)}"

        # Check if in a normal location
        in_normal = any(path_lower.startswith(np) for np in _NORMAL_PATHS)
        if not in_normal:
            # Not suspicious per se, just unusual
            return False, ""

        return False, ""

    def assess_risk(self, exe_path: str, proc_name: str = "") -> SecurityInfo:
        """Perform a full security assessment of a process."""
        info = SecurityInfo()
        reasons = []

        # Check signature
        is_signed, signer = self.check_signature(exe_path)
        info.is_signed = is_signed
        info.signer = signer
        info.is_trusted = is_signed  # Simplified: signed = trusted

        if not is_signed and exe_path:
            reasons.append("Executable is not digitally signed")

        # Check location
        suspicious_loc, loc_reason = self.check_location(exe_path)
        info.suspicious_location = suspicious_loc
        if suspicious_loc:
            reasons.append(loc_reason)

        # Determine risk level
        if suspicious_loc and not is_signed:
            info.risk_level = "high"
        elif not is_signed:
            info.risk_level = "medium"
        elif suspicious_loc:
            info.risk_level = "low"
        elif is_signed:
            info.risk_level = "safe"
        else:
            info.risk_level = "unknown"

        info.risk_reasons = reasons
        return info

    def get_unsigned_processes(self) -> list[dict]:
        """Get all running unsigned processes."""
        unsigned = []
        seen_paths = set()

        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                exe = proc.info.get('exe')
                if exe and exe not in seen_paths:
                    seen_paths.add(exe)
                    is_signed, signer = self.check_signature(exe)
                    if not is_signed:
                        unsigned.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'exe': exe,
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return unsigned
