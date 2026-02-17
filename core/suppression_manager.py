"""
Suppression Manager — prevents killed processes from respawning.
Supports: disabling services, startup entries, scheduled tasks, and IFEO blocking.
"""

import json
import os
import subprocess
import winreg
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SuppressionEntry:
    process_name: str
    exe_path: str = ""
    method: str = ""  # "service", "startup", "task", "ifeo"
    detail: str = ""  # service name, task name, registry key, etc.
    created: str = ""
    active: bool = True


_SUPPRESSION_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "resources", "suppressions.json"
)


class SuppressionManager:
    """Manages process suppression rules."""

    def __init__(self):
        self.entries: list[SuppressionEntry] = []
        self._load()

    def _load(self):
        """Load suppression entries from disk."""
        try:
            with open(_SUPPRESSION_FILE, "r") as f:
                data = json.load(f)
                self.entries = [SuppressionEntry(**e) for e in data]
        except (FileNotFoundError, json.JSONDecodeError):
            self.entries = []

    def _save(self):
        """Persist suppression entries to disk."""
        data = []
        for e in self.entries:
            data.append({
                "process_name": e.process_name,
                "exe_path": e.exe_path,
                "method": e.method,
                "detail": e.detail,
                "created": e.created,
                "active": e.active,
            })
        os.makedirs(os.path.dirname(_SUPPRESSION_FILE), exist_ok=True)
        with open(_SUPPRESSION_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def get_entries(self) -> list[SuppressionEntry]:
        return list(self.entries)

    def disable_service(self, service_name: str, process_name: str = "") -> tuple[bool, str]:
        """Disable a Windows service to prevent respawn."""
        try:
            result = subprocess.run(
                ["sc", "config", service_name, "start=", "disabled"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                subprocess.run(
                    ["sc", "stop", service_name],
                    capture_output=True, text=True, timeout=10
                )
                entry = SuppressionEntry(
                    process_name=process_name or service_name,
                    method="service",
                    detail=service_name,
                    created=datetime.now().isoformat(),
                    active=True,
                )
                self.entries.append(entry)
                self._save()
                return True, f"Service '{service_name}' disabled."
            else:
                return False, f"Failed: {result.stderr.strip()}"
        except Exception as e:
            return False, str(e)

    def enable_service(self, service_name: str) -> tuple[bool, str]:
        """Re-enable a disabled service."""
        try:
            result = subprocess.run(
                ["sc", "config", service_name, "start=", "auto"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self.entries = [
                    e for e in self.entries
                    if not (e.method == "service" and e.detail == service_name)
                ]
                self._save()
                return True, f"Service '{service_name}' re-enabled."
            else:
                return False, f"Failed: {result.stderr.strip()}"
        except Exception as e:
            return False, str(e)

    def disable_startup_entry(self, name: str, location: str = "registry",
                              process_name: str = "") -> tuple[bool, str]:
        """Disable a startup entry."""
        try:
            if location == "registry":
                for hive, path in [
                    (winreg.HKEY_CURRENT_USER,
                     r"Software\Microsoft\Windows\CurrentVersion\Run"),
                    (winreg.HKEY_LOCAL_MACHINE,
                     r"Software\Microsoft\Windows\CurrentVersion\Run"),
                ]:
                    try:
                        key = winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS)
                        value, _ = winreg.QueryValueEx(key, name)
                        winreg.DeleteValue(key, name)
                        winreg.CloseKey(key)

                        # Store in disabled run key for restore
                        disabled_path = path.replace("\\Run", "\\Run-Disabled")
                        try:
                            dkey = winreg.CreateKey(hive, disabled_path)
                            winreg.SetValueEx(dkey, name, 0, winreg.REG_SZ, value)
                            winreg.CloseKey(dkey)
                        except Exception:
                            pass

                        entry = SuppressionEntry(
                            process_name=process_name or name,
                            method="startup",
                            detail=f"{name}|{location}|{value}",
                            created=datetime.now().isoformat(),
                            active=True,
                        )
                        self.entries.append(entry)
                        self._save()
                        return True, f"Startup entry '{name}' disabled."
                    except FileNotFoundError:
                        continue
                    except Exception:
                        continue
                return False, f"Startup entry '{name}' not found."
            else:
                return False, f"Unsupported location: {location}"
        except Exception as e:
            return False, str(e)

    def disable_scheduled_task(self, task_name: str,
                               process_name: str = "") -> tuple[bool, str]:
        """Disable a scheduled task."""
        try:
            result = subprocess.run(
                ["schtasks", "/Change", "/TN", task_name, "/Disable"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                entry = SuppressionEntry(
                    process_name=process_name or task_name,
                    method="task",
                    detail=task_name,
                    created=datetime.now().isoformat(),
                    active=True,
                )
                self.entries.append(entry)
                self._save()
                return True, f"Scheduled task '{task_name}' disabled."
            else:
                return False, f"Failed: {result.stderr.strip()}"
        except Exception as e:
            return False, str(e)

    def enable_scheduled_task(self, task_name: str) -> tuple[bool, str]:
        """Re-enable a scheduled task."""
        try:
            result = subprocess.run(
                ["schtasks", "/Change", "/TN", task_name, "/Enable"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self.entries = [
                    e for e in self.entries
                    if not (e.method == "task" and e.detail == task_name)
                ]
                self._save()
                return True, f"Scheduled task '{task_name}' re-enabled."
            else:
                return False, f"Failed: {result.stderr.strip()}"
        except Exception as e:
            return False, str(e)

    def block_via_ifeo(self, exe_name: str,
                       process_name: str = "") -> tuple[bool, str]:
        """Block a process using Image File Execution Options debugger redirect."""
        try:
            key_path = rf"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\{exe_name}"
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            # Redirect to a nonexistent debugger, preventing the process from launching
            winreg.SetValueEx(key, "Debugger", 0, winreg.REG_SZ,
                              r"C:\Windows\System32\systray.exe")
            winreg.CloseKey(key)

            entry = SuppressionEntry(
                process_name=process_name or exe_name,
                exe_path=exe_name,
                method="ifeo",
                detail=exe_name,
                created=datetime.now().isoformat(),
                active=True,
            )
            self.entries.append(entry)
            self._save()
            return True, f"Process '{exe_name}' blocked via IFEO."
        except PermissionError:
            return False, "Access denied. Run as Administrator."
        except Exception as e:
            return False, str(e)

    def unblock_ifeo(self, exe_name: str) -> tuple[bool, str]:
        """Remove an IFEO block."""
        try:
            key_path = rf"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\{exe_name}"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_ALL_ACCESS)
            try:
                winreg.DeleteValue(key, "Debugger")
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)

            self.entries = [
                e for e in self.entries
                if not (e.method == "ifeo" and e.detail == exe_name)
            ]
            self._save()
            return True, f"IFEO block removed for '{exe_name}'."
        except Exception as e:
            return False, str(e)

    def restore_entry(self, index: int) -> tuple[bool, str]:
        """Restore a suppression entry by index."""
        if index < 0 or index >= len(self.entries):
            return False, "Invalid index."

        entry = self.entries[index]
        if entry.method == "service":
            return self.enable_service(entry.detail)
        elif entry.method == "task":
            return self.enable_scheduled_task(entry.detail)
        elif entry.method == "ifeo":
            return self.unblock_ifeo(entry.detail)
        elif entry.method == "startup":
            parts = entry.detail.split("|")
            if len(parts) >= 3:
                name, location, value = parts[0], parts[1], "|".join(parts[2:])
                try:
                    for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
                        path = r"Software\Microsoft\Windows\CurrentVersion\Run"
                        try:
                            key = winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS)
                            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
                            winreg.CloseKey(key)
                            self.entries.pop(index)
                            self._save()
                            return True, f"Startup entry '{name}' restored."
                        except Exception:
                            continue
                except Exception as e:
                    return False, str(e)
            return False, "Cannot restore startup entry — missing data."
        return False, f"Unknown method: {entry.method}"

    def restore_all(self) -> list[tuple[bool, str]]:
        """Restore all active suppression entries."""
        results = []
        for i in range(len(self.entries) - 1, -1, -1):
            if self.entries[i].active:
                results.append(self.restore_entry(i))
        return results
