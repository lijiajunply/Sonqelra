"""组合层：构成可嵌套的音乐表达式树。

本模块提供四种组合片段：

- ``a + b`` 串行组合（:class:`Sequence`）
- ``a | b`` 并行组合（:class:`Parallel`）
- ``a.repeat(n)`` 重复（:class:`Repeat`）
- ``a.transpose(n)`` 移调（:class:`Transpose`）

片段内部通过 :meth:`~sonqelra.core.base.Music.iter_events` 惰性展开为
时间轴上的事件序列。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction

from .atomic import SPELLINGS, Duration, Event, Spelling
from .base import Music


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
        if self.spelling not in SPELLINGS:
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
            yield Event(event.start, event.duration, pitch, event.velocity)
