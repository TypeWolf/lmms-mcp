"""Python data models for LMMS project structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class TrackType(IntEnum):
    INSTRUMENT = 0
    PATTERN = 1
    SAMPLE = 2
    EVENT = 3
    VIDEO = 4
    AUTOMATION = 5
    HIDDEN_AUTOMATION = 6


TICKS_PER_BAR = 192
TICKS_PER_STEP = 12
STEPS_PER_BAR = 16
DEFAULT_BPM = 140


@dataclass
class Note:
    key: int = 60
    pos: int = 0
    length: int = 48
    volume: int = 100
    panning: int = 0

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "pos": self.pos,
            "length": self.length,
            "volume": self.volume,
            "panning": self.panning,
            "note_name": midi_to_note_name(self.key),
        }

    @staticmethod
    def from_dict(d: dict) -> Note:
        return Note(
            key=d.get("key", 60),
            pos=d.get("pos", 0),
            length=d.get("length", 48),
            volume=d.get("volume", 100),
            panning=d.get("panning", 0),
        )


@dataclass
class Pattern:
    name: str = "Pattern"
    pattern_type: int = 1
    steps: int = 16
    length: int = 192
    muted: bool = False
    notes: list[Note] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.pattern_type,
            "steps": self.steps,
            "length": self.length,
            "muted": self.muted,
            "notes": [n.to_dict() for n in self.notes],
        }


@dataclass
class Track:
    track_type: TrackType = TrackType.INSTRUMENT
    name: str = "Unnamed"
    muted: bool = False
    solo: bool = False
    volume: int = 100
    panning: int = 0
    mixer_channel: int = 0
    instrument: str = ""
    patterns: list[Pattern] = field(default_factory=list)
    index: int = 0

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "type": int(self.track_type),
            "type_name": self.track_type.name,
            "name": self.name,
            "muted": self.muted,
            "solo": self.solo,
            "volume": self.volume,
            "panning": self.panning,
            "mixer_channel": self.mixer_channel,
            "instrument": self.instrument,
            "patterns": [p.to_dict() for p in self.patterns],
        }


@dataclass
class MixerChannel:
    num: int = 0
    name: str = "Master"
    volume: float = 1.0
    muted: bool = False
    soloed: bool = False
    effects: list[str] = field(default_factory=list)
    sends: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "num": self.num,
            "name": self.name,
            "volume": self.volume,
            "muted": self.muted,
            "soloed": self.soloed,
            "effects": self.effects,
            "sends": self.sends,
        }


@dataclass
class SongInfo:
    bpm: int = 140
    time_sig_numerator: int = 4
    time_sig_denominator: int = 4
    master_volume: int = 100
    master_pitch: int = 0
    tracks: list[Track] = field(default_factory=list)
    mixer_channels: list[MixerChannel] = field(default_factory=list)
    file_path: str = ""
    modified: bool = False

    def to_dict(self) -> dict:
        return {
            "bpm": self.bpm,
            "time_signature": f"{self.time_sig_numerator}/{self.time_sig_denominator}",
            "master_volume": self.master_volume,
            "master_pitch": self.master_pitch,
            "file_path": self.file_path,
            "modified": self.modified,
            "track_count": len(self.tracks),
            "tracks": [t.to_dict() for t in self.tracks],
            "mixer_channels": [m.to_dict() for m in self.mixer_channels],
        }


# MIDI note name helpers

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_note_name(midi_key: int) -> str:
    """Convert a MIDI key number (0-127) to a note name like 'C4', 'A#3'."""
    octave = (midi_key // 12) - 1
    note = NOTE_NAMES[midi_key % 12]
    return f"{note}{octave}"


def note_name_to_midi(name: str) -> int:
    """Convert a note name like 'C4', 'A#3', 'C-1' to a MIDI key number."""
    import re

    name = name.strip()
    m = re.match(r"^([A-G]#?)(-?\d+)$", name)
    if not m:
        raise ValueError(f"Invalid note name: {name}")

    note_part = m.group(1)
    octave = int(m.group(2))

    if note_part not in NOTE_NAMES:
        raise ValueError(f"Invalid note: {note_part}")

    note_index = NOTE_NAMES.index(note_part)
    return (octave + 1) * 12 + note_index


def bars_to_ticks(bars: int, ticks_per_bar: int = TICKS_PER_BAR) -> int:
    """Convert bars to ticks."""
    return bars * ticks_per_bar


def ticks_to_bars(ticks: int, ticks_per_bar: int = TICKS_PER_BAR) -> float:
    """Convert ticks to bars."""
    return ticks / ticks_per_bar
