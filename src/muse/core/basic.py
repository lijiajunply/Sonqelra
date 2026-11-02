"""音乐组合 DSL 的核心数据模型。

本模块提供两种基础类型：

- :class:`Pitch`：用音名、变音记号与八度描述的音高。
- :class:`Event`：带有绝对起点和时长的音符事件。

以及一组可通过运算符组合的音乐片段（:class:`Music`）：

- ``a + b`` 串行组合（:class:`Sequence`）
- ``a | b`` 并行组合（:class:`Parallel`）
- ``a.repeat(n)`` 重复
- ``a.transpose(n)`` 移调

所有时长均以四分音符为单位，使用 :class:`fractions.Fraction`
精确表示，避免浮点误差。片段内部通过 :meth:`Music.iter_events`
惰性展开为时间轴上的事件序列，:meth:`Music.events` 则一次性返回
元组；两者结果相同，前者适合长片段或只取前几个事件的场景。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction
from typing import Final, Literal, TypeAlias

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
_SPELLINGS: Final[dict[Spelling, tuple[tuple[str, int], ...]]] = {
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

        table = _SPELLINGS.get(spelling)
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
    """

    start: Duration
    duration: Duration
    pitch: Pitch

    def shifted(self, offset: Duration) -> Event:
        """返回整体平移 ``offset`` 后的副本。

        Args:
            offset: 时间偏移量，以四分音符为单位。

        Returns:
            起点加上 ``offset`` 的新事件，时值与音高不变。
        """
        return Event(self.start + offset, self.duration, self.pitch)


class Music:
    """可组合的音乐片段基类。

    子类必须实现 :attr:`duration` 与 :meth:`iter_events`；基类通过
    ``+``、``|``、:meth:`repeat`、:meth:`transpose` 提供组合能力。
    :meth:`events` 由 :meth:`iter_events` 派生，无需重写。
    """

    @property
    def duration(self) -> Duration:
        """片段的总时长，以四分音符为单位。

        Returns:
            子类实现的总时长。

        Raises:
            NotImplementedError: 子类未实现本属性。
        """
        raise NotImplementedError

    def events(self) -> tuple[Event, ...]:
        """将片段展开为事件元组（立即求值）。

        等价于 ``tuple(self.iter_events())``。片段较长且只需前几个
        事件时，应改用 :meth:`iter_events` 以提前停止计算。

        Returns:
            事件元组，其中每个事件的 ``start`` 均相对于片段起点。
        """
        return tuple(self.iter_events())

    def iter_events(self) -> Iterator[Event]:
        """惰性展开片段，逐个产出事件。

        事件顺序与 :meth:`events` 完全一致，但不会一次性构造完整
        元组；下游可以按需取用，甚至从大型或无限结构中只取前几项。

        Returns:
            事件迭代器，其中每个事件的 ``start`` 均相对于片段起点。

        Raises:
            NotImplementedError: 子类未实现本方法。
        """
        raise NotImplementedError

    def __add__(self, other: Music) -> Sequence:
        """串行组合：当前片段在前，``other`` 紧随其后。

        Args:
            other: 要接在当前片段之后的音乐片段。

        Returns:
            包含两个子片段的 :class:`Sequence`。
        """
        return Sequence((self, other))

    def __or__(self, other: Music) -> Parallel:
        """并行组合：两个片段同时开始。

        Args:
            other: 与当前片段同时演奏的音乐片段。

        Returns:
            包含两个子片段的 :class:`Parallel`。
        """
        return Parallel((self, other))

    def repeat(self, count: int) -> Repeat:
        """将当前片段重复 ``count`` 次。

        Args:
            count: 重复次数，必须为非负整数。

        Returns:
            重复后的 :class:`Repeat` 片段。

        Raises:
            ValueError: ``count`` 为负数。
        """
        if count < 0:
            raise ValueError("Negative repeat count")
        return Repeat(self, count)

    def transpose(
        self, semitones: int, *, spelling: Spelling = "sharp"
    ) -> Transpose:
        """将当前片段按半音数移调。

        Args:
            semitones: 移调的半音数，正值升高、负值降低。
            spelling: 移调结果的等音拼写偏好：``"sharp"`` 使用升号，
                ``"flat"`` 使用降号。

        Returns:
            移调后的 :class:`Transpose` 片段。
        """
        return Transpose(self, semitones, spelling)


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
        yield Event(Fraction(0), self.length, self.pitch)


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


