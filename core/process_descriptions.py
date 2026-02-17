"""
Process description resolver — maps process names to human-readable descriptions.
Uses a local JSON database, executable metadata, command line analysis, and
parent process context to build rich, contextual descriptions.
"""

import json
import os
import re
from typing import Optional
from functools import lru_cache


_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "process_db.json")
_process_db: dict = {}


def load_database():
    """Load the process description database from JSON."""
    global _process_db
    try:
        with open(_DB_PATH, "r", encoding="utf-8") as f:
            _process_db = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _process_db = {}


def get_process_info(name: str) -> Optional[dict]:
    """Get known info about a process by its executable name."""
    if not _process_db:
        load_database()
    return _process_db.get(name.lower())


def get_svchost_service_description(service_name: str) -> str:
    """Get a friendly description for a service hosted by svchost.exe."""
    if not _process_db:
        load_database()
    svchost = _process_db.get("svchost.exe", {})
    descs = svchost.get("service_descriptions", {})
    return descs.get(service_name.lower(), f"Windows Service: {service_name}")


@lru_cache(maxsize=1024)
def get_file_description(exe_path: str) -> Optional[str]:
    """Extract the FileDescription from an executable's version info."""
    if not exe_path or not os.path.isfile(exe_path):
        return None
    try:
        import win32api
        info = win32api.GetFileVersionInfo(exe_path, "\\")
        lang_codepage = win32api.GetFileVersionInfo(
            exe_path, "\\VarFileInfo\\Translation"
        )
        if lang_codepage:
            lang, codepage = lang_codepage[0]
            str_info_path = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\FileDescription"
            desc = win32api.GetFileVersionInfo(exe_path, str_info_path)
            if desc and desc.strip():
                return desc.strip()
    except Exception:
        pass
    return None


@lru_cache(maxsize=1024)
def get_file_company(exe_path: str) -> Optional[str]:
    """Extract the CompanyName from an executable's version info."""
    if not exe_path or not os.path.isfile(exe_path):
        return None
    try:
        import win32api
        lang_codepage = win32api.GetFileVersionInfo(
            exe_path, "\\VarFileInfo\\Translation"
        )
        if lang_codepage:
            lang, codepage = lang_codepage[0]
            str_info_path = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\CompanyName"
            company = win32api.GetFileVersionInfo(exe_path, str_info_path)
            if company and company.strip():
                return company.strip()
    except Exception:
        pass
    return None


# Map well-known parent process names to friendly app names
_PARENT_APP_NAMES = {
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Firefox",
    "brave.exe": "Brave Browser",
    "opera.exe": "Opera",
    "code.exe": "VS Code",
    "teams.exe": "Microsoft Teams",
    "slack.exe": "Slack",
    "discord.exe": "Discord",
    "spotify.exe": "Spotify",
    "steam.exe": "Steam",
    "explorer.exe": "Windows Explorer",
    "devenv.exe": "Visual Studio",
    "outlook.exe": "Outlook",
    "cmd.exe": "Command Prompt",
    "powershell.exe": "PowerShell",
    "pwsh.exe": "PowerShell 7",
    "windowsterminal.exe": "Windows Terminal",
    "python.exe": "Python",
    "node.exe": "Node.js",
    "java.exe": "Java",
    "javaw.exe": "Java",
    "cursor.exe": "Cursor Editor",
    "rider64.exe": "JetBrains Rider",
    "idea64.exe": "IntelliJ IDEA",
    "pycharm64.exe": "PyCharm",
    "webstorm64.exe": "WebStorm",
    "sublime_text.exe": "Sublime Text",
    "obs64.exe": "OBS Studio",
    "zoom.exe": "Zoom",
    "docker desktop.exe": "Docker Desktop",
}

# Processes that are "helper" types — describe them by what they serve
_HELPER_PROCESSES = {
    "conhost.exe", "crashpad_handler.exe", "msedgewebview2.exe",
    "runtimebroker.exe", "dllhost.exe", "backgroundtaskhost.exe",
    "werfault.exe", "werfaultsecure.exe",
}


def _get_parent_app_name(parent_name: str) -> str:
    """Get a friendly name for a parent process."""
    return _PARENT_APP_NAMES.get(parent_name.lower(), parent_name)


