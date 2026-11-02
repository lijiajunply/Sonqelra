"""作品层：控制乐器、全局时间与输出。

规划中的类型：

- ``Track``：把片段绑定到乐器。
- ``Score``：由多条 ``Track`` 组成完整作品。
- ``TempoMap``：全局速度映射。
- ``MeterMap``：全局拍号映射。

目前尚未实现，待作品层设计确定后补充。
"""

from dataclasses import dataclass, field

from fractions import Fraction
from muse.core.base import Music
from typing import TypeAlias

# 乐器类型
Instrument: TypeAlias = str  # TODO: 设计乐器类型
Tempo: TypeAlias = int  # 每分钟节拍数，Tempo = 120 表示每分钟 120 个四分音符。

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
class Track:
    """轨道：将片段绑定到乐器。

    Attributes:
        music: 轨道的片段。
        instrument: 轨道的乐器。
    """

    music: Music
    instrument: Instrument
    name: str

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