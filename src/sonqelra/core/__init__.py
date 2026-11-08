"""sonqelra 的核心数据模型。

按三个层次组织：

- :mod:`sonqelra.core.atomic`：原子层，不可再拆分的基本音乐数据。
- :mod:`sonqelra.core.compose`：组合层，可嵌套的音乐表达式树。
- :mod:`sonqelra.core.work`：作品层，组织音轨与全局时间信息。

本模块重新导出原子层与组合层对外公开的类型，便于
``from sonqelra.core import Pitch, N``。
"""

from .atomic import Duration, Event, N, Note, Pitch, Rest, Spelling
from .base import Music
from .compose import Parallel, Repeat, Sequence, Transpose
from .work import ControlChange, PitchBend, Track, Score, TempoMap, MeterMap, TimeSignature

__all__ = [
    "Duration",
    "Event",
    "Music",
    "N",
    "Note",
    "Parallel",
    "Pitch",
    "Repeat",
    "Rest",
    "Sequence",
    "Spelling",
    "Transpose",
    "Track",
    "ControlChange",
    "PitchBend",
    "Score",
    "TempoMap",
    "MeterMap",
    "TimeSignature",
]
