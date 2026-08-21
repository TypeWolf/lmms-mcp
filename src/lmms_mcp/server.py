"""LMMS MCP Server - AI-powered music production with LMMS.

This server provides tools, resources, and prompts for creating and
manipulating LMMS projects programmatically via the Model Context Protocol.
"""

import json
import os
from pathlib import Path
from xml.etree import ElementTree as ET

from mcp.server import MCPServer

from . import effects as effects_mod
from . import presets as zyn_presets
from . import xml_parser
from .models import (
    NOTE_NAMES,
    TICKS_PER_BAR,
    TICKS_PER_STEP,
    STEPS_PER_BAR,
    TrackType,
    Note,
    midi_to_note_name,
    note_name_to_midi,
    bars_to_ticks,
    ticks_to_bars,
)
from .project import LMMSProject, get_project, set_project

DEFAULT_PROJECTS_DIR = os.environ.get(
    "LMMS_PROJECTS_DIR",
    str(Path.home() / "Desktop" / "Media" / "lmms" / "AI-Projects"),
)

# Real LMMS built-in instrument plugin names (as used in the XML
# <instrument name="..."> attribute). Verified against LMMS source.
KNOWN_INSTRUMENTS = {
    "tripleoscillator": "Three-oscillator subtractive synth (default, always works)",
    "kicker": "Kick drum synthesizer",
    "audiofileprocessor": "Audio file player/sampler (WAV, OGG, etc.)",
    "organic": "Additive organ synthesizer",
    "malletsstk": "Physical modeling mallets (STK)",
    "freeboy": "Game Boy sound chip emulator (chiptune)",
    "lb302": "Roland TB-303 style acid bass synth",
    "monstro": "Powerful 3-oscillator polyphonic synth",
    "nes": "NES 8-bit sound chip emulator (chiptune)",
    "opulenz": "OPL3 FM synthesizer (Yamaha DX100 style)",
    "patman": "GUS patch sampler",
    "sf2player": "SoundFont (.sf2) sample player",
    "sfxr": "Retro sound effect generator (chiptune)",
    "sid": "Commodore 64 SID chip emulator (chiptune)",
    "slicert": "Beat slicer for chopping audio loops",
    "vibedstrings": "Vibrating string physical model",
    "watsyn": "4-oscillator wavetable-style synth",
    "xpressive": "Expressive mono lead synth",
    "zynaddsubfx": "ZynAddSubFX powerful feature-rich synth",
    "gigplayer": "GIG sample library player",
    "bitinvader": "Bit-crushed wavetable synth",
    "vestige": "VST plugin host (Windows only)",
}

# Recommended instruments per use case - helps agents pick valid plugins
INSTRUMENT_RECOMMENDATIONS = {
    "drums": ["kicker", "audiofileprocessor", "sfxr"],
    "bass": ["lb302", "tripleoscillator", "monstro"],
    "lead": ["tripleoscillator", "watsyn", "xpressive", "opulenz"],
    "pad": ["organic", "zynaddsubfx", "monstro"],
    "chiptune": ["freeboy", "nes", "sid", "sfxr"],
    "keys": ["malletsstk", "opulenz", "zynaddsubfx"],
    "strings": ["vibedstrings", "zynaddsubfx"],
}

mcp = MCPServer(
    "LMMS MCP Server",
    instructions=f"""LMMS MCP Server for AI-powered music production.

This server lets you create, load, modify, and save LMMS music projects.
LMMS is a free, open-source digital audio workstation (DAW).

Key concepts:
- LMMS projects contain tracks (Instrument, Sample, Pattern, Automation)
- Instrument tracks hold synthesizer/sampler plugins and patterns with notes
- Pattern tracks (Beat/Bassline) hold drum patterns in the song editor
- The Mixer has channels (0=Master) where tracks route their audio
- Time is measured in ticks: 192 ticks = 1 bar (4/4 time)
- Notes use MIDI key numbers: 60=C4 (middle C), 69=A4
- Volume: 0-200 (100=normal), Panning: -100 to +100

IMPORTANT - Instruments: Only use built-in LMMS instrument names (see the
add_instrument_track tool description or lmms://reference/instruments).
LMMS has NO plugin download mechanism. If asked for a sound you cannot
produce, use tripleoscillator (universal synth) and explain the limitation.
Safe choices: tripleoscillator, kicker (drums), lb302 (bass),
freeboy/nes/sid (chiptune), organic (pads/organ).

ZynAddSubFX: For rich sounds, add a track with instrument "zynaddsubfx",
then load one of ~950 factory presets via load_zyn_preset (browse with
list_zyn_presets). Fine-tune with set_zyn_params.

Effects: Add built-in effects to tracks or mixer channels with add_effect
(see lmms://reference/effects for the full list). Typical chains:
- Lead: delay -> reverbsc
- Vocals: eq -> compressor -> reverbsc
- Master bus: eq -> compressor -> stereoenhancer

Default projects directory: {DEFAULT_PROJECTS_DIR}
When saving a project, use this directory if no specific path is given.
Example: save to {DEFAULT_PROJECTS_DIR}/my_song.mmpz

Workflow: Create a project -> Add tracks -> Load instruments/presets ->
Add notes -> Add effects -> Configure mixer -> Save
""",
)

# ──────────────────────────────────────────────────────────────────
# PROJECT TOOLS
# ──────────────────────────────────────────────────────────────────


@mcp.tool()
def create_project(
    bpm: int = 140,
    time_sig_numerator: int = 4,
    time_sig_denominator: int = 4,
    master_volume: int = 100,
    master_pitch: int = 0,
) -> str:
    """Create a new empty LMMS project.

    Args:
        bpm: Tempo in beats per minute (10-999)
        time_sig_numerator: Time signature numerator (e.g. 4 for 4/4)
        time_sig_denominator: Time signature denominator (e.g. 4 for 4/4)
        master_volume: Master volume (0-200, 100=normal)
        master_pitch: Master pitch offset in semitones (-12 to +12)
    """
    proj = LMMSProject()
    proj.new(
        bpm=bpm,
        time_sig_numerator=time_sig_numerator,
        time_sig_denominator=time_sig_denominator,
        master_volume=master_volume,
        master_pitch=master_pitch,
    )
    set_project(proj)
    return json.dumps({
        "message": "New project created",
        "bpm": bpm,
        "time_signature": f"{time_sig_numerator}/{time_sig_denominator}",
        "master_volume": master_volume,
        "master_pitch": master_pitch,
    })