def _describe_from_cmdline(proc_name: str, cmdline: str, exe_path: str) -> Optional[str]:
    """Try to extract a meaningful description from the command line arguments."""
    name_lower = proc_name.lower()
    cmd_lower = cmdline.lower()

    # --- Chrome / Edge / Brave (Chromium-based) ---
    if name_lower in ("chrome.exe", "msedge.exe", "brave.exe", "opera.exe"):
        browser = _PARENT_APP_NAMES.get(name_lower, proc_name)
        if "--type=renderer" in cmd_lower:
            return f"{browser} — Tab renderer (displays a web page)"
        elif "--type=gpu-process" in cmd_lower:
            return f"{browser} — GPU process (hardware-accelerated graphics)"
        elif "--type=utility" in cmd_lower:
            if "network" in cmd_lower:
                return f"{browser} — Network service (handles all web requests)"
            elif "audio" in cmd_lower:
                return f"{browser} — Audio service (plays sounds from web pages)"
            elif "storage" in cmd_lower:
                return f"{browser} — Storage service (manages cookies, cache, etc.)"
            return f"{browser} — Utility process (background helper)"
        elif "--type=crashpad-handler" in cmd_lower:
            return f"{browser} — Crash reporter (sends crash data if the browser crashes)"
        elif "--type=broker" in cmd_lower:
            return f"{browser} — Security broker (manages permissions between processes)"
        elif "--type=" not in cmd_lower:
            return f"{browser} — Main browser process (manages all tabs and extensions)"

    # --- VS Code ---
    if name_lower == "code.exe":
        if "--type=renderer" in cmd_lower:
            return "VS Code — Editor window renderer"
        elif "--type=gpu-process" in cmd_lower:
            return "VS Code — GPU acceleration process"
        elif "--type=utility" in cmd_lower:
            return "VS Code — Utility helper process"
        elif "extensionhost" in cmd_lower.lower():
            return "VS Code — Extension Host (runs all your extensions)"
        elif "--type=" not in cmd_lower:
            return "VS Code — Main process"

    # --- msedgewebview2.exe ---
    if name_lower == "msedgewebview2.exe":
        if "--type=renderer" in cmd_lower:
            return "Edge WebView2 — Rendering web content for an app"
        elif "--type=gpu-process" in cmd_lower:
            return "Edge WebView2 — GPU acceleration for embedded web content"
        # Try to figure out which app is using it from the cmdline
        webview_match = re.search(r'--webview-exe-name=(\S+)', cmdline)
        if webview_match:
            app_name = webview_match.group(1)
            return f"Edge WebView2 — Embedded browser for {app_name}"

    # --- Python scripts ---
    if name_lower in ("python.exe", "pythonw.exe"):
        # Look for the script name in the cmdline
        parts = cmdline.split()
        for part in parts[1:]:
            p = part.strip('"').strip("'")
            if p.endswith('.py') or p.endswith('.pyw'):
                script = os.path.basename(p)
                return f"Python — Running script: {script}"
            if p == "-m":
                # Next arg is the module
                idx = parts.index(part)
                if idx + 1 < len(parts):
                    module = parts[idx + 1].strip('"')
                    return f"Python — Running module: {module}"
            if p == "-c":
                return "Python — Running inline code"
        return "Python — Interpreter running"

    # --- Node.js ---
    if name_lower == "node.exe":
        parts = cmdline.split()
        for part in parts[1:]:
            p = part.strip('"').strip("'")
            if p.endswith('.js') or p.endswith('.mjs') or p.endswith('.ts'):
                script = os.path.basename(p)
                return f"Node.js — Running: {script}"
        if "npm" in cmd_lower:
            return "Node.js — Running npm (package manager)"
        if "npx" in cmd_lower:
            return "Node.js — Running npx command"
        return "Node.js — JavaScript runtime"

    # --- Java ---
    if name_lower in ("java.exe", "javaw.exe"):
        if "minecraft" in cmd_lower:
            return "Java — Running Minecraft"
        if "eclipse" in cmd_lower:
            return "Java — Running Eclipse IDE"
        # Look for -jar or main class
        jar_match = re.search(r'-jar\s+"?([^"\s]+)', cmdline)
        if jar_match:
            jar = os.path.basename(jar_match.group(1))
            return f"Java — Running: {jar}"
        class_match = re.search(r'(?:^|\s)([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+)\s*$', cmdline)
        if class_match:
            return f"Java — Running class: {class_match.group(1)}"

    # --- cmd.exe ---
    if name_lower == "cmd.exe":
        if "/c " in cmd_lower:
            cmd_part = cmdline.split("/c ", 1)[-1][:80]
            return f"Command Prompt — Running: {cmd_part}"
        if "/k " in cmd_lower:
            cmd_part = cmdline.split("/k ", 1)[-1][:80]
            return f"Command Prompt — Running: {cmd_part}"

    # --- PowerShell ---
    if name_lower in ("powershell.exe", "pwsh.exe"):
        ps_name = "PowerShell" if name_lower == "powershell.exe" else "PowerShell 7"
        if "-file " in cmd_lower or "-f " in cmd_lower:
            file_match = re.search(r'-(?:file|f)\s+"?([^"\s]+)', cmdline, re.IGNORECASE)
            if file_match:
                script = os.path.basename(file_match.group(1))
                return f"{ps_name} — Running script: {script}"
        if "-command " in cmd_lower or "-c " in cmd_lower:
            return f"{ps_name} — Running a command"
        if "-encodedcommand" in cmd_lower:
            return f"{ps_name} — Running an encoded command"

    # --- svchost.exe (handled separately but add cmdline context) ---
    if name_lower == "svchost.exe":
        svc_match = re.search(r'-s\s+(\S+)', cmdline)
        if svc_match:
            svc_name = svc_match.group(1)
            desc = get_svchost_service_description(svc_name)
            return f"Service Host: {desc}"

    # --- rundll32.exe ---
    if name_lower == "rundll32.exe":
        parts = cmdline.split(None, 1)
        if len(parts) > 1:
            dll_part = parts[1][:100]
            # Try to extract meaningful DLL name
            dll_match = re.search(r'(\w+\.dll)', dll_part, re.IGNORECASE)
            if dll_match:
                return f"Running DLL function: {dll_match.group(1)} — {dll_part[:60]}"

    # --- msiexec.exe ---
    if name_lower == "msiexec.exe":
        if "/i " in cmd_lower:
            return "Windows Installer — Installing software"
        if "/x " in cmd_lower:
            return "Windows Installer — Uninstalling software"
        if "/p " in cmd_lower:
            return "Windows Installer — Applying patch"

    return None


