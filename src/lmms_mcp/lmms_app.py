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
import shutil
import subprocess
import sysconfig
from pathlib import Path


def _is_executable(path: Path) -> bool:
    return path.is_file() and (os.name == "nt" or os.access(path, os.X_OK))


def find_lmms_exe() -> Path | None:
    """Locate LMMS; an explicit override selects one installation only.

    Read configuration at call time and preserve the launcher path: resolving
    an AppDir's AppRun symlink before invoking it can break its shell wrapper.
    """
    configured = os.environ.get("LMMS_EXECUTABLE")
    if configured:
        candidate = Path(configured).expanduser()
        return candidate if _is_executable(candidate) else None
    candidates = [
        Path("C:/Program Files/LMMS/lmms.exe"),
        Path("C:/Program Files (x86)/LMMS/lmms.exe"),
        Path.home() / "AppData/Local/Programs/LMMS/lmms.exe",
    ] if os.name == "nt" else []
    for candidate in candidates:
        if _is_executable(candidate):
            return candidate
    found = shutil.which("lmms")
    return Path(found) if found else None


def get_plugins_dir() -> Path | None:
    """Find the selected installation's plugins without launching it.

    LMMS_PLUGIN_DIR is also understood by LMMS itself. Packed AppImages need
    an explicit directory or an extracted AppDir; never unpack implicitly or
    borrow a different system installation's inventory.
    """
    configured = os.environ.get("LMMS_PLUGIN_DIR")
    if configured:
        plugins = Path(configured).expanduser()
        return plugins if plugins.is_dir() else None
    exe = find_lmms_exe()
    if exe is None:
        return None
    if exe.suffix.lower() == ".appimage":
        return None
    try:
        executable = exe.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    prefix = executable.parent.parent
    candidates = [
        executable.parent / "plugins",  # portable Windows layout
        prefix / "lib/lmms",  # Unix prefix and extracted AppDir
        prefix / "lib64/lmms",
    ]
    # Debian-style packages use the host ABI's multiarch directory. Stay
    # within the selected prefix rather than borrowing another installation.
    multiarch = sysconfig.get_config_var("MULTIARCH")
    if multiarch:
        candidates.append(prefix / "lib" / multiarch / "lmms")
    return next((path for path in candidates if path.is_dir()), None)


def get_installed_plugins() -> set[str]:
    """Set of plugin library names shipped with the installed LMMS.

    Normalize Linux libNAME.so and Windows NAME.dll to the XML plugin name.
    These are file-presence hints: no library is loaded or validated here.
    Returns an empty set if no inventory directory can be found.
    """
    plugins_dir = get_plugins_dir()
    if plugins_dir is None:
        return set()
    names = set()
    for library in plugins_dir.iterdir():
        if not library.is_file():
            continue
        suffix = library.suffix.lower()
        name = library.stem.lower()
        if suffix == ".dll":
            names.add(name)
        elif suffix == ".so" and name.startswith("lib"):
            names.add(name[3:])
    return names


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
        if out.returncode != 0:
            return None
        match = re.search(r"\bLMMS\s+(\d+\.\d+(?:\.\d+)?)", out.stdout + out.stderr)
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


def get_plugin_availability(
    plugin_name: str,
    *,
    installed_plugins: set[str] | None = None,
) -> tuple[bool | None, str]:
    """Report plugin file presence, absence, or unknown availability.

    None means the inventory cannot establish availability. Even True only
    establishes file presence, not that LMMS can load or render the plugin.
    An optional inventory lets callers use one consistent detection snapshot.
    """
    name = plugin_name.strip().lower()
    if installed_plugins is None:
        try:
            installed = get_installed_plugins()
        except OSError:
            return None, "Plugin inventory could not be read - cannot verify"
    else:
        installed = installed_plugins
    if name in installed:
        return True, "installed"
    if any(alias in installed for alias in PLUGIN_ALIASES.get(name, {name})):
        return True, "installed (alias)"
    if name in STATIC_PLUGINS:
        return None, "May be built-in on some builds - cannot verify"
    if not installed:
        return None, "Plugin inventory unavailable or empty - cannot verify"
    return False, (
        f"'{plugin_name}' is not included in your installed LMMS "
        f"(found {len(installed)} plugins). It may require a newer "
        f"LMMS version."
    )


def check_plugin_available(plugin_name: str) -> tuple[bool, str]:
    """Legacy permissive check for offline project composition.

    Unknown availability remains allowed for backward compatibility. This
    boolean is not verification; use get_plugin_availability for that purpose.
    """
    available, reason = get_plugin_availability(plugin_name)
    return available is not False, reason


def classify_installed_plugins(
    known_instruments: set[str],
    known_effects: set[str],
) -> dict[str, list[str]]:
    """Classify installed plugin library names by comparing with known names.

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
