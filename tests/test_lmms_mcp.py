"""Tests for LMMS MCP Server."""

import json
import tempfile
from pathlib import Path

import pytest

from lmms_mcp.models import Note, midi_to_note_name, note_name_to_midi, bars_to_ticks, ticks_to_bars
from lmms_mcp.xml_parser import create_empty_project, load_project, save_project, find_tracks, add_instrument_track, add_note_to_track
from lmms_mcp.project import LMMSProject


class TestModels:
    def test_midi_to_note_name(self):
        assert midi_to_note_name(60) == "C4"
        assert midi_to_note_name(69) == "A4"
        assert midi_to_note_name(0) == "C-1"
        assert midi_to_note_name(127) == "G9"

    def test_note_name_to_midi(self):
        assert note_name_to_midi("C4") == 60
        assert note_name_to_midi("A4") == 69
        assert note_name_to_midi("A#3") == 58

    def test_roundtrip_note_names(self):
        for key in [0, 24, 48, 60, 69, 72, 96, 127]:
            name = midi_to_note_name(key)
            assert note_name_to_midi(name) == key

    def test_bars_to_ticks(self):
        assert bars_to_ticks(1) == 192
        assert bars_to_ticks(4) == 768

    def test_ticks_to_bars(self):
        assert ticks_to_bars(192) == 1.0
        assert ticks_to_bars(768) == 4.0

    def test_note_to_dict(self):
        note = Note(key=60, pos=0, length=48, volume=100)
        d = note.to_dict()
        assert d["key"] == 60
        assert d["note_name"] == "C4"

    def test_note_from_dict(self):
        note = Note.from_dict({"key": 69, "pos": 48, "length": 96})
        assert note.key == 69
        assert note.pos == 48


class TestXMLParser:
    def test_create_empty_project(self):
        root = create_empty_project(bpm=120)
        head = root.find("head")
        assert head is not None
        assert head.get("bpm") == "120"

    def test_save_load_roundtrip(self):
        root = create_empty_project(bpm=150)
        with tempfile.NamedTemporaryFile(suffix=".mmpz", delete=False) as f:
            path = f.name

        save_project(path, root)
        loaded = load_project(path)
        head = loaded.find("head")
        assert head.get("bpm") == "150"

        Path(path).unlink()

    def test_save_load_uncompressed(self):
        root = create_empty_project(bpm=130)
        with tempfile.NamedTemporaryFile(suffix=".mmp", delete=False) as f:
            path = f.name

        save_project(path, root, compressed=False)
        loaded = load_project(path)
        head = loaded.find("head")
        assert head.get("bpm") == "130"

        Path(path).unlink()

    def test_add_instrument_track(self):
        root = create_empty_project()
        add_instrument_track(root, "My Synth", instrument="tripleoscillator")
        tracks = find_tracks(root)
        assert len(tracks) == 1
        assert tracks[0].get("name") == "My Synth"
        assert tracks[0].get("type") == "0"

    def test_add_note(self):
        root = create_empty_project()
        add_instrument_track(root, "Test Track")
        add_note_to_track(root, 0, key=60, pos=0, length=48)
        tracks = find_tracks(root)
        pattern = tracks[0].find("pattern")
        assert pattern is not None
        notes = pattern.findall("note")
        assert len(notes) == 1
        assert notes[0].get("key") == "60"


