"""XML parser for LMMS .mmpz and .mmp project files."""

import struct
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET


def _q_compress(data: bytes) -> bytes:
    """Replicate Qt's qCompress: 4-byte big-endian size header + zlib data."""
    compressed = zlib.compress(data, 9)
    size = len(data)
    return struct.pack(">I", size) + compressed


def _q_uncompress(data: bytes) -> bytes:
    """Replicate Qt's qUncompress: read 4-byte big-endian size header + zlib data."""
    if len(data) < 4:
        raise ValueError("Data too short for qCompress header")
    size = struct.unpack(">I", data[:4])[0]
    decompressed = zlib.decompress(data[4:])
    return decompressed


def load_project(path: str | Path) -> ET.Element:
    """Load an LMMS project file (.mmpz or .mmp) and return the root element.

    .mmpz files use Qt's qCompress format: 4-byte big-endian length header + zlib.
    We try plain XML first, then qUncompress, then raw zlib.
    """
    path = Path(path)
    raw = path.read_bytes()

    # Try plain XML first (.mmp files)
    try:
        root = ET.fromstring(raw)
        return root
    except ET.ParseError:
        pass

    # Try Qt's qCompress format (4-byte header + zlib)
    try:
        decompressed = _q_uncompress(raw)
        root = ET.fromstring(decompressed)
        return root
    except (struct.error, zlib.error, ET.ParseError):
        pass

    # Try raw zlib (no header)
    try:
        decompressed = zlib.decompress(raw)
        root = ET.fromstring(decompressed)
        return root
    except (zlib.error, ET.ParseError):
        pass

    raise ValueError(f"Cannot parse {path}: not a valid LMMS project file")


def save_project(path: str | Path, root: ET.Element, compressed: bool = True) -> None:
    """Save an LMMS project element to a file.

    If compressed is True, writes .mmpz (Qt qCompress format).
    Otherwise writes plain .mmp XML.
    """
    path = Path(path)
    ET.indent(root, space="  ")
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
    xml_str = '<?xml version="1.0"?>\n<!DOCTYPE lmms-project>\n' + xml_str

    if compressed:
        data = _q_compress(xml_str.encode("utf-8"))
    else:
        data = xml_str.encode("utf-8")

    path.write_bytes(data)


def create_empty_project(
    bpm: int = 140,
    time_sig_numerator: int = 4,
    time_sig_denominator: int = 4,
    master_volume: int = 100,
    master_pitch: int = 0,
) -> ET.Element:
    """Create a minimal empty LMMS project element tree."""
    root = ET.Element("lmms-project", {
        "version": "1.0",
        "creator": "LMMS MCP Server",
        "creatorversion": "1.2.0",
        "type": "song",
    })

    head = ET.SubElement(root, "head", {
        "timesig_numerator": str(time_sig_numerator),
        "timesig_denominator": str(time_sig_denominator),
        "bpm": str(bpm),
        "mastervol": str(master_volume),
        "masterpitch": str(master_pitch),
    })

    song = ET.SubElement(root, "song")

    trackcontainer = ET.SubElement(song, "trackcontainer", {
        "type": "song",
        "visible": "1",
        "width": "600",
        "height": "300",
        "x": "5",
        "y": "5",
        "maximized": "0",
        "minimized": "0",
    })

    mixer = ET.SubElement(song, "mixer", {
        "visible": "1",
        "width": "561",
        "height": "332",
        "x": "5",
        "y": "310",
        "maximized": "0",
        "minimized": "0",
    })
    ET.SubElement(mixer, "mixerchannel", {
        "num": "0",
        "muted": "0",
        "volume": "1",
        "name": "Master",
        "soloed": "0",
    }).append(ET.Element("fxchain", {"numofeffects": "0", "enabled": "0"}))

    ET.SubElement(song, "ControllerRackView", {
        "visible": "1", "width": "258", "height": "142",
        "x": "836", "y": "407", "maximized": "0", "minimized": "0",
    })
    ET.SubElement(song, "pianoroll", {
        "visible": "0", "width": "640", "height": "480",
        "x": "1", "y": "1", "maximized": "0", "minimized": "0",
    })
    ET.SubElement(song, "automationeditor", {
        "visible": "0", "width": "640", "height": "400",
        "x": "56", "y": "255", "maximized": "0", "minimized": "0",
    })
    ET.SubElement(song, "projectnotes", {
        "visible": "0", "width": "640", "height": "400",
        "x": "1", "y": "1", "maximized": "0", "minimized": "0",
    })
    ET.SubElement(song, "timeline", {
        "lp0pos": "0", "lp1pos": "192", "lpstate": "0",
    })
    ET.SubElement(song, "controllers")

    return root


