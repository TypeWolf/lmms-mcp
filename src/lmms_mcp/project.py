"""High-level LMMS project manipulation."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from .models import (
    TrackType,
    Note,
    Pattern,
    Track,
    MixerChannel,
    SongInfo,
)
from .xml_parser import (
    create_empty_project,
    element_to_dict,
    find_mixer_channels,
    find_tracks,
    get_track_name,
    get_track_type,
    load_project,
    save_project,
    set_head_attribute,
    add_instrument_track,
    add_sample_track,
    add_automation_track,
    add_pattern_track,
    add_note_to_track,
    add_bb_clip,
    add_mixer_channel,
    TRACK_TYPE_NAMES,
)


class LMMSProject:
    """High-level interface for manipulating an LMMS project."""

    def __init__(self) -> None:
        self._root: ET.Element | None = None
        self._path: str = ""
        self._modified: bool = False

    @property
    def root(self) -> ET.Element:
        if self._root is None:
            raise ValueError("No project loaded. Call new() or load() first.")
        return self._root

    @property
    def path(self) -> str:
        return self._path

    @property
    def modified(self) -> bool:
        return self._modified

    def new(
        self,
        bpm: int = 140,
        time_sig_numerator: int = 4,
        time_sig_denominator: int = 4,
        master_volume: int = 100,
        master_pitch: int = 0,
    ) -> None:
        """Create a new empty project."""
        self._root = create_empty_project(
            bpm=bpm,
            time_sig_numerator=time_sig_numerator,
            time_sig_denominator=time_sig_denominator,
            master_volume=master_volume,
            master_pitch=master_pitch,
        )
        self._path = ""
        self._modified = True

    def load(self, path: str | Path) -> None:
        """Load a project from a .mmpz or .mmp file."""
        self._root = load_project(path)
        self._path = str(path)
        self._modified = False

    def save(self, path: str | Path | None = None, compressed: bool | None = None) -> str:
        """Save the project. Returns the path it was saved to.

        If compressed is None, the format follows the file extension:
        ".mmp" is plain XML, anything else compressed (.mmpz).
        """
        save_path = path or self._path
        if not save_path:
            raise ValueError("No path specified and no previous path to save to.")

        if compressed is None:
            compressed = not str(save_path).lower().endswith(".mmp")

        save_project(save_path, self._root, compressed=compressed)
        self._path = str(save_path)
        self._modified = False
        return self._path

    def get_info(self) -> SongInfo:
        """Extract song information from the project."""
        root = self.root
        head = root.find("head")
        if head is None:
            head = root.find("song/head")

        info = SongInfo(
            bpm=int(head.get("bpm", "140")) if head is not None else 140,
            time_sig_numerator=int(head.get("timesig_numerator", "4")) if head is not None else 4,
            time_sig_denominator=int(head.get("timesig_denominator", "4")) if head is not None else 4,
            master_volume=int(head.get("mastervol", "100")) if head is not None else 100,
            master_pitch=int(head.get("masterpitch", "0")) if head is not None else 0,
            file_path=self._path,
            modified=self._modified,
        )

        info.tracks = self._parse_tracks()
        info.mixer_channels = self._parse_mixer_channels()

        return info

    def _parse_tracks(self) -> list[Track]:
        """Parse all tracks from the XML."""
        tracks_xml = find_tracks(self.root)
        result = []

        for idx, track_elem in enumerate(tracks_xml):
            track = Track(
                track_type=TrackType(get_track_type(track_elem)),
                name=get_track_name(track_elem),
                muted=track_elem.get("muted", "0") == "1",
                solo=track_elem.get("solo", "0") == "1",
                index=idx,
            )

            if track.track_type == TrackType.INSTRUMENT:
                self._parse_instrument_track(track_elem, track)
            elif track.track_type == TrackType.PATTERN:
                self._parse_pattern_track(track_elem, track)
            elif track.track_type in (TrackType.SAMPLE, TrackType.AUTOMATION):
                self._parse_simple_track(track_elem, track)

            result.append(track)

        return result

    def _parse_instrument_track(self, elem: ET.Element, track: Track) -> None:
        """Parse instrument track details."""
        inst_elem = elem.find("instrumenttrack")
        if inst_elem is None:
            return

        track.volume = int(inst_elem.get("vol", "100"))
        track.panning = int(inst_elem.get("pan", "0"))
        track.mixer_channel = int(inst_elem.get("mixch", "0"))

        instrument = inst_elem.find("instrument")
        if instrument is not None:
            track.instrument = instrument.get("name", "")

        for pattern_elem in elem.findall("pattern"):
            pattern = Pattern(
                name=pattern_elem.get("name", "Pattern"),
                pattern_type=int(pattern_elem.get("type", "1")),
                steps=int(pattern_elem.get("steps", "16")),
                length=int(pattern_elem.get("len", "192")),
                muted=pattern_elem.get("muted", "0") == "1",
            )
            for note_elem in pattern_elem.findall("note"):
                pattern.notes.append(Note(
                    key=int(note_elem.get("key", "60")),
                    pos=int(note_elem.get("pos", "0")),
                    length=int(note_elem.get("len", "48")),
                    volume=int(note_elem.get("vol", "100")),
                    panning=int(note_elem.get("pan", "0")),
                ))
            track.patterns.append(pattern)

    def _parse_pattern_track(self, elem: ET.Element, track: Track) -> None:
        """Parse beat/bassline pattern track."""
        bbtrack = elem.find("bbtrack")
        if bbtrack is None:
            return

        container = bbtrack.find("trackcontainer")
        if container is None:
            return

        inner_tracks = container.findall("track")
        for inner in inner_tracks:
            for pattern_elem in inner.findall("pattern"):
                pattern = Pattern(
                    name=pattern_elem.get("name", "Pattern"),
                    pattern_type=int(pattern_elem.get("type", "1")),
                    steps=int(pattern_elem.get("steps", "16")),
                    length=int(pattern_elem.get("len", "192")),
                    muted=pattern_elem.get("muted", "0") == "1",
                )
                for note_elem in pattern_elem.findall("note"):
                    pattern.notes.append(Note(
                        key=int(note_elem.get("key", "60")),
                        pos=int(note_elem.get("pos", "0")),
                        length=int(note_elem.get("len", "48")),
                        volume=int(note_elem.get("vol", "100")),
                        panning=int(note_elem.get("pan", "0")),
                    ))
                track.patterns.append(pattern)

    def _parse_simple_track(self, elem: ET.Element, track: Track) -> None:
        """Parse sample or automation track."""
        sample_elem = elem.find("sampletrack")
        if sample_elem is not None:
            track.volume = int(sample_elem.get("vol", "100"))
            track.panning = int(sample_elem.get("pan", "0"))

    def _parse_mixer_channels(self) -> list[MixerChannel]:
        """Parse all mixer channels."""
        channels_xml = find_mixer_channels(self.root)
        result = []

        for ch_elem in channels_xml:
            fxchain = ch_elem.find("fxchain")
            effects = []
            if fxchain is not None:
                for eff in fxchain.findall("effect"):
                    effects.append(eff.get("name", "unknown"))

            sends = []
            for send in ch_elem.findall("send"):
                sends.append({
                    "channel": int(send.get("channel", "0")),
                    "amount": float(send.get("amount", "1")),
                })

            channel = MixerChannel(
                num=int(ch_elem.get("num", "0")),
                name=ch_elem.get("name", ""),
                volume=float(ch_elem.get("volume", "1")),
                muted=ch_elem.get("muted", "0") == "1",
                soloed=ch_elem.get("soloed", "0") == "1",
                effects=effects,
                sends=sends,
            )
            result.append(channel)

        return result

    def add_track(self, track_type: str, name: str, **kwargs) -> dict:
        """Add a track to the project. Returns info about the new track."""
        type_map = {
            "instrument": (TrackType.INSTRUMENT, add_instrument_track),
            "sample": (TrackType.SAMPLE, add_sample_track),
            "automation": (TrackType.AUTOMATION, add_automation_track),
            "pattern": (TrackType.PATTERN, add_pattern_track),
        }

        if track_type not in type_map:
            raise ValueError(f"Unknown track type: {track_type}. Use: {list(type_map.keys())}")

        enum_val, add_func = type_map[track_type]

        if track_type == "instrument":
            elem = add_func(
                self.root,
                name=name,
                instrument=kwargs.get("instrument", "tripleoscillator"),
                mixer_channel=kwargs.get("mixer_channel", 0),
                volume=kwargs.get("volume", 100),
                panning=kwargs.get("panning", 0),
            )
        elif track_type == "sample":
            elem = add_func(
                self.root,
                name=name,
                mixer_channel=kwargs.get("mixer_channel", 0),
                volume=kwargs.get("volume", 100),
                panning=kwargs.get("panning", 0),
            )
        elif track_type == "automation":
            elem = add_func(self.root, name=name)
        elif track_type == "pattern":
            elem = add_func(self.root, name=name)

        self._modified = True
        tracks = find_tracks(self.root)
        idx = len(tracks) - 1

        return {
            "track_index": idx,
            "track_type": track_type,
            "name": name,
            "message": f"Added {track_type} track '{name}' at index {idx}",
        }

    def remove_track(self, index: int) -> dict:
        """Remove a track by index."""
        tracks = find_tracks(self.root)
        if index >= len(tracks):
            raise IndexError(f"Track index {index} out of range (have {len(tracks)} tracks)")

        track = tracks[index]
        name = get_track_name(track)

        song = self.root.find("song")
        container = song.find("trackcontainer[@type='song']")
        container.remove(track)

        self._modified = True
        return {
            "message": f"Removed track '{name}' (index {index})",
            "remaining_tracks": len(find_tracks(self.root)),
        }

    def set_tempo(self, bpm: int) -> None:
        """Set the song tempo."""
        if not 10 <= bpm <= 999:
            raise ValueError("BPM must be between 10 and 999")
        set_head_attribute(self.root, "bpm", str(bpm))
        self._modified = True

    def set_time_signature(self, numerator: int, denominator: int) -> None:
        """Set the time signature."""
        set_head_attribute(self.root, "timesig_numerator", str(numerator))
        set_head_attribute(self.root, "timesig_denominator", str(denominator))
        self._modified = True

    def set_master_volume(self, volume: int) -> None:
        """Set master volume (0-200)."""
        if not 0 <= volume <= 200:
            raise ValueError("Master volume must be between 0 and 200")
        set_head_attribute(self.root, "mastervol", str(volume))
        self._modified = True

    def set_master_pitch(self, pitch: int) -> None:
        """Set master pitch (-12 to +12)."""
        if not -12 <= pitch <= 12:
            raise ValueError("Master pitch must be between -12 and +12")
        set_head_attribute(self.root, "masterpitch", str(pitch))
        self._modified = True

    def add_note(
        self,
        track_index: int,
        key: int = 60,
        pos: int = 0,
        length: int = 48,
        volume: int = 100,
        panning: int = 0,
        pattern_index: int | None = None,
    ) -> dict:
        """Add a note to a track's pattern.

        pos is relative to the pattern start. If the note ends beyond
        the pattern clip length, the clip is extended automatically
        (LMMS does not play notes outside the clip window).
        """
        res = add_note_to_track(
            self.root,
            track_index=track_index,
            key=key,
            pos=pos,
            length=length,
            volume=volume,
            panning=panning,
            pattern_index=pattern_index,
        )
        self._modified = True
        message = (
            f"Added note at track {track_index}: key={key} pos={pos} len={length}"
        )
        if res["extended_len"]:
            message += (
                f" [pattern '{res['pattern_name']}' len extended "
                f"{res['old_len']} -> {res['new_len']}: notes beyond a "
                f"pattern clip's end are silent in LMMS]"
            )
        return {"message": message}

    def add_mixer_channel(self, name: str, volume: float = 1.0) -> dict:
        """Add a mixer channel."""
        elem = add_mixer_channel(self.root, name=name, volume=volume)
        self._modified = True
        return {
            "channel_num": int(elem.get("num", "0")),
            "name": name,
            "message": f"Added mixer channel '{name}' at position {elem.get('num')}",
        }

    def to_dict(self) -> dict:
        """Convert the entire project to a dictionary."""
        return self.get_info().to_dict()

    def get_xml_string(self) -> str:
        """Get the XML representation of the project."""
        ET.indent(self.root, space="  ")
        return ET.tostring(self.root, encoding="unicode", xml_declaration=False)


# Module-level singleton
_current_project: LMMSProject | None = None


def get_project() -> LMMSProject:
    """Get the current project singleton."""
    global _current_project
    if _current_project is None:
        _current_project = LMMSProject()
        _current_project.new()
    return _current_project


def set_project(project: LMMSProject) -> None:
    """Set the current project singleton."""
    global _current_project
    _current_project = project
