"""
Safety tier system for process termination.
🟢 GREEN  — Safe to kill (user apps, browsers, etc.)
🟡 YELLOW — Caution (background services, may affect functionality)
🔴 RED    — System Critical (protected, killing may crash Windows)
"""

from enum import Enum
from typing import NamedTuple
from core.process_descriptions import get_process_info


class SafetyTier(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class SafetyInfo(NamedTuple):
    tier: SafetyTier
    label: str
    warning: str
    can_kill: bool  # Whether the UI should allow termination


# Category-to-tier mapping
_CATEGORY_TIERS = {
    "system_critical": SafetyTier.RED,
    "windows_service": SafetyTier.YELLOW,
    "user_app": SafetyTier.GREEN,
    "background_app": SafetyTier.GREEN,
    "startup_item": SafetyTier.GREEN,
    "unknown": SafetyTier.GREEN,
}

# Processes that are ALWAYS red-tier regardless of DB
_ALWAYS_CRITICAL = {
    "system", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "lsaiso.exe", "dwm.exe", "ntoskrnl.exe",
    "registry.exe", "memory_compression", "trustedinstaller.exe",
    "fontdrvhost.exe",
}

# Yellow overrides — services that aren't critical but need caution
_CAUTION_OVERRIDES = {
    "explorer.exe", "spoolsv.exe", "searchindexer.exe", "audiodg.exe",
    "msmpeng.exe", "securityhealthservice.exe", "wlanext.exe",
    "nissrv.exe", "wudfhost.exe",
}


def classify_process(proc_name: str, pid: int = 0) -> SafetyInfo:
    """Classify a process into a safety tier for termination."""
    name_lower = proc_name.lower()

    # PID 0 (System Idle) and PID 4 (System) are always critical
    if pid in (0, 4):
        return SafetyInfo(
            tier=SafetyTier.RED,
            label="System Critical",
            warning="Core operating system process. Cannot be terminated.",
            can_kill=False,
        )

    # Check hardcoded critical list
    if name_lower in _ALWAYS_CRITICAL:
        info = get_process_info(name_lower)
        warning = ""
        if info:
            warning = info.get("kill_warning", "System critical process. Terminating may crash Windows.")
        else:
            warning = "System critical process. Terminating may crash Windows."
        return SafetyInfo(
            tier=SafetyTier.RED,
            label="System Critical",
            warning=warning,
            can_kill=False,
        )

    # Check caution overrides
    if name_lower in _CAUTION_OVERRIDES:
        info = get_process_info(name_lower)
        warning = ""
        if info:
            warning = info.get("kill_warning", "This service may affect system functionality.")
        else:
            warning = "This service may affect system functionality."
        return SafetyInfo(
            tier=SafetyTier.YELLOW,
            label="Caution",
            warning=warning,
            can_kill=True,
        )

    # Check database
    info = get_process_info(name_lower)
    if info:
        category = info.get("category", "unknown")
        safe = info.get("safe_to_kill", True)
        warning = info.get("kill_warning", "")

        if not safe and category == "system_critical":
            return SafetyInfo(
                tier=SafetyTier.RED,
                label="System Critical",
                warning=warning or "System critical process.",
                can_kill=False,
            )
        elif not safe:
            return SafetyInfo(
                tier=SafetyTier.YELLOW,
                label="Caution",
                warning=warning or "This process provides important functionality.",
                can_kill=True,
            )
        else:
            tier = _CATEGORY_TIERS.get(category, SafetyTier.GREEN)
            if tier == SafetyTier.YELLOW:
                return SafetyInfo(
                    tier=SafetyTier.YELLOW,
                    label="Caution",
                    warning=warning or "Windows service — may affect functionality.",
                    can_kill=True,
                )
            return SafetyInfo(
                tier=SafetyTier.GREEN,
                label="Safe",
                warning="",
                can_kill=True,
            )

    # Default: unknown processes are green (user can kill)
    return SafetyInfo(
        tier=SafetyTier.GREEN,
        label="Safe",
        warning="",
        can_kill=True,
    )


def get_tier_color(tier: SafetyTier) -> str:
    """Get the hex color for a safety tier."""
    return {
        SafetyTier.GREEN: "#4CAF50",
        SafetyTier.YELLOW: "#FF9800",
        SafetyTier.RED: "#F44336",
    }[tier]


def get_tier_emoji(tier: SafetyTier) -> str:
    """Get the emoji indicator for a safety tier."""
    return {
        SafetyTier.GREEN: "🟢",
        SafetyTier.YELLOW: "🟡",
        SafetyTier.RED: "🔴",
    }[tier]
