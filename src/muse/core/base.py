"""片段抽象基类。

本模块只定义 :class:`Music`，作为原子层与组合层所有片段的共同父类。
组合运算符（``+``、``|``、:meth:`~Music.repeat`、:meth:`~Music.transpose`）
在调用时才导入组合层的实现，从而避免原子层与组合层之间的循环依赖。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .atomic import Duration, Event, Spelling
    from .compose import Parallel, Repeat, Sequence, Transpose


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
            包含两个子片段的 :class:`~muse.core.compose.Sequence`。
        """
        from .compose import Sequence

        return Sequence((self, other))

    def __or__(self, other: Music) -> Parallel:
        """并行组合：两个片段同时开始。

        Args:
            other: 与当前片段同时演奏的音乐片段。

        Returns:
            包含两个子片段的 :class:`~muse.core.compose.Parallel`。
        """
        from .compose import Parallel

        return Parallel((self, other))

    def repeat(self, count: int) -> Repeat:
        """将当前片段重复 ``count`` 次。

        Args:
            count: 重复次数，必须为非负整数。

        Returns:
            重复后的 :class:`~muse.core.compose.Repeat` 片段。

        Raises:
            ValueError: ``count`` 为负数。
        """
        from .compose import Repeat

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
            移调后的 :class:`~muse.core.compose.Transpose` 片段。
        """
        from .compose import Transpose

        return Transpose(self, semitones, spelling)
