"""Detect the installed LMMS application and its available plugins.

The MCP server manipulates project files directly without launching
LMMS. However, knowing which plugins the installed LMMS actually ships
prevents generating projects with missing-plugin warnings.

LMMS 1.2.x and 1.3.x differ in plugin availability, e.g.:
- SlicerT, Xpressive: 1.3+ only
- Compressor, Dispersion, FrequencyShifter, SlewDistortion effects: 1.3+ only
"""

import os
import re
import subprocess
from pathlib import Path

_CANDIDATE_EXES = [
    Path(os.environ.get("LMMS_EXECUTABLE", "")) if os.environ.get("LMMS_EXECUTABLE") else None,
    Path("C:/Program Files/LMMS/lmms.exe"),
    Path("C:/Program Files (x86)/LMMS/lmms.exe"),
    Path.home() / "AppData/Local/Programs/LMMS/lmms.exe",
]


def find_lmms_exe() -> Path | None:
    """Locate the installed LMMS executable."""
    for candidate in _CANDIDATE_EXES:
        if candidate is not None and candidate.is_file():
            return candidate
    return None


def get_plugins_dir() -> Path | None:
    """Return the plugins directory of the installed LMMS."""
    exe = find_lmms_exe()
    if exe is None:
        return None
    plugins = exe.parent / "plugins"
    return plugins if plugins.is_dir() else None


def get_installed_plugins() -> set[str]:
    """Set of plugin library names shipped with the installed LMMS.

    Names are lowercase DLL basenames (e.g. "tripleoscillator",
    "reverbsc"). Returns an empty set if LMMS is not found.
    """
    plugins_dir = get_plugins_dir()
    if plugins_dir is None:
        return set()
    return {
        f.stem.lower() for f in plugins_dir.glob("*.dll")
    }


def get_lmms_version() -> str | None:
    """Version string of the installed LMMS (e.g. '1.2.2'), or None."""
    exe = find_lmms_exe()
    if exe is None:
        return None
    try:
        out = subprocess.run(
            [str(exe), "--version"],
            capture_output=True, text=True, timeout=10,
        )
        match = re.search(r"(\d+\.\d+(?:\.\d+)?)", out.stdout + out.stderr)
        return match.group(1) if match else None
    except (OSError, subprocess.TimeoutExpired):
        return None


# Known aliases across versions (XML name -> possible DLL names).
# Some instruments are statically linked into lmms.exe and have no DLL;
# those are listed in STATIC_PLUGINS.
STATIC_PLUGINS = {
    # Official Windows builds link FreeBoy into the main binary
    "freeboy",
}

PLUGIN_ALIASES = {
    "nes": {"nes", "papu", "nescaline"},
    "papu": {"nes", "papu", "nescaline"},
    "malletsstk": {"malletsstk", "stk"},
    "audiofileprocessor": {"audiofileprocessor"},
    "sf2player": {"sf2player", "fluidsynth"},
    "opulenz": {"opl2", "opulenz"},  # named OPL2 in LMMS 1.2.x
}


def check_plugin_available(plugin_name: str) -> tuple[bool, str]:
    """Check whether a plugin exists in the installed LMMS.

    Returns (available, reason). If no LMMS installation is detected,
    everything is considered available (cannot verify).
    """
    name = plugin_name.lower()
    if name in STATIC_PLUGINS:
        return True, "built-in"
    installed = get_installed_plugins()
    if not installed:
        return True, "LMMS installation not found - cannot verify"
    if name in installed:
        return True, "installed"
    if any(alias in installed for alias in PLUGIN_ALIASES.get(name, {name})):
        return True, "installed (alias)"
    return False, (
        f"'{plugin_name}' is not included in your installed LMMS "
        f"(found {len(installed)} plugins). It may require a newer "
        f"LMMS version."
    )