@mcp.tool()
def load_project(path: str) -> str:
    """Load an existing LMMS project file (.mmpz or .mmp).

    Args:
        path: Full path to the LMMS project file
    """
    proj = LMMSProject()
    proj.load(path)
    set_project(proj)
    info = proj.get_info()
    return json.dumps({
        "message": f"Loaded project from {path}",
        "bpm": info.bpm,
        "time_signature": info.time_signature,
        "track_count": info.track_count,
        "tracks": [{"index": t.index, "name": t.name, "type": t.type_name} for t in info.tracks],
    })


@mcp.tool()
def save_project(
    path: str = "",
    compressed: bool = True,
) -> str:
    """Save the current LMMS project to a file.

    Args:
        path: File path to save to. If empty, saves to the default projects directory.
            If only a filename is given (e.g. "song.mmpz"), it's saved in the default directory.
        compressed: If True, saves as .mmpz (compressed). If False, saves as .mmp (XML).
    """
    proj = get_project()

    if not path and not proj.path:
        projects_dir = Path(DEFAULT_PROJECTS_DIR)
        projects_dir.mkdir(parents=True, exist_ok=True)
        save_path = str(projects_dir / "untitled.mmpz")
    elif path and not Path(path).is_absolute():
        projects_dir = Path(DEFAULT_PROJECTS_DIR)
        projects_dir.mkdir(parents=True, exist_ok=True)
        save_path = str(projects_dir / path)
    else:
        save_path = path if path else None

    result_path = proj.save(save_path, compressed=compressed) if save_path else proj.save(compressed=compressed)

    return json.dumps({
        "message": f"Project saved to {result_path}",
        "path": result_path,
        "compressed": compressed,
    })


@mcp.tool()
def get_project_info() -> str:
    """Get comprehensive information about the current LMMS project.

    Returns tempo, time signature, tracks, mixer channels, and more.
    """
    proj = get_project()
    info = proj.get_info()
    return json.dumps(info.to_dict(), indent=2)


@mcp.tool()
def get_project_xml() -> str:
    """Get the raw XML representation of the current project.

    Useful for debugging or understanding the exact project structure.
    """
    proj = get_project()
    return proj.get_xml_string()


# ──────────────────────────────────────────────────────────────────
# TRACK TOOLS
# ──────────────────────────────────────────────────────────────────


@mcp.tool()
def add_instrument_track(
    name: str,
    instrument: str = "tripleoscillator",
    mixer_channel: int = 0,
    volume: int = 100,
    panning: int = 0,
) -> str:
    """Add an instrument track to the project.

    Args:
        name: Track name (e.g. "Lead Synth", "Bass")
        instrument: Plugin name (lowercase). Valid options:
            tripleoscillator, kicker, audiofileprocessor, organic,
            malletsstk, freeboy, lb302, monstro, nes, opulenz,
            patman, sf2player, sfxr, sid, slicert, vibedstrings,
            watsyn, xpressive, zynaddsubfx, gigplayer, bitinvader
        mixer_channel: Mixer channel number (0=Master, 1+=custom channels)
        volume: Track volume (0-200, 100=normal)
        panning: Track panning (-100 to +100, 0=center)
    """
    proj = get_project()

    # Validate instrument name (case-insensitive fuzzy match)
    normalized = instrument.strip().lower()
    if normalized not in KNOWN_INSTRUMENTS:
        # Try common aliases / case variants
        alias_map = {
            "mallets": "malletsstk",
            "stk": "malletsstk",
            "sf2": "sf2player",
            "fluidsynth": "sf2player",
            "zynaddsubfx": "zynaddsubfx",
            "zyn": "zynaddsubfx",
            "zynadd": "zynaddsubfx",
            "audiofileprocessor": "audiofileprocessor",
            "audiofile": "audiofileprocessor",
            "afp": "audiofileprocessor",
            "lb-302": "lb302",
            "303": "lb302",
            "opl3": "opulenz",
            "opulenz": "opulenz",
        }
        resolved = alias_map.get(normalized)
        if resolved is None:
            suggestions = ", ".join(sorted(KNOWN_INSTRUMENTS.keys()))
            return json.dumps({
                "error": f"Unknown instrument '{instrument}'. "
                f"LMMS has no plugin download mechanism - only built-in "
                f"instruments can be used.",
                "valid_instruments": sorted(KNOWN_INSTRUMENTS.keys()),
                "hint": f"Use one of: {suggestions}. "
                f"Recommended: tripleoscillator (universal), kicker (drums), "
                f"lb302 (bass), freeboy/nes/sid (chiptune).",
            })
        normalized = resolved

    result = proj.add_track(
        "instrument", name,
        instrument=normalized,
        mixer_channel=mixer_channel,
        volume=volume,
        panning=panning,
    )
    return json.dumps(result)


@mcp.tool()
def add_sample_track(
    name: str,
    mixer_channel: int = 0,
    volume: int = 100,
    panning: int = 0,
) -> str:
    """Add a sample track for arranging audio files.

    Args:
        name: Track name
        mixer_channel: Mixer channel number (0=Master)
        volume: Track volume (0-200)
        panning: Track panning (-100 to +100)
    """
    proj = get_project()
    result = proj.add_track(
        "sample", name,
        mixer_channel=mixer_channel,
        volume=volume,
        panning=panning,
    )
    return json.dumps(result)


@mcp.tool()
def add_automation_track(name: str = "Automation track") -> str:
    """Add an automation track for parameter automation.

    Args:
        name: Track name
    """
    proj = get_project()
    result = proj.add_track("automation", name)
    return json.dumps(result)


@mcp.tool()
def add_pattern_track(name: str = "Pattern 0") -> str:
    """Add a beat/bassline pattern track for drum sequencing.

    Args:
        name: Pattern track name
    """
    proj = get_project()
    result = proj.add_track("pattern", name)
    return json.dumps(result)


@mcp.tool()
def remove_track(track_index: int) -> str:
    """Remove a track by its index.

    Args:
        track_index: Zero-based index of the track to remove
    """
    proj = get_project()
    result = proj.remove_track(track_index)
    return json.dumps(result)


@mcp.tool()
def get_track(track_index: int) -> str:
    """Get detailed information about a specific track.

    Args:
        track_index: Zero-based index of the track
    """
    proj = get_project()
    info = proj.get_info()
    if track_index >= len(info.tracks):
        return json.dumps({"error": f"Track index {track_index} out of range. Have {len(info.tracks)} tracks."})
    track = info.tracks[track_index]
    return json.dumps(track.to_dict(), indent=2)


