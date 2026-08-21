"""Effect chain (fxchain) handling for LMMS projects.

Provides the list of built-in LMMS effect plugins and functions to
manipulate fxchain elements on tracks and mixer channels.
"""

import xml.etree.ElementTree as ET

# Built-in LMMS effects: plugin name -> (description, controls node name).
# Names verified against LMMS source (plugin descriptors + nodeName()).
KNOWN_EFFECTS = {
    "amplifier": ("Volume/gain control", "AmplifierControls"),
    "bassbooster": ("Low frequency booster", "bassboostercontrols"),
    "bitcrush": ("Bit crusher for lo-fi sound", "bitcrushcontrols"),
    "compressor": ("Dynamic range compressor", "CompressorControls"),
    "crossovereq": ("3-band crossover EQ", "crossoevereqcontrols"),
    "delay": ("Tempo-synced delay/echo", "Delay"),
    "dispersion": ("Dispersion/phaser effect", "DispersionControls"),
    "dualfilter": ("Dual filter (2 filters in parallel/serial)", "DualFilterControls"),
    "dynamicsprocessor": ("Dynamics processor (compressor/expander)", "dynamicsprocessor_controls"),
    "eq": ("Parametric equalizer", "Eq"),
    "flanger": ("Flanger modulation effect", "Flanger"),
    "frequencyshifter": ("Frequency shifter", "FrequencyShifterControls"),
    "multitapecho": ("Multi-tap echo", "multitapechocontrols"),
    "reverbsc": ("Studio-quality reverb (Schroeder)", "ReverbSCControls"),
    "slewdistortion": ("Slew-rate distortion", "SlewDistortionControls"),
    "stereoenhancer": ("Stereo width enhancer", "stereoenhancercontrols"),
    "stereomatrix": ("Stereo channel matrix", "stereomatrixcontrols"),
    "waveshaper": ("Waveshaping distortion", "waveshapercontrols"),
}

# Effects that require external hosts/libraries - listed separately so
# agents know they may not work on every system.
EXTERNAL_EFFECTS = {
    "ladspaeffect": "LADSPA plugin host (depends on installed LADSPA libs)",
    "lv2effect": "LV2 plugin host (depends on installed LV2 plugins)",
    "vsteffect": "VST plugin host (Windows/macOS, requires VST DLLs)",
}

# Recommended effects per use case
EFFECT_RECOMMENDATIONS = {
    "vocals": ["eq", "compressor", "reverbsc", "delay"],
    "drums": ["compressor", "eq", "waveshaper"],
    "bass": ["compressor", "eq", "bassbooster"],
    "synth": ["delay", "reverbsc", "flanger", "bitcrush"],
    "master": ["eq", "compressor", "stereoenhancer", "amplifier"],
}


def get_fxchain(parent: ET.Element, create: bool = True) -> ET.Element:
    """Get or create the fxchain element under a track or mixer channel."""
    fxchain = parent.find("fxchain")
    if fxchain is None and create:
        fxchain = ET.SubElement(parent, "fxchain", {
            "numofeffects": "0", "enabled": "0",
        })
    return fxchain


