"""Opt-in real STDIO MCP -> LMMS smoke test, with no model calls.

Prepare an isolated environment and LMMS_TEST_EXECUTABLE separately. Set
LMMS_TEST_STDIO_RENDER=1 to enable. Nothing is downloaded, installed or extracted
by this test. Artifacts stay under pytest's temporary directory by default.
"""

import array
import json
import math
import os
import sys
import time
import wave
from importlib.metadata import version
from pathlib import Path
from xml.etree import ElementTree as ET

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class ToolClient:
    def __init__(self, session, transcript):
        self.session = session
        self.transcript = transcript

    async def call(self, name, arguments=None, *, expect_error=False, parse=True):
        started = time.monotonic()
        result = await self.session.call_tool(
            name, arguments or {}, read_timeout_seconds=45,
        )
        self.transcript.append({
            "name": name, "arguments": arguments or {},
            "elapsed_seconds": round(time.monotonic() - started, 6),
            "response": result.model_dump(mode="json", by_alias=True),
        })
        # None characterizes an application error under either envelope: it
        # must remain an error if the server later corrects its isError flag.
        if expect_error is not None:
            assert bool(result.is_error) is expect_error, result
        text = "\n".join(block.text for block in result.content if block.type == "text")
        if not parse:
            return text
        value = json.loads(text)
        if expect_error is False:
            assert "error" not in value, value
        return value


def fixture_tracks():
    melody = [60, 64, 67, 64, 69, 67, 64, 60]
    return [
        {
            "name": "Pulso MCP - melodia", "volume": 18, "panning": 10,
            "notes": [
                {"key": key, "pos": index * 48, "length": 40,
                 "volume": 70, "panning": 0}
                for index, key in enumerate(melody)
            ],
        },
        {
            "name": "Pulso MCP - bajo", "volume": 14, "panning": -10,
            "notes": [
                {"key": key, "pos": index * 96, "length": 96,
                 "volume": 65, "panning": 0}
                for index, key in enumerate((24, 31, 21, 28))
            ],
        },
    ]


def assert_restored_project(info, disk, expected):
    """Compare API and independently parsed XML against the input score."""
    assert info["bpm"] == 108 and info["master_volume"] == 50
    assert info["track_count"] == len(info["tracks"]) == len(expected)
    assert int(disk.find("head").get("bpm")) == 108
    assert int(disk.find("head").get("mastervol")) == 50
    disk_tracks = disk.findall("./song/trackcontainer/track")
    assert len(disk_tracks) == len(expected)
    fields = ("key", "pos", "length", "volume", "panning")
    xml_fields = ("key", "pos", "len", "vol", "pan")
    for track, xml_track, target in zip(info["tracks"], disk_tracks, expected):
        assert track["name"] == xml_track.get("name") == target["name"]
        instrument = xml_track.find("instrumenttrack")
        assert track["instrument"] == instrument.find("instrument").get("name") == "tripleoscillator"
        assert track["volume"] == int(instrument.get("vol")) == target["volume"]
        assert track["panning"] == int(instrument.get("pan")) == target["panning"]
        assert len(track["patterns"]) == len(xml_track.findall("pattern")) == 1
        assert int(xml_track.find("pattern").get("pos")) == 0
        wanted = sorted(tuple(note[field] for field in fields) for note in target["notes"])
        api_notes = sorted(
            tuple(note[field] for field in fields)
            for note in track["patterns"][0]["notes"]
        )
        xml_notes = sorted(
            tuple(int(note.get(field)) for field in xml_fields)
            for note in xml_track.findall("./pattern/note")
        )
        assert api_notes == wanted, "Reloaded note values differ from the input score"
        assert xml_notes == wanted, "Saved XML note values differ from the input score"


async def compose_and_reload(client, project):
    expected = fixture_tracks()
    for index, track in enumerate(expected):
        created = await client.call("add_instrument_track", {
            "name": track["name"], "instrument": "tripleoscillator",
            "volume": track["volume"], "panning": track["panning"],
        })
        assert created["track_index"] == index
        added = await client.call("add_notes_batch", {
            "track_index": index, "notes": track["notes"],
        })
        assert added["added"] == len(track["notes"])
        assert all("error" not in item for item in added["notes"])
    await client.call("save_project", {"path": str(project), "compressed": False})
    # Replace in-memory state: a no-op load cannot pass.
    await client.call("create_project", {"bpm": 120})
    empty = await client.call("get_project_info")
    assert empty["bpm"] == 120 and empty["track_count"] == 0
    await client.call("load_project", {"path": str(project)})
    restored = await client.call("get_project_info")
    assert_restored_project(restored, ET.parse(project).getroot(), expected)