def resolve_description(proc_name: str, exe_path: Optional[str] = None,
                        services: Optional[list] = None,
                        cmdline: str = "",
                        parent_name: str = "",
                        parent_pid: int = 0) -> str:
    """
    Resolve a friendly description for a process.
    Priority: cmdline analysis > DB + context > svchost service > exe metadata > fallback.
    """
    name_lower = proc_name.lower()

    # 1. Try cmdline-based description (most specific)
    if cmdline:
        cmdline_desc = _describe_from_cmdline(proc_name, cmdline, exe_path or "")
        if cmdline_desc:
            return cmdline_desc

    # 2. For helper processes, describe what they're serving
    if name_lower in _HELPER_PROCESSES and parent_name:
        parent_app = _get_parent_app_name(parent_name)
        helper_descs = {
            "conhost.exe": f"Console window for {parent_app} — draws the text output",
            "crashpad_handler.exe": f"Crash reporter for {parent_app} — sends crash data if it crashes",
            "msedgewebview2.exe": f"Embedded web browser used by {parent_app} to display web content",
            "runtimebroker.exe": f"Permission broker — manages security permissions for Store apps",
            "dllhost.exe": f"COM Surrogate — hosting a component, launched by {parent_app}",
            "backgroundtaskhost.exe": f"Background task running for {parent_app}",
            "werfault.exe": f"Windows Error Reporting — {parent_app} may have crashed",
            "werfaultsecure.exe": f"Secure error reporter — collecting crash data for {parent_app}",
        }
        desc = helper_descs.get(name_lower)
        if desc:
            return desc

    # 3. DB lookup
    info = get_process_info(name_lower)
    if info:
        base_desc = info.get("description", proc_name)

        # For svchost, try to identify the specific service
        if name_lower == "svchost.exe" and services:
            svc_descs = []
            for svc in services[:3]:
                svc_descs.append(get_svchost_service_description(svc))
            if svc_descs:
                return "Service Host: " + " | ".join(svc_descs)
        return base_desc

    # 4. Fallback: try to get description from executable metadata
    if exe_path:
        file_desc = get_file_description(exe_path)
        if file_desc:
            # Add parent context if available
            if parent_name and parent_name.lower() not in ("explorer.exe", "services.exe",
                                                            "svchost.exe", "wininit.exe"):
                parent_app = _get_parent_app_name(parent_name)
                return f"{file_desc} (launched by {parent_app})"
            return file_desc

    # 5. Last resort: use process name + parent context
    if parent_name:
        parent_app = _get_parent_app_name(parent_name)
        return f"{proc_name} — helper process for {parent_app}"

    return proc_name


def resolve_kill_impact(proc_name: str) -> str:
    """Resolve the kill impact description for a process."""
    info = get_process_info(proc_name.lower())
    if info:
        return info.get("kill_impact", "")
    return ""


def resolve_category(proc_name: str) -> str:
    """Resolve the category for a process."""
    info = get_process_info(proc_name.lower())
    if info:
        return info.get("category", "unknown")
    return "unknown"


def resolve_safety(proc_name: str) -> dict:
    """Resolve safety information for terminating a process."""
    info = get_process_info(proc_name.lower())
    if info:
        return {
            "safe_to_kill": info.get("safe_to_kill", True),
            "warning": info.get("kill_warning", ""),
            "category": info.get("category", "unknown"),
        }
    return {
        "safe_to_kill": True,
        "warning": "",
        "category": "unknown",
    }


# Pre-load on import
load_database()