def element_to_dict(elem: ET.Element) -> dict:
    """Recursively convert an XML element to a dictionary."""
    result = dict(elem.attrib)

    children = list(elem)
    if children:
        child_dict: dict[str, list] = {}
        for child in children:
            tag = child.tag
            if tag not in child_dict:
                child_dict[tag] = []
            child_dict[tag].append(element_to_dict(child))
        result["_children"] = child_dict

    if elem.text and elem.text.strip():
        result["_text"] = elem.text.strip()

    return result


def find_tracks(root: ET.Element) -> list[ET.Element]:
    """Find all <track> elements in the project."""
    song = root.find("song")
    if song is None:
        return []

    container = song.find("trackcontainer[@type='song']")
    if container is None:
        return []

    return container.findall("track")


def find_mixer_channels(root: ET.Element) -> list[ET.Element]:
    """Find all <mixerchannel> elements."""
    song = root.find("song")
    if song is None:
        return []

    mixer = song.find("mixer")
    if mixer is None:
        return []

    return mixer.findall("mixerchannel")


def get_track_type(elem: ET.Element) -> int:
    """Get the track type integer from a <track> element."""
    return int(elem.get("type", "0"))


def get_track_name(elem: ET.Element) -> str:
    """Get the track name from a <track> element."""
    return elem.get("name", "Unnamed")


TRACK_TYPE_NAMES = {
    0: "Instrument",
    1: "Pattern",
    2: "Sample",
    3: "Event",
    4: "Video",
    5: "Automation",
    6: "HiddenAutomation",
}


def track_type_name(type_id: int) -> str:
    """Convert a track type integer to its name."""
    return TRACK_TYPE_NAMES.get(type_id, f"Unknown({type_id})")


def add_instrument_track(
    root: ET.Element,
    name: str,
    instrument: str = "tripleoscillator",
    mixer_channel: int = 0,
    volume: int = 100,
    panning: int = 0,
) -> ET.Element:
    """Add an instrument track to the project and return the track element."""
    song = root.find("song")
    container = song.find("trackcontainer[@type='song']")

    track = ET.SubElement(container, "track", {
        "muted": "0",
        "type": "0",
        "name": name,
        "solo": "0",
    })

    inst_track = ET.SubElement(track, "instrumenttrack", {
        "pan": str(panning),
        "mixch": str(mixer_channel),
        "usemasterpitch": "1",
        "pitchrange": "1",
        "pitch": "0",
        "basenote": "57",
        "vol": str(volume),
    })

    inst = ET.SubElement(inst_track, "instrument", {"name": instrument})
    ET.SubElement(inst, instrument.replace(" ", "").lower())

    eldata = ET.SubElement(inst_track, "eldata", {
        "fres": "0.5", "ftype": "0", "fcut": "14000", "fwet": "0",
    })
    ET.SubElement(eldata, "elvol", {
        "lspd_denominator": "4", "sustain": "0.5",
        "lspd_numerator": "4", "attack": "0", "decay": "0.5",
        "hold": "0", "amount": "0",
    })
    ET.SubElement(eldata, "elcut", {
        "lspd_denominator": "4", "sustain": "0.5",
        "lspd_numerator": "4", "attack": "0", "decay": "0.5",
        "hold": "0", "amount": "0",
    })
    ET.SubElement(eldata, "elres", {
        "lspd_denominator": "4", "sustain": "0.5",
        "lspd_numerator": "4", "attack": "0", "decay": "0.5",
        "hold": "0", "amount": "0",
    })

    ET.SubElement(inst_track, "chordcreator", {
        "chord": "0", "chordrange": "1", "chord-enabled": "0",
    })
    ET.SubElement(inst_track, "arpeggiator", {
        "arp": "0", "arp-enabled": "0",
        "arpcenter": "0", "arpdir": "0", "arprange": "1",
        "arpspeed": "4", "arpType": "0",
    })
    ET.SubElement(inst_track, "midiport", {
        "inputcontroller": "0", "fixedoutputvelocity": "-1",
        "inputchannel": "0", "outputcontroller": "0", "writable": "0",
        "outputchannel": "1", "fixedinputvelocity": "-1",
        "fixedoutputnote": "-1", "outputprogram": "1",
        "basevelocity": "63", "readable": "0",
    })
    ET.SubElement(inst_track, "fxchain", {
        "numofeffects": "0", "enabled": "0",
    })

    return track


