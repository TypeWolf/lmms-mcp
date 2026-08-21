# LMMS MCP Server

An MCP (Model Context Protocol) server for [LMMS](https://lmms.io/) - the free, open-source digital audio workstation. Lets AI agents create, modify, and save LMMS music projects programmatically.

## Features

- **Create & save** LMMS projects (`.mmpz` compressed, `.mmp` XML)
- **Add tracks**: Instrument, Sample, Pattern (Beat/Bassline), Automation
- **Add notes** with MIDI key, position, velocity, and panning
- **Mixer control**: Create channels, set volume, name channels
- **Song settings**: Tempo (BPM), time signature, master volume/pitch
- **Musical utilities**: Note name conversion, scale generation, tick/bar conversion
- **Full project inspection**: Read tracks, patterns, notes, mixer channels

## Installation

```bash
pip install lmms-mcp
```

Or from source:

```bash
git clone https://github.com/TypeWolf/lmms-mcp.git
cd lmms-mcp
pip install -e .
```

### Requirements

- Python 3.10+
- An MCP host (opencode, Claude Desktop, Cursor, etc.)

## Quick Start

### With opencode

Add to your `opencode.json`:

```json
{
  "mcp": {
    "lmms": {
      "type": "local",
      "command": ["python", "-m", "lmms_mcp"],
      "environment": {
        "LMMS_PROJECTS_DIR": "/path/to/your/lmms/projects"
      }
    }
  }
}
```

### With Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lmms": {
      "command": "python",
      "args": ["-m", "lmms_mcp"],
      "env": {
        "LMMS_PROJECTS_DIR": "/path/to/your/lmms/projects"
      }
    }
  }
}
```

### Run directly

```bash
python -m lmms_mcp
```

## Tools

### Project Management

| Tool | Description |
|------|-------------|
| `create_project` | Create a new empty LMMS project |
| `load_project` | Load an existing `.mmpz` or `.mmp` file |
| `save_project` | Save the current project |
| `get_project_info` | Get project overview (tempo, tracks, mixer) |
| `get_project_xml` | Get raw XML of the project |

### Track Operations

| Tool | Description |
|------|-------------|
| `add_instrument_track` | Add a synthesizer/sampler track |
| `add_sample_track` | Add an audio sample track |
| `add_automation_track` | Add a parameter automation track |
| `add_pattern_track` | Add a beat/bassline pattern track |
| `remove_track` | Remove a track by index |
| `get_track` | Get detailed track information |
| `list_tracks` | List all tracks with summary |
| `set_track_volume` | Set track volume (0-200) |
| `set_track_panning` | Set track panning (-100 to +100) |
| `mute_track` | Mute/unmute a track |
| `solo_track` | Solo/unsolo a track |

### Notes & Patterns

| Tool | Description |
|------|-------------|
| `add_note` | Add a note by MIDI key number |
| `add_note_by_name` | Add a note by name (e.g. "C4", "A#3") |
| `add_notes_batch` | Add multiple notes at once |

### Mixer

| Tool | Description |
|------|-------------|
| `add_mixer_channel` | Create a new mixer channel |
| `get_mixer_channels` | List all mixer channels |
| `set_mixer_channel_volume` | Set channel volume |
| `set_mixer_channel_name` | Rename a channel |

### Song Settings

| Tool | Description |
|------|-------------|
| `set_tempo` | Set BPM (10-999) |
| `set_time_signature` | Set time signature (e.g. 4/4, 3/4) |
| `set_master_volume` | Set master volume (0-200) |
| `set_master_pitch` | Set master pitch (-12 to +12 semitones) |

### Effects (FX Chain)

| Tool | Description |
|------|-------------|
| `add_effect` | Add a built-in effect to a track or mixer channel |
| `remove_effect` | Remove an effect by name or chain position |
| `toggle_effect` | Enable/bypass an effect without removing it |
| `get_effect_chain` | List all effects on a track or mixer channel |

### ZynAddSubFX Presets & Parameters

| Tool | Description |
|------|-------------|
| `list_zyn_presets` | Browse ~950 factory presets (.xiz) by category |
| `load_zyn_preset` | Load a preset into a zynaddsubfx track |
| `set_zyn_params` | Set portamento, filter, FM gain, resonance etc. |

### Utilities

| Tool | Description |
|------|-------------|
| `note_name_to_key` | Convert note name to MIDI number |
| `key_to_note_name` | Convert MIDI number to note name |
| `bars_to_ticks_converter` | Convert bars to ticks |
| `ticks_to_bars_converter` | Convert ticks to bars |
| `generate_scale` | Generate a musical scale |

## Resources

| URI | Description |
|-----|-------------|
| `lmms://project/info` | Current project information |
| `lmms://project/tracks` | All tracks in the project |
| `lmms://project/mixer` | All mixer channels |
| `lmms://project/xml` | Raw project XML |
| `lmms://reference/instruments` | Available LMMS instruments |
| `lmms://reference/effects` | Available LMMS effects |
| `lmms://reference/note_names` | MIDI note name mapping |
| `lmms://reference/scales` | Available musical scales |

