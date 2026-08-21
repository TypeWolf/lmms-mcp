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


def classify_installed_plugins(
    known_instruments: set[str],
    known_effects: set[str],
) -> dict[str, list[str]]:
    """Classify all installed plugin DLLs by comparing with known names.

    Returns dict with keys "instruments", "effects", "unknown".
    Unknown DLLs are custom/newer plugins the user added - they can be
    used but their type (instrument vs effect) is not known from the
    filename alone.
    """
    installed = get_installed_plugins()
    result: dict[str, list[str]] = {"instruments": [], "effects": [], "unknown": []}
    for name in sorted(installed):
        if name.startswith("lib"):
            continue  # support libraries, not plugins
        if name in known_instruments or any(
            name in aliases for aliases in PLUGIN_ALIASES.values()
        ) and name in known_instruments:
            result["instruments"].append(name)
        elif name in known_effects:
            result["effects"].append(name)
        else:
            result["unknown"].append(name)
    return result


def find_vst_plugins(directory: str | Path, recursive: bool = True) -> list[dict]:
    """Scan a directory for VST plugin DLLs.

    Returns list of dicts with name and path. Note: any .dll could be a
    VST effect or instrument - LMMS decides on load.
    """
    root = Path(directory)
    if not root.is_dir():
        raise ValueError(f"Directory not found: {directory}")
    it = root.rglob("*.dll") if recursive else root.glob("*.dll")
    skip = {"lmms.exe", "remotevstplugin.exe", "32bitvsthelper.exe"}
    results = []
    for dll in sorted(it):
        if dll.stem.lower() in skip:
            continue
        results.append({
            "name": dll.stem,
            "path": str(dll),
            "size_kb": round(dll.stat().st_size / 1024),
        })
    return results