def add_sample_track(
    root: ET.Element,
    name: str,
    mixer_channel: int = 0,
    volume: int = 100,
    panning: int = 0,
) -> ET.Element:
    """Add a sample track to the project."""
    song = root.find("song")
    container = song.find("trackcontainer[@type='song']")

    track = ET.SubElement(container, "track", {
        "muted": "0",
        "type": "2",
        "name": name,
        "solo": "0",
    })

    sample_track = ET.SubElement(track, "sampletrack", {
        "pan": str(panning),
        "vol": str(volume),
    })
    ET.SubElement(sample_track, "fxchain", {
        "numofeffects": "0", "enabled": "0",
    })

    return track


def add_automation_track(root: ET.Element, name: str = "Automation track") -> ET.Element:
    """Add an automation track to the project."""
    song = root.find("song")
    container = song.find("trackcontainer[@type='song']")

    track = ET.SubElement(container, "track", {
        "muted": "0",
        "type": "5",
        "name": name,
        "solo": "0",
    })

    ET.SubElement(track, "automationtrack")

    return track


def add_pattern_track(root: ET.Element, name: str = "Pattern 0") -> ET.Element:
    """Add a beat/bassline pattern track to the project."""
    song = root.find("song")
    container = song.find("trackcontainer[@type='song']")

    track = ET.SubElement(container, "track", {
        "muted": "0",
        "type": "1",
        "name": name,
        "solo": "0",
    })

    bbtrack = ET.SubElement(track, "bbtrack")
    bb_container = ET.SubElement(bbtrack, "trackcontainer", {
        "width": "640", "x": "610", "y": "5", "maximized": "0",
        "height": "400", "visible": "0", "type": "bbtrackcontainer",
        "minimized": "0",
    })

    return track


def add_note_to_track(
    root: ET.Element,
    track_index: int,
    key: int = 60,
    pos: int = 0,
    length: int = 48,
    volume: int = 100,
    panning: int = 0,
    pattern_name: str | None = None,
) -> ET.Element:
    """Add a note to a pattern on an instrument track.

    Creates the pattern if it doesn't exist.
    """
    tracks = find_tracks(root)
    if track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range (have {len(tracks)} tracks)")

    track = tracks[track_index]
    track_type = get_track_type(track)

    if track_type == 0:
        pattern = track.find("pattern")
        if pattern is None:
            pname = pattern_name or track.get("name", "Pattern")
            pattern = ET.SubElement(track, "pattern", {
                "len": "192", "muted": "0", "name": pname,
                "steps": "16", "pos": "0", "type": "1",
            })
    elif track_type == 1:
        bbtrack = track.find("bbtrack")
        if bbtrack is None:
            raise ValueError("Pattern track has no bbtrack element")
        container = bbtrack.find("trackcontainer")
        if container is None:
            raise ValueError("Pattern track has no trackcontainer")
        inner_tracks = container.findall("track")
        if not inner_tracks:
            raise ValueError("Pattern track has no inner instruments")
        pattern = inner_tracks[0].find("pattern")
        if pattern is None:
            pname = pattern_name or "Pattern"
            pattern = ET.SubElement(inner_tracks[0], "pattern", {
                "len": "192", "muted": "0", "name": pname,
                "steps": "16", "pos": "0", "type": "1",
            })
    else:
        raise ValueError(f"Cannot add notes to track type {track_type_name(track_type)}")

    note = ET.SubElement(pattern, "note", {
        "len": str(length),
        "key": str(key),
        "vol": str(volume),
        "pos": str(pos),
        "pan": str(panning),
    })

    return note


def add_bb_clip(
    root: ET.Element,
    track_index: int,
    position: int = 0,
    length: int = 768,
) -> ET.Element:
    """Add a beat/bassline clip to a pattern track in the song editor."""
    tracks = find_tracks(root)
    if track_index >= len(tracks):
        raise IndexError(f"Track index {track_index} out of range")

    track = tracks[track_index]
    if get_track_type(track) != 1:
        raise ValueError("Can only add BB clips to pattern tracks (type=1)")

    clip = ET.SubElement(track, "bbtco", {
        "len": str(length),
        "muted": "0",
        "name": "",
        "usestyle": "1",
        "pos": str(position),
        "color": "4282417407",
    })

    return clip