@mcp.tool()
def list_tracks() -> str:
    """List all tracks in the current project with their index, name, and type."""
    proj = get_project()
    info = proj.get_info()
    tracks = [
        {
            "index": t.index,
            "name": t.name,
            "type": t.type_name,
            "instrument": t.instrument,
            "muted": t.muted,
            "patterns": len(t.patterns),
        }
        for t in info.tracks
    ]
    return json.dumps({"tracks": tracks, "count": len(tracks)}, indent=2)


@mcp.tool()
def set_track_volume(track_index: int, volume: int) -> str:
    """Set the volume of a track.

    Args:
        track_index: Zero-based track index
        volume: Volume level (0-200, 100=normal)
    """
    proj = get_project()
    from .xml_parser import find_tracks
    tracks = find_tracks(proj.root)
    if track_index >= len(tracks):
        return json.dumps({"error": f"Track index {track_index} out of range"})

    track = tracks[track_index]
    track_type = int(track.get("type", "0"))

    if track_type == 0:
        inst = track.find("instrumenttrack")
        if inst is not None:
            inst.set("vol", str(volume))
    elif track_type == 2:
        samp = track.find("sampletrack")
        if samp is not None:
            samp.set("vol", str(volume))

    proj._modified = True
    return json.dumps({"message": f"Set track {track_index} volume to {volume}"})


@mcp.tool()
def set_track_panning(track_index: int, panning: int) -> str:
    """Set the panning of a track.

    Args:
        track_index: Zero-based track index
        panning: Pan value (-100=left, 0=center, 100=right)
    """
    proj = get_project()
    from .xml_parser import find_tracks
    tracks = find_tracks(proj.root)
    if track_index >= len(tracks):
        return json.dumps({"error": f"Track index {track_index} out of range"})

    track = tracks[track_index]
    track_type = int(track.get("type", "0"))

    if track_type == 0:
        inst = track.find("instrumenttrack")
        if inst is not None:
            inst.set("pan", str(panning))
    elif track_type == 2:
        samp = track.find("sampletrack")
        if samp is not None:
            samp.set("pan", str(panning))

    proj._modified = True
    return json.dumps({"message": f"Set track {track_index} panning to {panning}"})


@mcp.tool()
def mute_track(track_index: int, muted: bool = True) -> str:
    """Mute or unmute a track.

    Args:
        track_index: Zero-based track index
        muted: True to mute, False to unmute
    """
    proj = get_project()
    from .xml_parser import find_tracks
    tracks = find_tracks(proj.root)
    if track_index >= len(tracks):
        return json.dumps({"error": f"Track index {track_index} out of range"})

    tracks[track_index].set("muted", "1" if muted else "0")
    proj._modified = True
    return json.dumps({"message": f"Track {track_index} {'muted' if muted else 'unmuted'}"})


@mcp.tool()
def solo_track(track_index: int, solo: bool = True) -> str:
    """Solo or unsolo a track.

    Args:
        track_index: Zero-based track index
        solo: True to solo, False to unsolo
    """
    proj = get_project()
    from .xml_parser import find_tracks
    tracks = find_tracks(proj.root)
    if track_index >= len(tracks):
        return json.dumps({"error": f"Track index {track_index} out of range"})

    tracks[track_index].set("solo", "1" if solo else "0")
    proj._modified = True
    return json.dumps({"message": f"Track {track_index} {'soloed' if solo else 'unsoloed'}"})


# ──────────────────────────────────────────────────────────────────
# NOTE / PATTERN TOOLS
# ──────────────────────────────────────────────────────────────────


@mcp.tool()
def add_note(
    track_index: int,
    key: int = 60,
    pos: int = 0,
    length: int = 48,
    volume: int = 100,
    panning: int = 0,
) -> str:
    """Add a note to a track's pattern.

    Args:
        track_index: Zero-based track index (must be an instrument or pattern track)
        key: MIDI note number (0-127). 60=C4 (middle C), 69=A4
        pos: Position in ticks within the pattern (192 ticks = 1 bar)
        length: Note length in ticks (48 = 1/16 note, 96 = 1/8 note, 192 = 1 bar)
        volume: Note velocity (0-200, 100=normal)
        panning: Note panning (-100 to +100)
    """
    proj = get_project()
    result = proj.add_note(
        track_index=track_index,
        key=key,
        pos=pos,
        length=length,
        volume=volume,
        panning=panning,
    )
    return json.dumps(result)


@mcp.tool()
def add_note_by_name(
    track_index: int,
    note_name: str = "C4",
    pos: int = 0,
    length: int = 48,
    volume: int = 100,
) -> str:
    """Add a note using a note name (e.g. 'C4', 'A#3', 'F#5').

    Args:
        track_index: Zero-based track index
        note_name: Note name like 'C4', 'A#3', 'F5', 'Bb2'
        pos: Position in ticks (192 ticks = 1 bar)
        length: Note length in ticks (48 = 1/16, 96 = 1/8, 192 = 1 bar)
        volume: Note velocity (0-200)
    """
    try:
        key = note_name_to_midi(note_name)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    proj = get_project()
    result = proj.add_note(
        track_index=track_index,
        key=key,
        pos=pos,
        length=length,
        volume=volume,
    )
    return json.dumps(result)


@mcp.tool()
def add_notes_batch(
    track_index: int,
    notes: list[dict],
) -> str:
    """Add multiple notes to a track at once.

    Args:
        track_index: Zero-based track index
        notes: List of note objects, each with: key (int or str like "C4"),
            pos (ticks), length (ticks, default 48), volume (0-200, default 100),
            panning (-100 to +100, default 0)
    """
    proj = get_project()
    added = []
    for note_data in notes:
        key = note_data.get("key", 60)
        if isinstance(key, str):
            try:
                key = note_name_to_midi(key)
            except ValueError as e:
                added.append({"error": str(e), "note": note_data})
                continue

        result = proj.add_note(
            track_index=track_index,
            key=key,
            pos=note_data.get("pos", 0),
            length=note_data.get("length", 48),
            volume=note_data.get("volume", 100),
            panning=note_data.get("panning", 0),
        )
        added.append(result)

    return json.dumps({"added": len(added), "notes": added})


# ──────────────────────────────────────────────────────────────────
# MIXER TOOLS
# ──────────────────────────────────────────────────────────────────