async def check_session(session, output, report, transcript):
    client = ToolClient(session, transcript)
    initialized = await session.initialize()
    report["protocol_version"] = initialized.protocol_version
    report["server_info"] = initialized.server_info.model_dump(mode="json")
    listing = await session.list_tools()
    assert listing.next_cursor is None, "Review pagination before widening this smoke test"
    names = {tool.name for tool in listing.tools}
    required = {
        "create_project", "add_instrument_track", "add_notes_batch",
        "save_project", "load_project", "get_project_info",
        "get_lmms_info", "render_project", "set_tempo",
    }
    assert required <= names
    report.update(tool_count=len(names), tool_names=sorted(names))
    (output / "catalog.json").write_text(listing.model_dump_json(by_alias=True), encoding="utf-8")
    installation = await client.call("get_lmms_info")
    assert installation["found"] is True and installation["version"] is not None
    expected_version = os.environ.get("LMMS_TEST_EXPECTED_VERSION")
    if expected_version:
        assert installation["version"] == expected_version
    report["lmms_version"] = installation["version"]
    assert "tripleoscillator" in installation["instruments_verified_available"]
    await client.call("set_tempo", {"bpm": "not-an-integer"}, expect_error=True, parse=False)
    await client.call("create_project", {"bpm": 108, "master_volume": 50})
    # Characterize the inherited JSON error while also accepting isError=true.
    invalid = await client.call("add_instrument_track", {
        "name": "Invalid control", "instrument": "not_a_real_instrument_742",
    }, expect_error=None, parse=False)
    assert "unknown instrument" in invalid.lower(), invalid
    report["application_error_is_error"] = transcript[-1]["response"].get("isError", False)
    info = await client.call("get_project_info")
    assert info["track_count"] == 0
    await compose_and_reload(client, output / "Pulso-MCP.mmp")
    rendered = await client.call("render_project", {
        "output_path": str(output / "Pulso-MCP.wav"),
        "file_format": "wav", "samplerate": 44100,
    })
    assert rendered.get("success") is True and rendered["returncode"] == 0
    report["render"] = rendered


async def exercise(parameters, output, report, transcript):
    with anyio.fail_after(90), (output / "server-stderr.log").open("w", encoding="utf-8") as errors:
        async with stdio_client(parameters, errlog=errors) as streams:
            async with ClientSession(*streams, read_timeout_seconds=20) as session:
                await check_session(session, output, report, transcript)
    report["session_closed"] = True


def inspect_audio(path):
    with wave.open(str(path), "rb") as wav:
        assert wav.getsampwidth() == 2
        channels, rate, frames = wav.getnchannels(), wav.getframerate(), wav.getnframes()
        pcm = array.array("h", wav.readframes(frames))
    if sys.byteorder != "little":
        pcm.byteswap()
    assert channels == 2 and rate == 44100 and frames > 0
    peak = max(abs(value) for value in pcm)
    rms = math.sqrt(sum(value * value for value in pcm) / len(pcm))
    clipping = sum(abs(value) >= 32767 for value in pcm)
    assert 4 <= frames / rate <= 9 and rms > 10 and clipping == 0
    return {
        "channels": channels, "sample_rate_hz": rate, "sample_width_bytes": 2,
        "duration_seconds": round(frames / rate, 4),
        "peak_dbfs": round(20 * math.log10(peak / 32768), 3),
        "rms_dbfs": round(20 * math.log10(rms / 32768), 3),
        "full_scale_samples": clipping,
    }


@pytest.mark.skipif(
    os.environ.get("LMMS_TEST_STDIO_RENDER") != "1",
    reason="Set LMMS_TEST_STDIO_RENDER=1 in a prepared isolated environment",
)
def test_stdio_roundtrip_and_real_render(tmp_path):
    executable = os.environ.get("LMMS_TEST_EXECUTABLE")
    assert executable, "LMMS_TEST_EXECUTABLE must explicitly select the test application"
    assert Path(executable).is_file() and os.access(executable, os.X_OK)
    output = Path(os.environ.get("LMMS_TEST_ARTIFACT_DIR", tmp_path / "stdio-render"))
    output.mkdir(parents=True, exist_ok=False)
    transcript = []
    report = {"status": "FAIL", "transport": "stdio", "sdk_version": version("mcp")}
    env = {
        "PYTHONPATH": os.pathsep.join(filter(None, (
            str(Path(__file__).resolve().parents[1] / "src"), os.environ.get("PYTHONPATH"),
        ))),
        "PYTHONDONTWRITEBYTECODE": "1", "LMMS_EXECUTABLE": executable,
        "LMMS_PROJECTS_DIR": str(output), "QT_QPA_PLATFORM": "offscreen",
        "OMP_NUM_THREADS": "1",
    }
    for key in ("QT_QPA_PLATFORM_PLUGIN_PATH", "LMMS_PLUGIN_DIR"):
        if key in os.environ:
            env[key] = os.environ[key]
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "lmms_mcp"], env=env, cwd=str(output),
    )
    try:
        anyio.run(exercise, parameters, output, report, transcript)
        report["audio"] = inspect_audio(output / "Pulso-MCP.wav")
        report["tool_calls"] = len(transcript)
        report["controls"] = {
            "invalid_argument_is_error": True,
            "application_error_detected_with_either_envelope": True,
            "invalid_instrument_did_not_add_track": True,
            "reload_replaced_different_in_memory_project": True,
            "api_and_independent_xml_match_input_note_values": True,
        }
        report["listening_review"] = "NOT_PERFORMED"
        report["status"] = "PASS"
    finally:
        (output / "transcript.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
        (output / "smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