def add_mixer_channel(
    root: ET.Element,
    name: str,
    volume: float = 1.0,
) -> ET.Element:
    """Add a new mixer channel to the project."""
    song = root.find("song")
    mixer = song.find("mixer")
    if mixer is None:
        raise ValueError("No mixer element found")

    existing = mixer.findall("mixerchannel")
    num = max(int(ch.get("num", "0")) for ch in existing) + 1

    channel = ET.SubElement(mixer, "mixerchannel", {
        "num": str(num),
        "muted": "0",
        "volume": str(volume),
        "name": name,
        "soloed": "0",
    })
    ET.SubElement(channel, "fxchain", {"numofeffects": "0", "enabled": "0"})

    return channel


def set_head_attribute(root: ET.Element, attr: str, value: str) -> None:
    """Set an attribute on the <head> element."""
    head = root.find("song/head")
    if head is None:
        head = root.find("head")
    if head is not None:
        head.set(attr, value)


# ──────────────────────────────────────────────────────────────────
# INSTRUMENT PARAMETER / PRESET SUPPORT
# ──────────────────────────────────────────────────────────────────

def find_track_element(root: ET.Element, index: int) -> ET.Element:
    """Find a track element by its position in the song trackcontainer."""
    song = root.find("song")
    container = song.find("trackcontainer[@type='song']")
    tracks = container.findall("track")
    if not 0 <= index < len(tracks):
        raise ValueError(
            f"Track index {index} out of range (0-{len(tracks) - 1})"
        )
    return tracks[index]


def set_instrument_params(
    root: ET.Element,
    track_index: int,
    params: dict,
) -> dict:
    """Set parameters on the <instrument> element of an instrument track.

    For zynaddsubfx these are: portamento, filterfreq, filterq, bandwidth,
    fmgain, rescenterfreq, resbandwidth, modifiedcontrollers.
    """
    track = find_track_element(root, track_index)
    inst_track = track.find("instrumenttrack")
    if inst_track is None:
        raise ValueError(f"Track {track_index} is not an instrument track")
    inst = inst_track.find("instrument")
    if inst is None:
        raise ValueError(f"Track {track_index} has no instrument element")

    applied = {}
    for key, value in params.items():
        inst.set(key, str(value))
        applied[key] = value

    return {
        "track_index": track_index,
        "instrument": inst.get("name"),
        "applied": applied,
    }


def embed_zyn_preset(
    root: ET.Element,
    track_index: int,
    preset_xml: str,
    preset_name: str = "",
) -> dict:
    """Embed ZynAddSubFX preset XML into a zynaddsubfx instrument track.

    Args:
        root: Project root element.
        track_index: Index of the target instrument track.
        preset_xml: Raw XML string from a .xiz preset file.
        preset_name: Optional display name for the result message.

    Returns:
        Dict with result info.

    Raises:
        ValueError: If track is not a zynaddsubfx instrument or the
            preset XML is invalid.
    """
    track = find_track_element(root, track_index)
    inst_track = track.find("instrumenttrack")
    if inst_track is None:
        raise ValueError(f"Track {track_index} is not an instrument track")
    inst = inst_track.find("instrument")
    if inst is None or inst.get("name") != "zynaddsubfx":
        actual = inst.get("name") if inst is not None else "none"
        raise ValueError(
            f"Track {track_index} uses '{actual}', not 'zynaddsubfx'. "
            f"Zyn presets can only be loaded on zynaddsubfx tracks."
        )

    # Validate and normalize the preset XML (strip DOCTYPE - ElementTree
    # cannot parse it and LMMS does not need it)
    import re as _re
    cleaned = _re.sub(r"<!DOCTYPE[^>]*>", "", preset_xml)
    try:
        preset_root = ET.fromstring(cleaned)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid preset XML: {exc}") from exc

    if preset_root.tag != "ZynAddSubFX-data":
        raise ValueError(
            f"Preset root element is '{preset_root.tag}', expected "
            f"'ZynAddSubFX-data'. Is this really a .xiz file?"
        )

    # Remove any existing embedded data, then append the new one
    for old in inst.findall("ZynAddSubFX-data"):
        inst.remove(old)
    inst.append(preset_root)

    # Extract patch name from preset INFO if available
    patch_name = preset_name
    try:
        info = preset_root.find("INSTRUMENT/INFO")
        if info is not None:
            name_el = info.find("string[@name='name']")
            if name_el is not None and name_el.text:
                patch_name = name_el.text.strip()
    except (AttributeError, TypeError):
        pass

    return {
        "track_index": track_index,
        "preset": patch_name or preset_name or "unknown",
        "message": f"Loaded ZynAddSubFX preset '{patch_name}' into track "
                   f"{track_index}",
    }