def add_effect(
    parent: ET.Element,
    effect_name: str,
    wet: float = 1.0,
    enabled: bool = True,
    position: int | None = None,
) -> dict:
    """Add an effect to a fxchain element.

    Args:
        parent: The track or mixer channel element containing fxchain.
        effect_name: Built-in LMMS effect plugin name.
        wet: Wet/dry mix (0.0-1.0, 1.0=full effect).
        enabled: Whether the effect is active.
        position: Insert position in chain (None=append at end).

    Returns:
        Dict with result info.

    Raises:
        ValueError: If effect name is unknown.
    """
    normalized = effect_name.strip().lower()
    if normalized not in KNOWN_EFFECTS:
        if normalized in EXTERNAL_EFFECTS:
            raise ValueError(
                f"Effect '{effect_name}' requires external plugins "
                f"({EXTERNAL_EFFECTS[normalized]}). Use a built-in effect instead."
            )
        valid = ", ".join(sorted(KNOWN_EFFECTS.keys()))
        raise ValueError(f"Unknown effect '{effect_name}'. Valid effects: {valid}")

    fxchain = get_fxchain(parent)
    existing = [
        e.get("name") for e in fxchain.findall("effect")
    ]
    if normalized in existing:
        raise ValueError(
            f"Effect '{normalized}' already exists on this chain "
            f"(position {existing.index(normalized)})."
        )

    # Build effect element with standard attributes; plugin-specific
    # controls use defaults when omitted (LMMS fills them in).
    effect = ET.Element("effect", {
        "on": "1" if enabled else "0",
        "wet": str(wet),
        "autoquit": "1",
        "autoquit_denominator": "4",
        "autoquit_numerator": "4",
        "syncmode": "0",
        "name": normalized,
    })
    # Controls element with default attribute so LMMS restores defaults
    controls_name = KNOWN_EFFECTS[normalized][1]
    ET.SubElement(effect, controls_name)

    if position is None or position >= len(fxchain):
        fxchain.append(effect)
        final_pos = len(fxchain) - 1
    else:
        fxchain.insert(position, effect)
        final_pos = max(0, position)

    num = len(fxchain.findall("effect"))
    fxchain.set("numofeffects", str(num))
    fxchain.set("enabled", "1")

    return {
        "effect": normalized,
        "position": final_pos,
        "wet": wet,
        "enabled": enabled,
        "chain_size": num,
        "message": f"Added {normalized} at position {final_pos} "
                   f"(chain now has {num} effects)",
    }


def remove_effect(parent: ET.Element, identifier: str | int) -> dict:
    """Remove an effect from a fxchain by name or position.

    Args:
        parent: Track or mixer channel element containing fxchain.
        identifier: Effect name (str) or chain position (int).

    Returns:
        Dict with result info.

    Raises:
        ValueError: If effect not found.
    """
    fxchain = parent.find("fxchain")
    if fxchain is None:
        raise ValueError("This target has no effect chain.")

    effects = fxchain.findall("effect")
    target = None
    if isinstance(identifier, int):
        if 0 <= identifier < len(effects):
            target = effects[identifier]
    else:
        for eff in effects:
            if eff.get("name", "").lower() == str(identifier).lower():
                target = eff
                break

    if target is None:
        names = [e.get("name", "?") for e in effects]
        raise ValueError(
            f"Effect '{identifier}' not found. Existing effects: {names}"
        )

    removed_name = target.get("name")
    fxchain.remove(target)
    remaining = fxchain.findall("effect")
    fxchain.set("numofeffects", str(len(remaining)))
    if len(remaining) == 0:
        fxchain.set("enabled", "0")

    return {
        "removed": removed_name,
        "chain_size": len(remaining),
        "message": f"Removed {removed_name} ({len(remaining)} effects remain)",
    }


def list_effects(parent: ET.Element) -> list[dict]:
    """List all effects in a fxchain element."""
    fxchain = parent.find("fxchain")
    if fxchain is None:
        return []
    result = []
    for pos, eff in enumerate(fxchain.findall("effect")):
        result.append({
            "position": pos,
            "name": eff.get("name", "unknown"),
            "enabled": eff.get("on", "1") == "1",
            "wet": float(eff.get("wet", "1")),
        })
    return result


def set_effect_enabled(parent: ET.Element, identifier: str | int, enabled: bool) -> dict:
    """Enable/disable an effect in a fxchain by name or position."""
    fxchain = parent.find("fxchain")
    if fxchain is None:
        raise ValueError("This target has no effect chain.")
    effects = fxchain.findall("effect")
    target = None
    if isinstance(identifier, int):
        if 0 <= identifier < len(effects):
            target = effects[identifier]
    else:
        for eff in effects:
            if eff.get("name", "").lower() == str(identifier).lower():
                target = eff
                break
    if target is None:
        raise ValueError(f"Effect '{identifier}' not found.")
    target.set("on", "1" if enabled else "0")
    return {
        "effect": target.get("name"),
        "enabled": enabled,
        "message": f"{target.get('name')} {'enabled' if enabled else 'disabled'}",
    }