@dataclass(frozen=True)
class Sequence(Music):
    """串行组合：子片段依次播放。

    Attributes:
        children: 按播放顺序排列的子片段。
    """

    children: tuple[Music, ...]

    @property
    def duration(self) -> Duration:
        """所有子片段时值之和。

        Returns:
            片段总时长。
        """
        return sum(
            (child.duration for child in self.children),
            Fraction(0)
        )

    def iter_events(self) -> Iterator[Event]:
        """按顺序惰性产出子片段的事件，并将它们平移到各自的时间偏移。

        Yields:
            按子片段顺序拼接、起点已平移的事件。
        """
        offset = Fraction(0)

        for child in self.children:
            for event in child.iter_events():
                yield event.shifted(offset)
            offset += child.duration


@dataclass(frozen=True)
class Parallel(Music):
    """并行组合：子片段同时开始。

    Attributes:
        children: 同时播放的子片段。
    """

    children: tuple[Music, ...]

    @property
    def duration(self) -> Duration:
        """所有子片段中最长的时值；无子片段时为零。

        Returns:
            片段总时长。
        """
        return max(
            (child.duration for child in self.children),
            default=Fraction(0)
        )

    def iter_events(self) -> Iterator[Event]:
        """依次惰性产出各子片段的事件，不做时间平移。

        子片段按构造顺序依次展开：在完全取完前一个子片段之前，不会
        开始展开下一个。

        Yields:
            所有子片段直接拼接的事件。
        """
        for child in self.children:
            yield from child.iter_events()


@dataclass(frozen=True)
class Repeat(Music):
    """重复片段：将源片段连续播放若干次。

    Attributes:
        source: 被重复的片段。
        count: 重复次数。
    """

    source: Music
    count: int

    @property
    def duration(self) -> Duration:
        """源片段时值乘以重复次数。

        Returns:
            片段总时长。
        """
        return self.source.duration * self.count

    def iter_events(self) -> Iterator[Event]:
        """逐轮惰性产出源片段的事件，并将每轮平移到对应偏移。

        Yields:
            所有轮次拼接、起点已平移的事件。
        """
        for i in range(self.count):
            offset = self.source.duration * i
            for event in self.source.iter_events():
                yield event.shifted(offset)


@dataclass(frozen=True)
class Transpose(Music):
    """移调片段：将源片段的所有音高按半音数平移。

    Attributes:
        source: 被移调的片段。
        semitones: 移调的半音数，正值升高、负值降低。
        spelling: 移调结果的等音拼写偏好：``"sharp"`` 使用升号，
            ``"flat"`` 使用降号。默认 ``"sharp"``。

    Raises:
        ValueError: 构造时 ``spelling`` 不是已知的拼写偏好。
    """

    source: Music
    semitones: int
    spelling: Spelling = "sharp"

    def __post_init__(self) -> None:
        """校验拼写偏好是否合法。

        Raises:
            ValueError: ``spelling`` 不是 ``"sharp"`` 或 ``"flat"``。
        """
        if self.spelling not in _SPELLINGS:
            raise ValueError(f"Unknown spelling: {self.spelling!r}")

    @property
    def duration(self) -> Duration:
        """移调不改变时值，与源片段相同。

        Returns:
            片段总时长。
        """
        return self.source.duration

    def iter_events(self) -> Iterator[Event]:
        """对源片段每个事件惰性应用音高平移。

        移调量为 0 时保留源音高的拼写；否则按 ``spelling`` 决定等音
        拼写，例如 MIDI 61 在 ``"sharp"`` 下记为 ``C#4``，在
        ``"flat"`` 下记为 ``Db4``。

        Yields:
            移调后的事件。

        Raises:
            ValueError: 移调后的音高超出 MIDI 范围。
        """
        for event in self.source.iter_events():
            pitch = event.pitch.transpose(
                self.semitones, spelling=self.spelling
            )
            yield Event(event.start, event.duration, pitch)


def N(name: str, length: Duration | int | str) -> Note:
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
    return Note(Pitch.parse(name), Fraction(length))