@mcp.tool()
def add_mixer_channel(name: str, volume: float = 1.0) -> str:
    """Add a new mixer channel.

    Args:
        name: Channel name (e.g. "Drums", "Bass", "Lead")
        volume: Channel volume (0.0-2.0, 1.0=0dB)
    """
    proj = get_project()
    result = proj.add_mixer_channel(name=name, volume=volume)
    return json.dumps(result)


@mcp.tool()
def get_mixer_channels() -> str:
    """Get all mixer channels with their settings."""
    proj = get_project()
    info = proj.get_info()
    channels = [ch.to_dict() for ch in info.mixer_channels]
    return json.dumps({"channels": channels, "count": len(channels)}, indent=2)


@mcp.tool()
def set_mixer_channel_volume(channel_num: int, volume: float) -> str:
    """Set the volume of a mixer channel.

    Args:
        channel_num: Channel number (0=Master)
        volume: Volume (0.0-2.0, 1.0=0dB)
    """
    proj = get_project()
    from .xml_parser import find_mixer_channels
    channels = find_mixer_channels(proj.root)
    for ch in channels:
        if int(ch.get("num", "-1")) == channel_num:
            ch.set("volume", str(volume))
            proj._modified = True
            return json.dumps({"message": f"Set mixer channel {channel_num} volume to {volume}"})
    return json.dumps({"error": f"Mixer channel {channel_num} not found"})


@mcp.tool()
def set_mixer_channel_name(channel_num: int, name: str) -> str:
    """Rename a mixer channel.

    Args:
        channel_num: Channel number (0=Master)
        name: New channel name
    """
    proj = get_project()
    from .xml_parser import find_mixer_channels
    channels = find_mixer_channels(proj.root)
    for ch in channels:
        if int(ch.get("num", "-1")) == channel_num:
            ch.set("name", name)
            proj._modified = True
            return json.dumps({"message": f"Renamed mixer channel {channel_num} to '{name}'"})
    return json.dumps({"error": f"Mixer channel {channel_num} not found"})


# ──────────────────────────────────────────────────────────────────
# EFFECT (FXCHAIN) TOOLS
# ──────────────────────────────────────────────────────────────────


def _resolve_fxchain_target(target_type: str, target_index: int) -> ET.Element:
    """Resolve a track or mixer channel element for fxchain operations."""
    proj = get_project()
    root = proj.root
    if target_type == "track":
        return xml_parser.find_track_element(root, target_index)
    if target_type == "mixer":
        song = root.find("song")
        mixer = song.find("mixer")
        channels = mixer.findall("mixerchannel")
        if not 0 <= target_index < len(channels):
            raise ValueError(
                f"Mixer channel {target_index} out of range "
                f"(0-{len(channels) - 1})"
            )
        return channels[target_index]
    raise ValueError("target_type must be 'track' or 'mixer'")


@mcp.tool()
def add_effect(
    target_type: str,
    target_index: int,
    effect: str,
    wet: float = 1.0,
    enabled: bool = True,
    position: int | None = None,
) -> str:
    """Add an effect to a track's or mixer channel's effect chain.

    Args:
        target_type: "track" or "mixer"
        target_index: Track index or mixer channel number (0=Master)
        effect: Built-in LMMS effect name. Valid: amplifier, bassbooster,
            bitcrush, compressor, crossovereq, delay, dispersion,
            dualfilter, dynamicsprocessor, eq, flanger, frequencyshifter,
            multitapecho, reverbsc, slewdistortion, stereoenhancer,
            stereomatrix, waveshaper
        wet: Wet/dry mix 0.0-1.0 (1.0=full effect)
        enabled: Whether the effect is active
        position: Chain position to insert at (None=end of chain)
    """
    try:
        parent = _resolve_fxchain_target(target_type, target_index)
        result = effects_mod.add_effect(parent, effect, wet, enabled, position)
        return json.dumps(result)
    except ValueError as exc:
        return json.dumps({
            "error": str(exc),
            "valid_effects": sorted(effects_mod.KNOWN_EFFECTS.keys()),
            "recommendations": effects_mod.EFFECT_RECOMMENDATIONS,
        })


@mcp.tool()
def remove_effect(target_type: str, target_index: int, effect: str | int) -> str:
    """Remove an effect from a chain by name or chain position.

    Args:
        target_type: "track" or "mixer"
        target_index: Track index or mixer channel number
        effect: Effect name (e.g. "delay") or position (e.g. 0)
    """
    try:
        parent = _resolve_fxchain_target(target_type, target_index)
        result = effects_mod.remove_effect(parent, effect)
        return json.dumps(result)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def toggle_effect(
    target_type: str, target_index: int, effect: str | int, enabled: bool
) -> str:
    """Enable or disable an effect without removing it.

    Args:
        target_type: "track" or "mixer"
        target_index: Track index or mixer channel number
        effect: Effect name or chain position
        enabled: True to enable, False to bypass
    """
    try:
        parent = _resolve_fxchain_target(target_type, target_index)
        result = effects_mod.set_effect_enabled(parent, effect, enabled)
        return json.dumps(result)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def get_effect_chain(target_type: str, target_index: int) -> str:
    """List all effects on a track's or mixer channel's effect chain.

    Args:
        target_type: "track" or "mixer"
        target_index: Track index or mixer channel number
    """
    try:
        parent = _resolve_fxchain_target(target_type, target_index)
        return json.dumps({
            "target": f"{target_type}[{target_index}]",
            "effects": effects_mod.list_effects(parent),
        })
    except ValueError as exc:
        return json.dumps({"error": str(exc)})


# ──────────────────────────────────────────────────────────────────
# ZYNADDSUBFX PRESET / PARAMETER TOOLS
# ──────────────────────────────────────────────────────────────────


@mcp.tool()
def list_zyn_presets(category: str | None = None) -> str:
    """List available ZynAddSubFX presets (.xiz files).

    Args:
        category: Optional category filter (e.g. "Bass", "Strings",
            "Synth", "Pads", "Brass"). Omit to list all categories' presets.
    """
    base = zyn_presets.get_presets_dir()
    if base is None:
        return json.dumps({
            "error": "No ZynAddSubFX presets directory found.",
            "hint": "Set the LMMS_PRESETS_DIR environment variable to your "
                    "LMMS data/presets/ZynAddSubFX folder.",
        })
    try:
        presets = zyn_presets.list_presets(category)
    except ValueError as exc:
        return json.dumps({
            "error": str(exc),
            "categories": zyn_presets.list_categories(),
        })
    return json.dumps({
        "presets_dir": str(base),
        "categories": zyn_presets.list_categories(),
        "count": len(presets),
        "presets": presets[:200],
        "truncated": len(presets) > 200,
    }, indent=2)