class TestProject:
    def test_new_project(self):
        proj = LMMSProject()
        proj.new(bpm=120)
        info = proj.get_info()
        assert info.bpm == 120
        assert info.time_sig_numerator == 4

    def test_set_tempo(self):
        proj = LMMSProject()
        proj.new()
        proj.set_tempo(180)
        info = proj.get_info()
        assert info.bpm == 180

    def test_add_track(self):
        proj = LMMSProject()
        proj.new()
        result = proj.add_track("instrument", "Bass", instrument="LB302")
        assert result["track_index"] == 0
        info = proj.get_info()
        assert len(info.tracks) == 1
        assert info.tracks[0].name == "Bass"

    def test_add_multiple_tracks(self):
        proj = LMMSProject()
        proj.new()
        proj.add_track("instrument", "Drums", instrument="kicker")
        proj.add_track("instrument", "Bass", instrument="tripleoscillator")
        proj.add_track("sample", "Samples")
        info = proj.get_info()
        assert len(info.tracks) == 3

    def test_add_note(self):
        proj = LMMSProject()
        proj.new()
        proj.add_track("instrument", "Melody")
        result = proj.add_note(0, key=60, pos=0, length=48)
        assert "Added note" in result["message"]

    def test_save_and_load(self):
        proj = LMMSProject()
        proj.new(bpm=160)
        proj.add_track("instrument", "Lead")

        with tempfile.NamedTemporaryFile(suffix=".mmpz", delete=False) as f:
            path = f.name

        proj.save(path)

        proj2 = LMMSProject()
        proj2.load(path)
        info = proj2.get_info()
        assert info.bpm == 160
        assert len(info.tracks) == 1

        Path(path).unlink()

    def test_to_dict(self):
        proj = LMMSProject()
        proj.new()
        proj.add_track("instrument", "Test")
        d = proj.to_dict()
        assert "bpm" in d
        assert "tracks" in d
        assert len(d["tracks"]) == 1


class TestEffects:
    """Tests for the effect chain (fxchain) module."""

    def _make_project(self):
        root = create_empty_project()
        add_instrument_track(root, "Lead")
        return root

    def test_known_effects_complete(self):
        from lmms_mcp.effects import KNOWN_EFFECTS
        expected = {"delay", "reverbsc", "eq", "compressor", "flanger",
                    "bassbooster", "waveshaper", "stereoenhancer"}
        assert expected.issubset(set(KNOWN_EFFECTS.keys()))

    def test_add_effect_to_track(self):
        from lmms_mcp.effects import add_effect
        root = self._make_project()
        track = find_tracks(root)[0]
        result = add_effect(track, "delay")
        assert result["effect"] == "delay"
        assert result["chain_size"] == 1

    def test_add_duplicate_effect_raises(self):
        from lmms_mcp.effects import add_effect
        root = self._make_project()
        track = find_tracks(root)[0]
        add_effect(track, "delay")
        with pytest.raises(ValueError, match="already exists"):
            add_effect(track, "delay")

    def test_add_unknown_effect_raises(self):
        from lmms_mcp.effects import add_effect
        root = self._make_project()
        track = find_tracks(root)[0]
        with pytest.raises(ValueError, match="Unknown effect"):
            add_effect(track, "greatest_reverb_9000")

    def test_external_effect_rejected(self):
        from lmms_mcp.effects import add_effect
        root = self._make_project()
        track = find_tracks(root)[0]
        with pytest.raises(ValueError, match="external"):
            add_effect(track, "vsteffect")

    def test_remove_effect_by_name(self):
        from lmms_mcp.effects import add_effect, remove_effect
        root = self._make_project()
        track = find_tracks(root)[0]
        add_effect(track, "delay")
        result = remove_effect(track, "delay")
        assert result["removed"] == "delay"
        assert result["chain_size"] == 0

    def test_remove_effect_by_position(self):
        from lmms_mcp.effects import add_effect, remove_effect
        root = self._make_project()
        track = find_tracks(root)[0]
        add_effect(track, "delay")
        add_effect(track, "eq")
        result = remove_effect(track, 0)
        assert result["removed"] == "delay"

    def test_list_effects(self):
        from lmms_mcp.effects import add_effect, list_effects
        root = self._make_project()
        track = find_tracks(root)[0]
        add_effect(track, "delay", wet=0.7)
        add_effect(track, "reverbsc", enabled=False)
        effects = list_effects(track)
        assert len(effects) == 2
        assert effects[0]["name"] == "delay"
        assert effects[0]["wet"] == 0.7
        assert effects[1]["enabled"] is False

    def test_toggle_effect(self):
        from lmms_mcp.effects import add_effect, set_effect_enabled
        root = self._make_project()
        track = find_tracks(root)[0]
        add_effect(track, "delay")
        result = set_effect_enabled(track, "delay", False)
        assert result["enabled"] is False

    def test_fxchain_survives_roundtrip(self):
        from lmms_mcp.effects import add_effect
        root = self._make_project()
        track = find_tracks(root)[0]
        add_effect(track, "reverbsc")

        with tempfile.NamedTemporaryFile(suffix=".mmpz", delete=False) as f:
            path = f.name
        save_project(path, root)
        root2 = load_project(path)
        fxchain = find_tracks(root2)[0].find("fxchain")
        eff = fxchain.find("effect")
        assert eff.get("name") == "reverbsc"
        Path(path).unlink()


