"""作品层：控制乐器、全局时间与输出。

规划中的类型：

- ``Track``：把片段绑定到乐器。
- ``Score``：由多条 ``Track`` 组成完整作品。
- ``TempoMap``：全局速度映射。
- ``MeterMap``：全局拍号映射。

时间位置以四分音符为单位。
"""

from dataclasses import dataclass, field

from fractions import Fraction
from muse.core.base import Music
from typing import TypeAlias

# 乐器类型
Instrument: TypeAlias = str  # TODO: 设计乐器类型
Tempo: TypeAlias = int | float | Fraction  # 每分钟四分音符数。

# General MIDI Level 1 instrument names, in zero-based program order.
_GM_INSTRUMENTS = (
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavinet",
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)", "Electric Guitar (clean)",
    "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
    "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass", "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    "Violin", "Viola", "Cello", "Contrabass", "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    "String Ensemble 1", "String Ensemble 2", "SynthStrings 1", "SynthStrings 2", "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet", "French Horn", "Brass Section", "SynthBrass 1", "SynthBrass 2",
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax", "Oboe", "English Horn", "Bassoon", "Clarinet",
    "Piccolo", "Flute", "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)", "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass + lead)",
    "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)", "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)", "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
    "Sitar", "Banjo", "Shamisen", "Koto", "Kalimba", "Bag Pipe", "Fiddle", "Shanai",
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock", "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
    "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet", "Telephone Ring", "Helicopter", "Applause", "Gunshot",
)
_GM_PROGRAMS = {name.casefold(): program for program, name in enumerate(_GM_INSTRUMENTS)}
_GM_PROGRAMS["piano"] = 0

def _validate_change_positions(
    positions: tuple[Fraction, ...],
) -> None:
    """校验速度表或拍号表中的变化位置。"""
    if not positions:
        raise ValueError("Change map must contain at least one entry")

    if positions[0] != 0:
        raise ValueError("The first change must start at position 0")

    for previous, current in zip(positions, positions[1:]):
        if current <= previous:
            raise ValueError(
                "Change positions must be strictly increasing"
            )

@dataclass(frozen=True)
class ControlChange:
    """指定位置的 MIDI 控制器变化；例如控制器 64 是延音踏板。
    
    Attributes:
        start: 变化的起始时间（以四分音符为单位）。
        control: MIDI 控制器编号（0-127）。
        value: MIDI 控制器值（0-127）。
    """
    start: Fraction
    control: int
    value: int

    def __post_init__(self) -> None:
        if self.start < 0 or not 0 <= self.control <= 127 or not 0 <= self.value <= 127:
            raise ValueError("Invalid MIDI control change")


@dataclass(frozen=True)
class PitchBend:
    """指定位置的 MIDI 弯音，范围为 -8192 到 8191。
    

    Attributes:
        start: 变化的起始时间（以四分音符为单位）。
        pitch: MIDI 弯音值（-8192 到 8191）。
    """
    start: Fraction
    pitch: int

    def __post_init__(self) -> None:
        if self.start < 0 or not -8192 <= self.pitch <= 8191:
            raise ValueError("Invalid MIDI pitch bend")


@dataclass(frozen=True)
class Track:
    """轨道：将片段绑定到乐器。

    Attributes:
        music: 轨道的片段。
        instrument: 轨道的乐器。
        name: 轨道的名称。
        is_percussion: 是否为打击乐轨道。
        controls: 轨道的控制器变化列表。
    """

    music: Music
    instrument: Instrument
    name: str
    is_percussion: bool = False
    controls: tuple[ControlChange | PitchBend, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Track name must not be empty")
        if not self.instrument:
            raise ValueError("Track instrument must not be empty")

    def instrument_to_midi_program(self) -> int:
        """将乐器名称映射为 MIDI 程序号。

        Returns:
            MIDI 程序号（0-127）。

        Raises:
            ValueError: 乐器名称不在 General MIDI 乐器表中。
        """
        try:
            return _GM_PROGRAMS[self.instrument.strip().casefold()]
        except KeyError as exc:
            raise ValueError(f"Unknown MIDI instrument: {self.instrument!r}") from exc

@dataclass(frozen=True)
class TempoMap:
    """速度映射：全局速度变化。

    Attributes:
        tempo: 速度变化列表，每个元素为 (start, Tempo)。
            start 为速度变化的起始时间（以四分音符为单位），Tempo 为每分钟节拍数。
    """

    tempo: tuple[tuple[Fraction, Tempo], ...]  # (start, Tempo)

    def __post_init__(self) -> None:
        _validate_change_positions(
            tuple(start for start, _ in self.tempo)
        )

        for _, bpm in self.tempo:
            if bpm <= 0:
                raise ValueError("Tempo must be positive")

@dataclass(frozen=True)
class TimeSignature:
    """拍号：表示每小节的拍数和每拍的音符时值。

    Attributes:
        numerator: 分子，表示每小节的拍数。
        denominator: 分母，表示每拍的音符时值（1/denominator）。
    """
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if self.numerator <= 0:
            raise ValueError("Time signature numerator must be positive")

        if self.denominator <= 0:
            raise ValueError("Time signature denominator must be positive")

        # 正的 2 的幂：1、2、4、8、16……
        if self.denominator & (self.denominator - 1) != 0:
            raise ValueError(
                "Time signature denominator must be a power of 2"
            )

@dataclass(frozen=True)
class MeterMap:
    """拍号映射：全局拍号变化。

    Attributes:
        meter: 拍号变化列表，每个元素为 (start, TimeSignature)。
            start 为拍号变化的起始时间（以四分音符为单位），TimeSignature中，numerator 为分子，denominator 为分母。
    """

    meter: tuple[tuple[Fraction, TimeSignature], ...]  # (start, numerator, denominator)

    def __post_init__(self) -> None:
        _validate_change_positions(
            tuple(start for start, _ in self.meter)
        )

@dataclass(frozen=True)
class Score:
    """乐谱：由多条轨道组成的完整作品。

    Attributes:
        tracks: 乐谱的轨道列表。
        title: 乐谱的标题。
        tempo_map: 乐谱的速度映射。
        meter_map: 乐谱的拍号映射。
    """

    tracks: tuple[Track, ...]
    title: str
    
    tempo_map: TempoMap = field(
        default_factory=lambda: TempoMap(
            tempo=((Fraction(0), 120),)
        )
    )

    meter_map: MeterMap = field(
        default_factory=lambda: MeterMap(
            meter=((Fraction(0), TimeSignature(4, 4)),)
        )
    )

    def __post_init__(self) -> None:
        if not self.tracks:
            raise ValueError("Score must have at least one track")
