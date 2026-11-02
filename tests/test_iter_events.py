"""iter_events 的惰性语义，以及与 events 结果的一致性测试。"""

from collections.abc import Iterator
from fractions import Fraction
from itertools import islice

import pytest

from muse.core.basic import (
    Event,
    Music,
    N,
    Parallel,
    Pitch,
    Repeat,
    Rest,
    Sequence,
)


def _piece() -> Music:
    return (
        (N("C4", Fraction(1, 4)) + Rest(Fraction(1, 4)))
        | N("G4", Fraction(1, 2))
    ).repeat(2).transpose(2)


@pytest.mark.parametrize(
    "music",
    [
        N("C4", 1),
        Rest(Fraction(1)),
        Sequence(()),
        Parallel(()),
        N("C4", 1) + N("D4", 1),
        N("C4", 1) | N("E4", 1),
        N("C4", Fraction(1, 4)).repeat(3),
        N("C4", 1).transpose(1, spelling="flat"),
        _piece(),
    ],
    ids=[
        "note", "rest", "empty-sequence", "empty-parallel", "sequence",
        "parallel", "repeat", "transpose", "nested",
    ],
)
def test_iter_events_matches_events(music: Music) -> None:
    assert tuple(music.iter_events()) == music.events()


def test_iter_events_returns_an_iterator() -> None:
    stream = N("C4", 1).iter_events()
    assert iter(stream) is stream


def test_rest_yields_nothing() -> None:
    assert list(Rest(Fraction(1)).iter_events()) == []


def test_partial_iteration_keeps_offsets_correct() -> None:
    music = N("C4", 1) + N("D4", 1) + N("E4", 1)
    stream = music.iter_events()
    assert [next(stream).start for _ in range(3)] == [
        Fraction(0), Fraction(1), Fraction(2)
    ]


class _Counting(Music):
    """测试用片段：记录自身被展开的次数。"""

    def __init__(self, name: str = "C4") -> None:
        self.pitch = Pitch.parse(name)
        self.iterations = 0

    @property
    def duration(self) -> Fraction:
        return Fraction(1)

    def iter_events(self) -> Iterator[Event]:
        self.iterations += 1
        yield Event(Fraction(0), Fraction(1), self.pitch)


class _Infinite(Music):
    """永不结束的测试片段，用于验证惰性求值。"""

    @property
    def duration(self) -> Fraction:
        return Fraction(1)

    def iter_events(self) -> Iterator[Event]:
        index = 0
        while True:
            yield Event(Fraction(index), Fraction(1), Pitch.parse("C4"))
            index += 1


def test_creating_the_iterator_does_not_evaluate_children() -> None:
    first, second = _Counting(), _Counting()
    stream = Sequence((first, second)).iter_events()

    assert first.iterations == 0
    assert second.iterations == 0


def test_sequence_expands_later_children_only_when_needed() -> None:
    first, second = _Counting(), _Counting()
    stream = Sequence((first, second)).iter_events()

    assert next(stream).pitch.midi == 60
    assert first.iterations == 1
    assert second.iterations == 0

    next(stream)
    assert second.iterations == 1


def test_infinite_source_can_be_partially_consumed() -> None:
    stream = _Infinite().iter_events()
    assert [event.start for event in islice(stream, 3)] == [
        Fraction(0), Fraction(1), Fraction(2)
    ]


def test_sequence_with_infinite_child_does_not_block() -> None:
    stream = Sequence((_Infinite(), N("C4", 1))).iter_events()
    assert next(stream).start == 0


def test_repeat_and_transpose_stay_lazy() -> None:
    music = Repeat(_Infinite(), 2).transpose(2)
    events = list(islice(music.iter_events(), 3))
    assert [event.pitch.name for event in events] == ["D4", "D4", "D4"]
    assert [event.start for event in events] == [
        Fraction(0), Fraction(1), Fraction(2)
    ]


def test_errors_are_deferred_until_consumed() -> None:
    stream = N("G9", 1).transpose(1).iter_events()
    with pytest.raises(ValueError, match="MIDI note out of range"):
        next(stream)


def test_events_defaults_to_iter_events_for_custom_fragments() -> None:
    music = _Counting()
    assert music.events() == (
        Event(Fraction(0), Fraction(1), Pitch.parse("C4")),
    )