@mcp.tool()
def load_zyn_preset(track_index: int, preset: str) -> str:
    """Load a ZynAddSubFX preset (.xiz) into a zynaddsubfx instrument track.

    The track must use the 'zynaddsubfx' instrument. Presets can be
    referenced by filename (e.g. "Bass 1"), "Category/Name", or full path.

    Args:
        track_index: Index of the target track
        preset: Preset name, "Category/Name" or absolute path
    """
    proj = get_project()
    try:
        preset_xml = zyn_presets.load_preset_xml(preset)
        result = xml_parser.embed_zyn_preset(proj.root, track_index, preset_xml, preset)
        return json.dumps(result)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def set_zyn_params(
    track_index: int,
    portamento: int | None = None,
    filterfreq: int | None = None,
    filterq: int | None = None,
    bandwidth: int | None = None,
    fmgain: int | None = None,
    rescenterfreq: int | None = None,
    resbandwidth: int | None = None,
) -> str:
    """Set ZynAddSubFX global parameters on a zynaddsubfx track.

    All values are 0-127 as in the ZynAddSubFX UI. Only provided
    parameters are changed.

    Args:
        track_index: Index of the zynaddsubfx track
        portamento: Portamento amount (0-127)
        filterfreq: Filter cutoff frequency (0-127)
        filterq: Filter resonance/Q (0-127)
        bandwidth: Bandwidth (0-127)
        fmgain: FM gain (0-127)
        rescenterfreq: Resonance center frequency (0-127)
        resbandwidth: Resonance bandwidth (0-127)
    """
    proj = get_project()
    params = {}
    for name, value in [
        ("portamento", portamento), ("filterfreq", filterfreq),
        ("filterq", filterq), ("bandwidth", bandwidth),
        ("fmgain", fmgain), ("rescenterfreq", rescenterfreq),
        ("resbandwidth", resbandwidth),
    ]:
        if value is not None:
            if not 0 <= value <= 127:
                return json.dumps({
                    "error": f"{name} must be 0-127, got {value}"
                })
            params[name] = value
    if not params:
        return json.dumps({"error": "No parameters provided"})
    try:
        result = xml_parser.set_instrument_params(proj.root, track_index, params)
        # Mark modified controllers so LMMS applies them on load
        inst_track = xml_parser.find_track_element(proj.root, track_index) \
            .find("instrumenttrack/instrument")
        controllers = {
            "portamento": 1, "filterfreq": 2, "filterq": 3,
            "bandwidth": 4, "fmgain": 5,
            "rescenterfreq": 6, "resbandwidth": 7,
        }
        modified = sorted(controllers[p] for p in params if p in controllers)
        inst_track.set("modifiedcontrollers", ",".join(map(str, modified)))
        result["modifiedcontrollers"] = modified
        return json.dumps(result)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})


# ──────────────────────────────────────────────────────────────────
# ARRANGEMENT TOOLS (SONG EDITOR TIMELINE)
# ──────────────────────────────────────────────────────────────────


