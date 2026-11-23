"""Where exports go: native folder picker and "reveal in file manager"."""

import platform
import subprocess
from pathlib import Path

from adalove.config.paths import OUTPUT_DIR
from cli.ui import _info, console


_OUTPUT_ROOT = OUTPUT_DIR


def _pick_destination_folder() -> Path | None:
    """Open a native folder picker and return the chosen path, or None if the
    user cancels (or no picker is available on this OS/desktop).

    macOS uses `osascript` (AppleScript); Windows uses PowerShell's built-in
    FolderBrowserDialog; Linux tries `zenity` then `kdialog` — whichever the
    desktop environment ships. No extra Python dependency either way, and
    more reliable across Python builds than tkinter's file dialogs.
    """
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["osascript", "-e", 'POSIX path of (choose folder with prompt "Selecione a pasta de destino")'],
                capture_output=True,
                text=True,
                timeout=120,
            )
        elif system == "Windows":
            script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                "$f.Description = 'Selecione a pasta de destino'; "
                "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.SelectedPath }"
            )
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=120,
            )
        else:
            result = None
            for cmd in (
                ["zenity", "--file-selection", "--directory", "--title=Selecione a pasta de destino"],
                ["kdialog", "--getexistingdirectory", str(Path.home())],
            ):
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                    break
                except FileNotFoundError:
                    continue
            if result is None:
                return None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip())


def _choose_output_dir() -> Path:
    """Ask where this export's files should be written — falls back to the
    project's own output/ folder if the user cancels the picker. Writing
    directly to the chosen folder (instead of writing to output/ and copying
    afterwards) avoids keeping two copies in sync."""
    console.print()
    _info("Selecione a pasta de destino (cancele para usar a pasta padrão output/)...")
    return _pick_destination_folder() or _OUTPUT_ROOT


def _reveal_in_finder(path: Path) -> None:
    """Open the given folder in the OS's file manager once an export
    finishes — Finder on macOS, Explorer on Windows, whatever `xdg-open`
    resolves to on Linux."""
    system = platform.system()
    if system == "Darwin":
        cmd = ["open", str(path)]
    elif system == "Windows":
        cmd = ["explorer", str(path)]
    else:
        cmd = ["xdg-open", str(path)]
    try:
        subprocess.run(cmd, check=False)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
