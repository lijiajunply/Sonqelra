"""原子层：不可再拆分的基本音乐数据。

本模块提供：

- :class:`Pitch`：用音名、变音记号与八度描述的音高。
- :class:`Event`：展开到时间轴上的最小音符事件。
- :class:`Note`：单个音符片段。
- :class:`Rest`：休止片段。

所有时长均以四分音符为单位，使用 :class:`fractions.Fraction`
精确表示，避免浮点误差。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction
from typing import Final, Literal, TypeAlias

from .base import Music

# 时长以四分音符为单位；Fraction 保证时值相加、相乘时不产生浮点误差。
Duration: TypeAlias = Fraction

# 自然音级（C D E F G A B）相对 C 的半音偏移。
STEPS: Final[dict[str, int]] = {
    "C": 0, "D": 2, "E": 4, "F": 5,
    "G": 7, "A": 9, "B": 11,
}

# 等音拼写偏好：优先使用升号还是降号。
Spelling: TypeAlias = Literal["sharp", "flat"]

# 十二平均律中每种拼写偏好下，MIDI 音高对 12 取模后的 (音名, 变音记号)。
# 例如 MIDI 61 在 "sharp" 下为 C#4，在 "flat" 下为 Db4。
SPELLINGS: Final[dict[Spelling, tuple[tuple[str, int], ...]]] = {
    "sharp": (
        ("C", 0), ("C", 1),
        ("D", 0), ("D", 1),
        ("E", 0), ("F", 0),
        ("F", 1), ("G", 0),
        ("G", 1), ("A", 0),
        ("A", 1), ("B", 0),
    ),
    "flat": (
        ("C", 0), ("D", -1),
        ("D", 0), ("E", -1),
        ("E", 0), ("F", 0),
        ("G", -1), ("G", 0),
        ("A", -1), ("A", 0),
        ("B", -1), ("B", 0),
    ),
}


@dataclass(frozen=True)
class Pitch:
    """一个音高。

    Attributes:
        step: 音名，必须是 ``C``、``D``、``E``、``F``、``G``、``A``、``B``
            之一。
        accidental: 变音记号，以半音数表示：``0`` 为还原，``1`` 为升号，
            ``-1`` 为降号，``±2`` 为重升/重降。
        octave: 八度编号，采用科学音高记号（中央 C 为 ``C4``）。

    Raises:
        ValueError: 构造时音名不合法。
    """

    step: str
    accidental: int
    octave: int

    def __post_init__(self) -> None:
        """校验音名是否合法。

        Raises:
            ValueError: 音名不在自然音级 ``C``–``B`` 之中。
        """
        if self.step not in STEPS:
            raise ValueError("Invalid pitch step")

    @property
    def midi(self) -> int:
        """当前音高对应的 MIDI 音高编号。

        Returns:
            取值范围为 ``0`` 到 ``127`` 的 MIDI 编号。

        Raises:
            ValueError: 换算结果超出 MIDI 范围。
        """
        value = (
            12 * (self.octave + 1)
            + STEPS[self.step]
            + self.accidental
        )
        if not 0 <= value <= 127:
            raise ValueError("Pitch outside MIDI range")
        return value

    @property
    def name(self) -> str:
        """规范音高记号，例如 ``C#4``、``Bb3``、``C##4``。

        Returns:
            由音名、变音记号（升号重复 ``#``，降号重复 ``b``）和八度
            编号拼接而成的字符串，可直接传给 :meth:`parse`。
        """
        if self.accidental > 0:
            marks = "#" * self.accidental
        else:
            marks = "b" * -self.accidental
        return f"{self.step}{marks}{self.octave}"

    def __str__(self) -> str:
        """返回与 :attr:`name` 相同的音高记号。

        Returns:
            规范音高记号。
        """
        return self.name

    @classmethod
    def parse(cls, name: str) -> Pitch:
        """从科学音高记号解析出音高。

        示例：``C4``、``F#3``、``Bb5``、``A-1``、``C##4``。

        Args:
            name: 科学音高记号字符串，由音名、可选的变音记号（若干个
                同向的 ``#`` 或 ``b``，``##``/``bb`` 表示重升/重降），
                以及八度编号组成。

        Returns:
            解析得到的 :class:`Pitch` 实例。

        Raises:
            ValueError: 字符串不符合音高记号格式。
        """
        match = re.fullmatch(
            r"([A-G])(#*|b*)(-?\d+)", name
        )
        if not match:
            raise ValueError(f"Invalid pitch: {name}")

        step, marks, octave = match.groups()
        accidental = sum(1 if mark == "#" else -1 for mark in marks)
        return cls(step, accidental, int(octave))

    @classmethod
    def from_midi(cls, midi: int, *, spelling: Spelling = "sharp") -> Pitch:
        """将 MIDI 音高编号转换为音高。

        Args:
            midi: MIDI 音高编号，必须在 ``0`` 到 ``127`` 之间。
            spelling: 等音拼写偏好：``"sharp"`` 使用升号，``"flat"``
                使用降号。

        Returns:
            对应音高。

        Raises:
            ValueError: MIDI 编号超出范围，或拼写偏好未知。
        """
        if not 0 <= midi <= 127:
            raise ValueError("MIDI note out of range")

        table = SPELLINGS.get(spelling)
        if table is None:
            raise ValueError(f"Unknown spelling: {spelling!r}")

        step, accidental = table[midi % 12]
        return cls(step, accidental, midi // 12 - 1)

    def transpose(self, semitones: int, *, spelling: Spelling = "sharp") -> Pitch:
        """返回移调后的音高。

        移调量为 0 时原样返回当前对象，保留原有拼写（例如 ``Db4``
        不会被重写为 ``C#4``）。

        Args:
            semitones: 移调的半音数，正值升高、负值降低。
            spelling: 移调结果的等音拼写偏好，仅在移调量非零时生效。

        Returns:
            移调后的音高。

        Raises:
            ValueError: 移调结果超出 MIDI 范围，或拼写偏好未知。
        """
        midi = self.midi + semitones
        if semitones == 0:
            return self
        return self.from_midi(midi, spelling=spelling)


@dataclass(frozen=True)
class Event:
    """展开到时间轴上的音符事件。

    Attributes:
        start: 事件在所属片段中的起点，以四分音符为单位。
        duration: 事件时值，以四分音符为单位。
        pitch: 事件对应的音高。
        velocity: 事件的力度，取值范围为 ``0`` 到 ``127``。
    """

    start: Duration
    duration: Duration
    pitch: Pitch
    velocity: int = 80

    def shifted(self, offset: Duration) -> Event:
        """返回整体平移 ``offset`` 后的副本。

        Args:
            offset: 时间偏移量，以四分音符为单位。

        Returns:
            起点加上 ``offset`` 的新事件，时值与音高不变。
        """
        return Event(self.start + offset, self.duration, self.pitch, self.velocity)

    def __post_init__(self) -> None:
        """校验时值是否为正。

        Raises:
            ValueError: 时值小于或等于零。
        """
        if self.duration <= 0:
            raise ValueError("Event duration must be positive")
        if not 0 <= self.velocity <= 127:
            raise ValueError("Velocity must be in range 0-127")


@dataclass(frozen=True)
class Note(Music):
    """单个音符。

    Attributes:
        pitch: 音符的音高。
        length: 音符时值，必须为正数。

    Raises:
        ValueError: 时值小于或等于零。
    """

    pitch: Pitch
    length: Duration
    velocity: int = 80

    def __post_init__(self) -> None:
        """校验时值是否为正。

        Raises:
            ValueError: 时值小于或等于零。
        """
        if self.length <= 0:
            raise ValueError("Note duration must be positive")

    @property
    def duration(self) -> Duration:
        """音符时值。

        Returns:
            构造时传入的 ``length``。
        """
        return self.length

    def iter_events(self) -> Iterator[Event]:
        """产出从零时刻开始的单个事件。

        Yields:
            时值为 ``length``、音高为 ``pitch`` 的事件。
        """
        yield Event(Fraction(0), self.length, self.pitch, self.velocity)


@dataclass(frozen=True)
class Rest(Music):
    """休止符。

    Attributes:
        length: 休止时值，必须为非负数。

    Raises:
        ValueError: 时值为负数。
    """

    length: Duration

    def __post_init__(self) -> None:
        """校验时值是否为非负。

        Raises:
            ValueError: 时值为负数。
        """
        if self.length < 0:
            raise ValueError("Negative rest duration")

    @property
    def duration(self) -> Duration:
        """休止时值。

        Returns:
            构造时传入的 ``length``。
        """
        return self.length

    def iter_events(self) -> Iterator[Event]:
        """休止符不产生任何事件。

        Yields:
            什么也不产出。
        """
        yield from ()


def N(name: str, length: Duration | int | str, velocity: int = 80) -> Note:
    """按科学音高记号与时值构造单个音符。

    示例：``N("C4", Fraction(1, 4))``、``N("F#3", "1/8")``。

    Args:
        name: 科学音高记号，格式见 :meth:`Pitch.parse`。
        length: 音符时值。接受 :class:`~fractions.Fraction`、整数或
            形如 ``"1/4"`` 的字符串，内部统一转换为
            :class:`~fractions.Fraction`。

    Returns:
        构造得到的 :class:`Note`。

    Raises:
        ValueError: 音高记号或时值不合法。
    """
    return Note(Pitch.parse(name), Fraction(length), velocity)