## Prompts

| Name | Description |
|------|-------------|
| `create_basic_song` | Create a song structure with drums, bass, melody |
| `add_drum_pattern` | Generate a drum pattern (four-on-the-floor, breakbeat, etc.) |
| `create_melody` | Generate a melody in a given scale |
| `mix_and_arrange` | Mix and arrange the current project |
| `export_project` | Export/save the project |

## LMMS Concepts

| Concept | Value |
|---------|-------|
| Ticks per bar | 192 (in 4/4 time) |
| Default tempo | 140 BPM |
| Note 60 | C4 (middle C) |
| Note 69 | A4 (440 Hz) |
| Volume range | 0-200 (100 = normal) |
| Panning range | -100 (left) to +100 (right) |
| Track type 0 | Instrument |
| Track type 1 | Pattern (Beat/Bassline) |
| Track type 2 | Sample |
| Track type 5 | Automation |

## Available Instruments

All built-in LMMS instruments (verified against LMMS source). LMMS has no
plugin download mechanism - only these can be used:

| Plugin ID | Name |
|-----------|------|
| `tripleoscillator` | Three-oscillator subtractive synth (default) |
| `kicker` | Kick drum synth |
| `audiofileprocessor` | Audio file player/sampler |
| `organic` | Additive organ synth |
| `malletsstk` | Physical modeling mallets (STK) |
| `lb302` | TB-303 style acid bass |
| `monstro` | Powerful 3-oscillator polyphonic synth |
| `freeboy` | Game Boy sound chip emulator |
| `nes` | NES 8-bit sound chip emulator |
| `sid` | Commodore 64 SID chip emulator |
| `sfxr` | Retro sound effect generator |
| `opulenz` | OPL3 FM synthesizer |
| `watsyn` | 4-oscillator wavetable-style synth |
| `xpressive` | Expressive mono lead synth |
| `zynaddsubfx` | ZynAddSubFX powerful feature-rich synth |
| `sf2player` | SoundFont (.sf2) sample player |
| `vibedstrings` | Vibrating string physical model |
| `bitinvader` | Bit-crushed wavetable synth |
| `patman` | GUS patch sampler |
| `gigplayer` | GIG sample library player |
| `slicert` | Beat slicer for audio loops |
| `vestige` | VST plugin host (Windows only) |

## Available Effects

Built-in LMMS effects for `add_effect`: `amplifier`, `bassbooster`,
`bitcrush`, `compressor`, `crossovereq`, `delay`, `dispersion`,
`dualfilter`, `dynamicsprocessor`, `eq`, `flanger`, `frequencyshifter`,
`multitapecho`, `reverbsc`, `slewdistortion`, `stereoenhancer`,
`stereomatrix`, `waveshaper`.

Typical chains:
- Lead synth: `delay` -> `reverbsc`
- Vocals: `eq` -> `compressor` -> `reverbsc`
- Master bus: `eq` -> `compressor` -> `stereoenhancer`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LMMS_PROJECTS_DIR` | `~/Desktop/Media/lmms/AI-Projects` | Default directory for saving projects |
| `LMMS_PRESETS_DIR` | auto-detected | Path to ZynAddSubFX presets folder (`data/presets/ZynAddSubFX`) |

## Configuration

### opencode.json

```json
{
  "mcp": {
    "lmms": {
      "type": "local",
      "command": ["python", "-m", "lmms_mcp"],
      "cwd": ".",
      "enabled": true,
      "environment": {
        "LMMS_PROJECTS_DIR": "C:\\Users\\you\\Music\\LMMS\\Projects"
      }
    }
  }
}
```

### claude_desktop_config.json

```json
{
  "mcpServers": {
    "lmms": {
      "command": "python",
      "args": ["-m", "lmms_mcp"],
      "env": {
        "LMMS_PROJECTS_DIR": "/home/you/music/lmms/projects"
      }
    }
  }
}
```

## Development

```bash
# Clone and install
git clone https://github.com/TypeWolf/lmms-mcp.git
cd lmms-mcp
pip install -e ".[dev]"

# Run tests
pytest

# Run in development mode
mcp dev src/lmms_mcp/server.py
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Links

- [LMMS](https://lmms.io/) - The DAW this server controls
- [MCP Protocol](https://modelcontextprotocol.io/) - Model Context Protocol specification
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) - Official Python SDK
- [opencode](https://opencode.ai/) - AI coding assistant with MCP support
