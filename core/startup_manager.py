"""
Startup Manager — lists, enables, and disables startup items.
Sources: Registry Run keys, shell:startup folder, Task Scheduler.
"""

import os
import subprocess
import winreg
from dataclasses import dataclass
from typing import Optional


@dataclass
class StartupItem:
    name: str
    command: str
    location: str       # "registry_hkcu", "registry_hklm", "startup_folder", "task_scheduler"
    enabled: bool
    impact: str = ""    # "High", "Medium", "Low", "None", "Unknown"
    description: str = ""
    publisher: str = ""


class StartupManager:
    """Manages Windows startup items."""

    def get_all_items(self) -> list[StartupItem]:
        """Collect all startup items from all sources."""
        items = []
        items.extend(self._get_registry_items(winreg.HKEY_CURRENT_USER, "registry_hkcu"))
        items.extend(self._get_registry_items(winreg.HKEY_LOCAL_MACHINE, "registry_hklm"))
        items.extend(self._get_startup_folder_items())
        items.extend(self._get_scheduled_task_items())
        return items

    def _get_registry_items(self, hive, location_label: str) -> list[StartupItem]:
        """Read startup entries from registry Run keys."""
        items = []
        run_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

        # Enabled items
        try:
            key = winreg.OpenKey(hive, run_path, 0, winreg.KEY_READ)
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    items.append(StartupItem(
                        name=name,
                        command=value,
                        location=location_label,
                        enabled=True,
                        impact=self._estimate_impact(value),
                    ))
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass

        # Disabled items (stored by Windows in a separate key)
        disabled_path = run_path.replace("\\Run", "\\Run-Disabled")
        try:
            key = winreg.OpenKey(hive, disabled_path, 0, winreg.KEY_READ)
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    items.append(StartupItem(
                        name=name,
                        command=value,
                        location=location_label,
                        enabled=False,
                        impact=self._estimate_impact(value),
                    ))
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass

        # Also check the approved list used by Task Manager
        approved_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
        try:
            key = winreg.OpenKey(hive, approved_path, 0, winreg.KEY_READ)
            i = 0
            while True:
                try:
                    name, value, vtype = winreg.EnumValue(key, i)
                    # If first byte is not 02, the item is disabled
                    if isinstance(value, bytes) and len(value) >= 1:
                        is_enabled = value[0] == 0x02
                        # Find matching item and update enabled status
                        for item in items:
                            if item.name == name:
                                item.enabled = is_enabled
                                break
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(key)
        except FileNotFoundError:
            pass

        return items

    def _get_startup_folder_items(self) -> list[StartupItem]:
        """Read startup entries from the startup folder."""
        items = []
        startup_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"),
            os.path.expandvars(r"%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs\Startup"),
        ]
        for folder in startup_dirs:
            if os.path.isdir(folder):
                for fname in os.listdir(folder):
                    fpath = os.path.join(folder, fname)
                    if os.path.isfile(fpath):
                        items.append(StartupItem(
                            name=fname,
                            command=fpath,
                            location="startup_folder",
                            enabled=True,
                            impact=self._estimate_impact(fpath),
                        ))
        return items

    def _get_scheduled_task_items(self) -> list[StartupItem]:
        """Get scheduled tasks that run at logon."""
        items = []
        try:
            result = subprocess.run(
                ["schtasks", "/Query", "/FO", "CSV", "/V"],
                capture_output=True, text=True, timeout=15,
                encoding='utf-8', errors='replace'
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    headers = lines[0].replace('"', '').split(',')
                    name_idx = next((i for i, h in enumerate(headers) if 'TaskName' in h), 0)
                    trigger_idx = next((i for i, h in enumerate(headers) if 'Trigger' in h or 'Start' in h), -1)
                    action_idx = next((i for i, h in enumerate(headers) if 'Task To Run' in h), -1)
                    status_idx = next((i for i, h in enumerate(headers) if 'Status' in h), -1)

                    for line in lines[1:]:
                        parts = line.replace('"', '').split(',')
                        if len(parts) > max(name_idx, trigger_idx, action_idx, status_idx):
                            trigger = parts[trigger_idx] if trigger_idx >= 0 else ""
                            if "logon" in trigger.lower() or "startup" in trigger.lower():
                                task_name = parts[name_idx]
                                action = parts[action_idx] if action_idx >= 0 else ""
                                status = parts[status_idx] if status_idx >= 0 else ""
                                enabled = "disabled" not in status.lower()
                                items.append(StartupItem(
                                    name=task_name.split('\\')[-1],
                                    command=action,
                                    location="task_scheduler",
                                    enabled=enabled,
                                    impact="Medium",
                                    description=f"Scheduled task: {task_name}",
                                ))
        except Exception:
            pass
        return items

    def _estimate_impact(self, command: str) -> str:
        """Estimate startup impact based on the command."""
        cmd_lower = command.lower()
        high_impact = ['chrome', 'firefox', 'edge', 'teams', 'outlook', 'steam',
                       'discord', 'spotify', 'onedrive', 'dropbox', 'adobe',
                       'java', 'skype', 'zoom']
        medium_impact = ['update', 'helper', 'sync', 'monitor', 'tray', 'notify']
        low_impact = ['ctfmon', 'ime', 'input']

        for kw in high_impact:
            if kw in cmd_lower:
                return "High"
        for kw in medium_impact:
            if kw in cmd_lower:
                return "Medium"
        for kw in low_impact:
            if kw in cmd_lower:
                return "Low"
        return "Unknown"

    def toggle_item(self, item: StartupItem, enable: bool) -> tuple[bool, str]:
        """Enable or disable a startup item."""
        if item.location.startswith("registry_"):
            return self._toggle_registry_item(item, enable)
        elif item.location == "startup_folder":
            return self._toggle_folder_item(item, enable)
        elif item.location == "task_scheduler":
            return self._toggle_task_item(item, enable)
        return False, f"Unknown location: {item.location}"

    def _toggle_registry_item(self, item: StartupItem, enable: bool) -> tuple[bool, str]:
        """Toggle a registry startup item via the StartupApproved key."""
        hive = (winreg.HKEY_CURRENT_USER if item.location == "registry_hkcu"
                else winreg.HKEY_LOCAL_MACHINE)
        approved_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
        try:
            key = winreg.OpenKey(hive, approved_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                # Enabled = starts with 02
                data = b'\x02' + b'\x00' * 11
            else:
                # Disabled = starts with 03
                data = b'\x03' + b'\x00' * 11
            winreg.SetValueEx(key, item.name, 0, winreg.REG_BINARY, data)
            winreg.CloseKey(key)
            state = "enabled" if enable else "disabled"
            return True, f"Startup entry '{item.name}' {state}."
        except Exception as e:
            return False, str(e)

    def _toggle_folder_item(self, item: StartupItem, enable: bool) -> tuple[bool, str]:
        """Toggle a startup folder item by renaming."""
        path = item.command
        if enable:
            if path.endswith(".disabled"):
                new_path = path[:-9]
                os.rename(path, new_path)
                item.command = new_path
                return True, f"Startup item '{item.name}' enabled."
            return True, "Already enabled."
        else:
            if not path.endswith(".disabled"):
                new_path = path + ".disabled"
                os.rename(path, new_path)
                item.command = new_path
                return True, f"Startup item '{item.name}' disabled."
            return True, "Already disabled."

    def _toggle_task_item(self, item: StartupItem, enable: bool) -> tuple[bool, str]:
        """Toggle a scheduled task."""
        flag = "/Enable" if enable else "/Disable"
        try:
            result = subprocess.run(
                ["schtasks", "/Change", "/TN", item.description.replace("Scheduled task: ", ""), flag],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                state = "enabled" if enable else "disabled"
                return True, f"Task '{item.name}' {state}."
            return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)
