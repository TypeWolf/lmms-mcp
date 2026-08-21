"""ZynAddSubFX preset (.xiz) discovery and loading.

.xiz files are gzip-compressed XML documents with a <ZynAddSubFX-data>
root element. LMMS ships ~950 presets in data/presets/ZynAddSubFX.
"""

import gzip
import os
from pathlib import Path

PRESET_EXTENSIONS = {".xiz"}

# Candidate locations scanned in order; first existing directory wins.
# Can be overridden with the LMMS_PRESETS_DIR environment variable
# (points directly at the ZynAddSubFX folder or its parent presets dir).
_CANDIDATE_ROOTS = [
    Path(os.environ.get("LMMS_PRESETS_DIR", "")) if os.environ.get("LMMS_PRESETS_DIR") else None,
    Path("C:/Program Files/LMMS/data/presets/ZynAddSubFX"),
    Path("C:/Program Files (x86)/LMMS/data/presets/ZynAddSubFX"),
    Path.home() / "Documents/LMMS/presets/ZynAddSubFX",
    Path.home() / ".lmms/presets/ZynAddSubFX",
]


def get_presets_dir() -> Path | None:
    """Return the first existing ZynAddSubFX presets directory, if any."""
    for candidate in _CANDIDATE_ROOTS:
        if candidate is not None and candidate.is_dir():
            return candidate
    return None


def list_categories() -> list[str]:
    """List preset categories (subdirectories) in the presets dir."""
    base = get_presets_dir()
    if base is None:
        return []
    cats = sorted(
        d.name for d in base.iterdir()
        if d.is_dir() and any(d.glob("*.xiz"))
    )
    # Presets may also live directly in the root dir
    if any(base.glob("*.xiz")):
        cats.insert(0, "(root)")
    return cats


def list_presets(category: str | None = None) -> list[dict]:
    """List available .xiz presets, optionally filtered by category.

    Returns a list of dicts with name, category and path.
    """
    base = get_presets_dir()
    if base is None:
        return []

    results = []
    if category and category != "(root)":
        search_dir = base / category
        if not search_dir.is_dir():
            raise ValueError(
                f"Unknown preset category '{category}'. "
                f"Available: {', '.join(list_categories())}"
            )
        dirs_to_scan = [(category, search_dir)]
    elif category == "(root)":
        dirs_to_scan = [("(root)", base)]
    else:
        dirs_to_scan = [
            (d.name, d) for d in sorted(base.iterdir()) if d.is_dir()
        ]
        if any(base.glob("*.xiz")):
            dirs_to_scan.append(("(root)", base))

    for cat_name, cat_dir in dirs_to_scan:
        for xiz in sorted(cat_dir.glob("*.xiz")):
            results.append({
                "name": xiz.stem,
                "category": cat_name,
                "path": str(xiz),
            })
    return results


def load_preset_xml(path: str) -> str:
    """Load a .xiz preset file and return its XML content as string.

    Supports absolute paths, paths relative to the presets dir, and
    fuzzy "Category/Name" or plain "Name" lookups against the installed
    preset library (numeric prefixes like "0001-" are ignored).
    """
    given = Path(path)

    # 1. Direct hit (absolute path or exists relative to cwd)
    if given.is_absolute() and given.is_file():
        return _read_preset(given)
    if not given.is_absolute():
        base = get_presets_dir()
        if base is not None:
            direct = base / (
                given.with_suffix(".xiz") if not given.suffix else given
            )
            if direct.is_file():
                return _read_preset(direct)

    # 2. Fuzzy search by name fragment (ignores "0001-" style prefixes)
    base = get_presets_dir()
    if base is None:
        raise RuntimeError(
            "No ZynAddSubFX presets directory found. Set LMMS_PRESETS_DIR."
        )
    name_part = given.stem if given.suffix == ".xiz" else given.name
    pattern = f"*{name_part}.xiz"
    matches = sorted(base.rglob(pattern))
    if not matches:
        raise FileNotFoundError(
            f"Preset '{path}' not found. Use list_zyn_presets to browse "
            f"available presets."
        )
    # Prefer shortest path (closest name match)
    best = min(matches, key=lambda p: len(p.stem))
    return _read_preset(best)


def _read_preset(path: Path) -> str:
    """Read a preset file, transparently decompressing gzip (.xiz)."""
    if _is_gzip(path):
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
                return f.read()
        except (OSError, EOFError) as exc:
            raise ValueError(f"Cannot read preset '{path}': {exc}") from exc
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ValueError(f"Cannot read preset '{path}': {exc}") from exc


def _is_gzip(path: Path) -> bool:
    """Check gzip magic bytes."""
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"\x1f\x8b"
    except OSError:
        return False