class TestZynAddSubFX:
    """Tests for ZynAddSubFX preset and parameter support."""

    def _make_zyn_project(self):
        root = create_empty_project()
        add_instrument_track(root, "Zyn", instrument="zynaddsubfx")
        return root

    ZYN_PRESET_XML = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE ZynAddSubFX-data>\n'
        '<ZynAddSubFX-data version-major="1" version-minor="0">'
        '<INSTRUMENT><INFO>'
        "<string name=\"name\">TestPatch</string>"
        '</INFO></INSTRUMENT></ZynAddSubFX-data>'
    )

    def test_embed_preset(self):
        from lmms_mcp.xml_parser import embed_zyn_preset
        root = self._make_zyn_project()
        result = embed_zyn_preset(root, 0, self.ZYN_PRESET_XML)
        assert result["preset"] == "TestPatch"
        inst = find_tracks(root)[0].find("instrumenttrack/instrument")
        data = inst.find("ZynAddSubFX-data")
        assert data.tag == "ZynAddSubFX-data"

    def test_embed_preset_wrong_instrument(self):
        from lmms_mcp.xml_parser import embed_zyn_preset
        root = create_empty_project()
        add_instrument_track(root, "Not Zyn")  # tripleoscillator default
        with pytest.raises(ValueError, match="not 'zynaddsubfx'"):
            embed_zyn_preset(root, 0, self.ZYN_PRESET_XML)

    def test_embed_invalid_xml(self):
        from lmms_mcp.xml_parser import embed_zyn_preset
        root = self._make_zyn_project()
        with pytest.raises(ValueError, match="Invalid preset XML"):
            embed_zyn_preset(root, 0, "<not-valid-xml")

    def test_embed_wrong_root_element(self):
        from lmms_mcp.xml_parser import embed_zyn_preset
        root = self._make_zyn_project()
        with pytest.raises(ValueError, match="expected"):
            embed_zyn_preset(root, 0, "<something-else/>")

    def test_set_instrument_params(self):
        from lmms_mcp.xml_parser import set_instrument_params
        root = self._make_zyn_project()
        result = set_instrument_params(
            root, 0, {"filterfreq": 100, "portamento": 30}
        )
        assert result["applied"]["filterfreq"] == 100
        inst = find_tracks(root)[0].find("instrumenttrack/instrument")
        assert inst.get("filterfreq") == "100"

    def test_set_params_out_of_range_track(self):
        from lmms_mcp.xml_parser import set_instrument_params
        root = self._make_zyn_project()
        with pytest.raises(ValueError, match="out of range"):
            set_instrument_params(root, 99, {"portamento": 10})

    def test_find_track_element_range_check(self):
        from lmms_mcp.xml_parser import find_track_element
        root = self._make_zyn_project()
        with pytest.raises(ValueError, match="out of range"):
            find_track_element(root, 5)


if __name__ == "__main__":
    import sys
    print("Run with: pytest tests/")
    sys.exit(1)