@mcp.tool()
def assign_sample_file(track_index: int, file_path: str) -> str:
    """Assign an audio file to all clips on a sample track.

    Use relative paths for LMMS's built-in samples (e.g.
    "drums/kick01.ogg") or absolute paths for your own files.

    Args:
        track_index: Index of the sample track
        file_path: Audio file path (WAV/OGG/MP3/FLAC)
    """
    proj = get_project()
    try:
        track = xml_parser.find_track_element(proj.root, track_index)
        if xml_parser.get_track_type(track) != 2:
            return json.dumps({
                "error": f"Track {track_index} is not a sample track"
            })
        clips = track.findall("sampleclip")
        if not clips:
            clip = xml_parser.add_sample_clip(
                proj.root, track_index, file_path, position=0
            )
            count = 1
        else:
            for clip in clips:
                clip.set("src", file_path)
            count = len(clips)
        return json.dumps({
            "track_index": track_index,
            "file": file_path,
            "clips_updated": count,
            "message": f"Assigned '{file_path}' to {count} clip(s) "
                       f"on track {track_index}",
        })
    except (ValueError, IndexError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def place_sample_clip(
    track_index: int,
    file_path: str,
    pos_bars: float = 0,
    length_bars: float = 1,
) -> str:
    """Place an audio file clip on a sample track at a given bar.

    Args:
        track_index: Index of the sample track
        file_path: Audio file path (relative to LMMS samples or absolute)
        pos_bars: Start position in bars (0 = beginning)
        length_bars: Clip length in bars
    """
    proj = get_project()
    pos = bars_to_ticks(pos_bars)
    length = bars_to_ticks(length_bars)
    try:
        clip = xml_parser.add_sample_clip(proj.root, track_index, file_path, pos, length)
        return json.dumps({
            "track_index": track_index,
            "file": file_path,
            "pos_ticks": pos,
            "len_ticks": length,
            "message": f"Placed '{file_path}' at bar {pos_bars} "
                       f"({pos} ticks)",
        })
    except (ValueError, IndexError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def place_pattern(
    track_index: int,
    pos_bars: float = 0,
    name: str | None = None,
    length_bars: float = 1,
) -> str:
    """Place an empty pattern clip on an instrument track (song arrangement).

    The pattern starts empty; add notes with add_note (they go into the
    first pattern) or use this to sketch the arrangement structure first.

    Args:
        track_index: Index of the instrument track
        pos_bars: Start position in bars (0 = beginning)
        name: Optional pattern name (defaults to track name)
        length_bars: Pattern length in bars
    """
    proj = get_project()
    pos = bars_to_ticks(pos_bars)
    length = bars_to_ticks(length_bars)
    try:
        pattern = xml_parser.place_instrument_pattern(
            proj.root, track_index, pos, name, length
        )
        return json.dumps({
            "track_index": track_index,
            "pattern_name": pattern.get("name"),
            "pos_ticks": pos,
            "len_ticks": length,
            "message": f"Placed pattern '{pattern.get('name')}' at bar "
                       f"{pos_bars} on track {track_index}",
        })
    except (ValueError, IndexError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def place_bb_clip(
    bb_track_index: int,
    pos_bars: float = 0,
    length_bars: float = 4,
) -> str:
    """Place a beat/bassline clip on a pattern track in the song editor.

    This triggers the BB pattern (created via add_pattern_track and
    filled with notes) to play at the given time.

    Args:
        bb_track_index: Index of the pattern (BB) track
        pos_bars: Start position in bars
        length_bars: Clip length in bars (default 4 = one BB cycle of 16 steps)
    """
    proj = get_project()
    pos = bars_to_ticks(pos_bars)
    length = bars_to_ticks(length_bars)
    try:
        clip = xml_parser.add_bb_clip(proj.root, bb_track_index, pos, length)
        return json.dumps({
            "track_index": bb_track_index,
            "pos_ticks": pos,
            "len_ticks": length,
            "message": f"Placed BB clip at bar {pos_bars} "
                       f"(length {length_bars} bars)",
        })
    except (ValueError, IndexError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def move_clip(track_index: int, old_pos_bars: float, new_pos_bars: float) -> str:
    """Move a clip (pattern/bbtco/sampleclip) to a new time position.

    Args:
        track_index: Track containing the clip
        old_pos_bars: Current start position in bars
        new_pos_bars: New start position in bars
    """
    proj = get_project()
    try:
        result = xml_parser.move_clip(
            proj.root,
            track_index,
            bars_to_ticks(old_pos_bars),
            bars_to_ticks(new_pos_bars),
        )
        return json.dumps(result)
    except (ValueError, IndexError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def delete_clip(track_index: int, pos_bars: float) -> str:
    """Delete a clip at a given position from a track.

    Args:
        track_index: Track containing the clip
        pos_bars: Clip start position in bars
    """
    proj = get_project()
    try:
        result = xml_parser.delete_clip(proj.root, track_index, bars_to_ticks(pos_bars))
        return json.dumps(result)
    except (ValueError, IndexError) as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def get_arrangement() -> str:
    """Get the full song editor arrangement: all clips sorted by time.

    Shows every pattern, BB clip, sample clip and automation curve with
    their positions and lengths in ticks and bars.
    """
    proj = get_project()
    clips = xml_parser.get_arrangement(proj.root)
    for c in clips:
        c["pos_bars"] = round(ticks_to_bars(c["pos"]), 3)
        c["len_bars"] = round(ticks_to_bars(c["len"]), 3)
    total = max((c["pos"] + c["len"] for c in clips), default=0)
    return json.dumps({
        "clip_count": len(clips),
        "song_length_bars": round(ticks_to_bars(total), 2),
        "clips": clips,
    }, indent=2)


# ──────────────────────────────────────────────────────────────────
# AUTOMATION TOOLS
# ──────────────────────────────────────────────────────────────────


@mcp.tool()
def add_automation(
    target_type: str,
    param: str,
    points: list[dict],
    target_index: int = 0,
    name: str | None = None,
    smooth: bool = True,
) -> str:
    """Create an automation curve that controls a parameter over time.

    Automatable targets:
    - song + tempo: Song BPM (e.g. tempo ramps)
    - song + master_volume / master_pitch
    - track + volume / panning (target_index = track index)
    - mixer + volume (target_index = mixer channel number)

    Args:
        target_type: "song", "track" or "mixer"
        param: Parameter name (see above)
        points: Curve points as list of {"bar": float, "value": float}.
            Example: [{"bar": 0, "value": 120}, {"bar": 8, "value": 140}]
        target_index: Track index or mixer channel (ignored for "song")
        name: Automation name (defaults to parameter name)
        smooth: True = smooth curves (cubic), False = linear steps
    """
    proj = get_project()
    if not points:
        return json.dumps({"error": "points list is empty"})

    # Convert bar-based points to tick-based
    tick_points: list[tuple[int, float]] = []
    for i, pt in enumerate(points):
        try:
            bar = float(pt["bar"])
            value = float(pt["value"])
        except (KeyError, TypeError, ValueError):
            return json.dumps({
                "error": f"Point {i} must be {{'bar': float, 'value': float}}"
            })
        tick_points.append((bars_to_ticks(bar), value))

    try:
        model_id, current_value = xml_parser.resolve_automation_target(
            proj.root, target_type, target_index, param
        )
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    auto_name = name or param.replace("_", " ").title()
    try:
        track = xml_parser.add_automation_track(
            proj.root,
            auto_name,
            tick_points,
            target_id=model_id,
            progression=1 if smooth else 0,
        )
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    tracks = xml_parser.find_tracks(proj.root)
    return json.dumps({
        "automating": f"{target_type}[{target_index}].{param}",
        "current_value": current_value,
        "model_id": model_id,
        "automation_track_index": len(tracks) - 1,
        "points": len(tick_points),
        "smooth": smooth,
        "message": f"Created automation '{auto_name}' controlling "
                   f"{target_type}[{target_index}].{param} with "
                   f"{len(tick_points)} points",
    })


# ──────────────────────────────────────────────────────────────────
# TRANSPORT / SONG SETTINGS TOOLS
# ──────────────────────────────────────────────────────────────────


@mcp.tool()
def set_tempo(bpm: int) -> str:
    """Set the song tempo (BPM).

    Args:
        bpm: Tempo in beats per minute (10-999)
    """
    proj = get_project()
    proj.set_tempo(bpm)
    return json.dumps({"message": f"Tempo set to {bpm} BPM"})


@mcp.tool()
def set_time_signature(numerator: int, denominator: int) -> str:
    """Set the time signature.

    Args:
        numerator: Beats per bar (e.g. 4, 3, 6)
        denominator: Beat unit (e.g. 4 for quarter notes, 8 for eighth notes)
    """
    proj = get_project()
    proj.set_time_signature(numerator, denominator)
    return json.dumps({"message": f"Time signature set to {numerator}/{denominator}"})


@mcp.tool()
def set_master_volume(volume: int) -> str:
    """Set the master volume.

    Args:
        volume: Master volume (0-200, 100=normal)
    """
    proj = get_project()
    proj.set_master_volume(volume)
    return json.dumps({"message": f"Master volume set to {volume}"})


@mcp.tool()
def set_master_pitch(pitch: int) -> str:
    """Set the master pitch offset.

    Args:
        pitch: Pitch offset in semitones (-12 to +12)
    """
    proj = get_project()
    proj.set_master_pitch(pitch)
    return json.dumps({"message": f"Master pitch set to {pitch} semitones"})


# ──────────────────────────────────────────────────────────────────
# UTILITY / CONVERSION TOOLS
# ──────────────────────────────────────────────────────────────────


@mcp.tool()
def note_name_to_key(name: str) -> str:
    """Convert a note name (e.g. 'C4') to its MIDI key number.

    Args:
        name: Note name like 'C4', 'A#3', 'F#5', 'Bb2'
    """
    try:
        key = note_name_to_midi(name)
        return json.dumps({"note": name, "midi_key": key})
    except ValueError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def key_to_note_name(key: int) -> str:
    """Convert a MIDI key number to its note name.

    Args:
        key: MIDI key number (0-127)
    """
    if not 0 <= key <= 127:
        return json.dumps({"error": "MIDI key must be 0-127"})
    return json.dumps({"midi_key": key, "note": midi_to_note_name(key)})


@mcp.tool()
def bars_to_ticks_converter(bars: int) -> str:
    """Convert bars to ticks (192 ticks per bar in 4/4 time).

    Args:
        bars: Number of bars
    """
    ticks = bars_to_ticks(bars)
    return json.dumps({"bars": bars, "ticks": ticks, "ticks_per_bar": TICKS_PER_BAR})


@mcp.tool()
def ticks_to_bars_converter(ticks: int) -> str:
    """Convert ticks to bars (192 ticks per bar in 4/4 time).

    Args:
        ticks: Number of ticks
    """
    bars = ticks_to_bars(ticks)
    return json.dumps({"ticks": ticks, "bars": round(bars, 3), "ticks_per_bar": TICKS_PER_BAR})


@mcp.tool()
def generate_scale(
    root_note: str = "C4",
    scale_type: str = "major",
    num_octaves: int = 1,
) -> str:
    """Generate a musical scale as MIDI key numbers and note names.

    Args:
        root_note: Root note name (e.g. 'C4', 'A3')
        scale_type: Scale type: major, minor, dorian, mixolydian, pentatonic_major,
            pentatonic_minor, blues, chromatic, harmonic_minor, melodic_minor
        num_octaves: Number of octaves to generate
    """
    scales = {
        "major": [0, 2, 4, 5, 7, 9, 11],
        "minor": [0, 2, 3, 5, 7, 8, 10],
        "dorian": [0, 2, 3, 5, 7, 9, 10],
        "mixolydian": [0, 2, 4, 5, 7, 9, 10],
        "pentatonic_major": [0, 2, 4, 7, 9],
        "pentatonic_minor": [0, 3, 5, 7, 10],
        "blues": [0, 3, 5, 6, 7, 10],
        "chromatic": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
        "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
    }

    if scale_type not in scales:
        return json.dumps({"error": f"Unknown scale type: {scale_type}. Use: {list(scales.keys())}"})

    try:
        root_key = note_name_to_midi(root_note)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    intervals = scales[scale_type]
    notes = []
    for octave in range(num_octaves):
        for interval in intervals:
            key = root_key + octave * 12 + interval
            if key <= 127:
                notes.append({
                    "key": key,
                    "note": midi_to_note_name(key),
                    "position": len(notes),
                })

    return json.dumps({
        "root": root_note,
        "scale": scale_type,
        "notes": notes,
        "count": len(notes),
    })


# ──────────────────────────────────────────────────────────────────
# RESOURCES
# ──────────────────────────────────────────────────────────────────


@mcp.resource("lmms://project/info")
def resource_project_info() -> str:
    """Get current LMMS project information."""
    proj = get_project()
    info = proj.get_info()
    return json.dumps(info.to_dict(), indent=2)


@mcp.resource("lmms://project/tracks")
def resource_project_tracks() -> str:
    """Get all tracks in the current project."""
    proj = get_project()
    info = proj.get_info()
    tracks = [t.to_dict() for t in info.tracks]
    return json.dumps({"tracks": tracks}, indent=2)


@mcp.resource("lmms://project/mixer")
def resource_project_mixer() -> str:
    """Get all mixer channels in the current project."""
    proj = get_project()
    info = proj.get_info()
    channels = [ch.to_dict() for ch in info.mixer_channels]
    return json.dumps({"mixer_channels": channels}, indent=2)


@mcp.resource("lmms://project/xml")
def resource_project_xml() -> str:
    """Get the raw XML of the current project."""
    proj = get_project()
    return proj.get_xml_string()


@mcp.resource("lmms://reference/instruments")
def resource_instruments() -> str:
    """List of available LMMS instruments/plugins (built-in, verified)."""
    return json.dumps({
        "note": "These are ALL built-in LMMS instruments. LMMS cannot "
                "download additional plugins - do not use any other names.",
        "instruments": [
            {"name": name, "description": desc}
            for name, desc in sorted(KNOWN_INSTRUMENTS.items())
        ],
        "recommendations_by_use_case": INSTRUMENT_RECOMMENDATIONS,
    }, indent=2)


@mcp.resource("lmms://reference/effects")
def resource_effects() -> str:
    """List of available LMMS effects (built-in, verified)."""
    return json.dumps({
        "note": "These are ALL built-in LMMS effects. External-host "
                "effects (ladspaeffect, lv2effect, vsteffect) depend on "
                "system plugins and should be avoided.",
        "effects": [
            {"name": name, "description": desc, "controls_node": node}
            for name, (desc, node) in sorted(KNOWN_EFFECTS.items())
        ],
        "recommendations_by_use_case": EFFECT_RECOMMENDATIONS,
    }, indent=2)


@mcp.resource("lmms://reference/note_names")
def resource_note_names() -> str:
    """MIDI note number to note name mapping reference."""
    mapping = []
    for key in range(128):
        mapping.append({
            "key": key,
            "note": midi_to_note_name(key),
        })
    return json.dumps({"mapping": mapping, "total": 128}, indent=2)


@mcp.resource("lmms://reference/scales")
def resource_scales() -> str:
    """Available musical scales and their intervals."""
    return json.dumps({
        "scales": {
            "major": {"intervals": [0, 2, 4, 5, 7, 9, 11], "name": "Major (Ionian)"},
            "minor": {"intervals": [0, 2, 3, 5, 7, 8, 10], "name": "Natural Minor (Aeolian)"},
            "dorian": {"intervals": [0, 2, 3, 5, 7, 9, 10], "name": "Dorian Mode"},
            "mixolydian": {"intervals": [0, 2, 4, 5, 7, 9, 10], "name": "Mixolydian Mode"},
            "pentatonic_major": {"intervals": [0, 2, 4, 7, 9], "name": "Major Pentatonic"},
            "pentatonic_minor": {"intervals": [0, 3, 5, 7, 10], "name": "Minor Pentatonic"},
            "blues": {"intervals": [0, 3, 5, 6, 7, 10], "name": "Blues Scale"},
            "chromatic": {"intervals": list(range(12)), "name": "Chromatic"},
            "harmonic_minor": {"intervals": [0, 2, 3, 5, 7, 8, 11], "name": "Harmonic Minor"},
            "melodic_minor": {"intervals": [0, 2, 3, 5, 7, 9, 11], "name": "Melodic Minor"},
        },
    }, indent=2)


# ──────────────────────────────────────────────────────────────────
# PROMPTS
# ──────────────────────────────────────────────────────────────────


@mcp.prompt()
def create_basic_song(
    genre: str = "electronic",
    bpm: int = 120,
    key: str = "C4",
) -> str:
    """Create a basic song structure with drums, bass, and melody.

    Args:
        genre: Musical genre (electronic, rock, hip-hop, jazz, pop, ambient)
        bpm: Tempo in beats per minute
        key: Root note for the melody (e.g. 'C4', 'A3')
    """
    return f"""Create a {genre} song at {bpm} BPM in the key of {key}.

Steps:
1. Create a new project with {bpm} BPM
2. Add an instrument track "Drums" with kicker or audiofileprocessor
3. Add an instrument track "Bass" with tripleoscillator or LB302
4. Add an instrument track "Melody" with tripleoscillator or watsyn
5. Add an automation track for volume/parameter automation
6. Add notes to each track following {genre} conventions
7. Configure mixer channels
8. Save the project

Use the LMMS MCP tools to build this song step by step."""


@mcp.prompt()
def add_drum_pattern(
    pattern_style: str = "four_on_the_floor",
    steps: int = 16,
) -> str:
    """Create a drum pattern for the current project.

    Args:
        pattern_style: Drum pattern style (four_on_the_floor, breakbeat,
            hiphop, trap, rock_basic, waltz)
        steps: Number of steps in the pattern (16 or 32)
    """
    patterns = {
        "four_on_the_floor": "Classic 4/4 dance beat: kick on 1,3,5,7,9,11,13,15; snare on 5,13; hi-hat on every even step",
        "breakbeat": "Syncopated drum pattern with kick on 1,6,11; snare on 5,13; hi-hats on off-beats",
        "hiphop": "Boom-bap style: kick on 1,7; snare on 5,13; hi-hats on every 2nd step with swing",
        "trap": "Heavy 808s: kick on 1,9; snare on 5,13; rapid hi-hat rolls on every step",
        "rock_basic": "Standard rock beat: kick on 1,9; snare on 5,13; hi-hats on all steps",
        "waltz": "3/4 time: kick on 1; snare on 3,5; hi-hats on every step",
    }

    description = patterns.get(pattern_style, f"Custom {pattern_style} pattern")

    return f"""Create a drum pattern with style: {pattern_style}.

Description: {description}

Steps:
1. Find or create an instrument track for drums
2. Add notes at the correct positions:
   - Use position values: step * 12 ticks (12 ticks per 1/16 step)
   - Each step is 12 ticks apart
   - Total pattern length: {steps} steps = {steps * 12} ticks
3. Typical MIDI keys for drums:
   - Key 36 = Kick Drum
   - Key 38 = Snare
   - Key 42 = Closed Hi-Hat
   - Key 46 = Open Hi-Hat
   - Key 49 = Crash Cymbal
   - Key 51 = Ride Cymbal
4. Use the add_notes_batch tool for efficient note creation"""


@mcp.prompt()
def create_melody(
    scale_type: str = "major",
    root_note: str = "C4",
    bars: int = 4,
    style: str = "simple",
) -> str:
    """Generate a melody for the current project.

    Args:
        scale_type: Musical scale (major, minor, pentatonic_major, blues, etc.)
        root_note: Root note of the scale
        bars: Number of bars for the melody
        style: Melodic style (simple, complex, arpeggiated, chordal)
    """
    return f"""Create a melody in {scale_type} scale starting on {root_note}.

Parameters:
- Scale: {scale_type} starting at {root_note}
- Duration: {bars} bars ({bars * 192} ticks)
- Style: {style}

Steps:
1. Use the generate_scale tool to get the scale notes
2. Create or find a melody instrument track (tripleoscillator, watsyn, etc.)
3. Add notes following the {style} style:
   - Simple: Use mostly scale tones on strong beats
   - Complex: Use chromatic passing tones and syncopation
   - Arpeggiated: Break chords into ascending/descending patterns
   - Chordal: Stack notes to form chords
4. Position notes within the pattern:
   - 1 bar = 192 ticks
   - 1/4 note = 48 ticks
   - 1/8 note = 24 ticks
   - 1/16 note = 12 ticks"""


@mcp.prompt()
def mix_and_arrange() -> str:
    """Mix and arrange the current project.

    Guides through volume balancing, panning, and arrangement decisions.
    """
    return """Review and improve the current project's mix and arrangement.

Steps:
1. Get project info to see all tracks and mixer channels
2. For each track, consider:
   - Set appropriate volume levels (drums ~80-100, bass ~70-90, melody ~60-80)
   - Add panning for stereo width (bass center, hi-hats slightly left/right)
   - Route tracks to dedicated mixer channels
3. Create mixer channels if needed for:
   - Drum bus
   - Bass bus
   - Lead/Melody bus
   - FX returns (reverb, delay)
4. Adjust mixer channel volumes
5. Save the project"""


@mcp.prompt()
def export_project(
    format: str = "mmpz",
    path: str = "",
) -> str:
    """Export/save the current project.

    Args:
        format: Export format (mmpz=compressed, mmp=uncompressed XML, wav=render audio)
        path: Output file path
    """
    if format == "wav":
        return """To export as WAV audio, the project needs to be rendered using LMMS.

Steps:
1. Save the project first using save_project
2. Render using: lmms --render <project.mmpz> -o <output.wav>
3. Or use the --export option in LMMS GUI

Note: The MCP server can create and modify project files,
but audio rendering requires the LMMS application."""
    else:
        return f"""Save the project in {format} format.

Steps:
1. Use save_project with path='{path}' and compressed={format == 'mmpz'}
2. The project will be saved as {'compressed .mmpz' if format == 'mmpz' else 'uncompressed .mmp'}"""


# ──────────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────────


def main():
    """Run the LMMS MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
