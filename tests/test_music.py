"""音乐片段构造、组合与展开的测试。"""

from fractions import Fraction

import pytest

from sonqelra.core import (
    Event,
    Music,
    N,
    Note,
    Parallel,
    Pitch,
    Repeat,
    Rest,
    Sequence,
    Transpose,
)

C4 = Pitch.parse("C4")
E4 = Pitch.parse("E4")


def summary(music: Music) -> list[tuple[Fraction, Fraction, str]]:
    """把片段展开为 (起点, 时值, 音名) 列表，便于断言。"""
    return [
        (event.start, event.duration, event.pitch.name)
        for event in music.events()
    ]


class TestEvent:
    def test_shifted_offsets_start_only(self) -> None:
        event = Event(Fraction(1), Fraction(2), C4)
        shifted = event.shifted(Fraction(1, 4))
        assert shifted == Event(Fraction(5, 4), Fraction(2), C4)


class TestNote:
    def test_exposes_length_as_duration(self) -> None:
        note = Note(C4, Fraction(1, 4))
        assert note.duration == Fraction(1, 4)

    def test_events_start_at_zero(self) -> None:
        note = Note(C4, Fraction(1, 4))
        assert note.events() == (Event(Fraction(0), Fraction(1, 4), C4),)

    @pytest.mark.parametrize("length", [0, -1, Fraction(-1, 4)])
    def test_non_positive_length_raises(self, length: int | Fraction) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            Note(C4, Fraction(length))


class TestN:
    def test_builds_note_from_name_and_length(self) -> None:
        assert N("C#4", "1/8") == Note(Pitch.parse("C#4"), Fraction(1, 8))

    def test_accepts_integer_length(self) -> None:
        assert N("C4", 2).length == Fraction(2)

    def test_accepts_exact_fraction(self) -> None:
        assert N("C4", Fraction(1, 3)).length == Fraction(1, 3)

    def test_invalid_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid pitch"):
            N("H4", 1)

    def test_invalid_length_raises(self) -> None:
        with pytest.raises(ValueError):
            N("C4", "not-a-fraction")

    def test_zero_length_raises(self) -> None:
        with pytest.raises(ValueError, match="must be positive"):
            N("C4", 0)


class TestRest:
    def test_duration(self) -> None:
        assert Rest(Fraction(3, 4)).duration == Fraction(3, 4)

    def test_zero_length_is_allowed(self) -> None:
        assert Rest(Fraction(0)).events() == ()

    def test_produces_no_events(self) -> None:
        assert Rest(Fraction(1)).events() == ()

    def test_negative_length_raises(self) -> None:
        with pytest.raises(ValueError, match="Negative rest duration"):
            Rest(Fraction(-1))


class TestSequence:
    def test_offsets_follow_previous_durations(self) -> None:
        music = (
            N("C4", Fraction(1, 2))
            + Rest(Fraction(1, 4))
            + N("E4", Fraction(1, 4))
        )
        assert isinstance(music, Sequence)
        assert music.duration == 1
        assert summary(music) == [
            (Fraction(0), Fraction(1, 2), "C4"),
            (Fraction(3, 4), Fraction(1, 4), "E4"),
        ]

    def test_nested_sequences_accumulate_offsets(self) -> None:
        inner = N("C4", 1) + N("D4", 1)
        outer = inner + N("E4", 1)
        assert outer.duration == 3
        assert summary(outer) == [
            (Fraction(0), Fraction(1), "C4"),
            (Fraction(1), Fraction(1), "D4"),
            (Fraction(2), Fraction(1), "E4"),
        ]

    def test_empty_sequence_has_zero_duration(self) -> None:
        music = Sequence(())
        assert music.duration == 0
        assert music.events() == ()


class TestParallel:
    def test_starts_all_children_together(self) -> None:
        music = N("C4", 1) | N("E4", Fraction(1, 2))
        assert isinstance(music, Parallel)
        assert music.duration == 1
        assert summary(music) == [
            (Fraction(0), Fraction(1), "C4"),
            (Fraction(0), Fraction(1, 2), "E4"),
        ]

    def test_duration_is_longest_child(self) -> None:
        music = Parallel((N("C4", 1), N("E4", 2)))
        assert music.duration == 2

    def test_empty_parallel_has_zero_duration(self) -> None:
        music = Parallel(())
        assert music.duration == 0
        assert music.events() == ()


class TestRepeat:
    def test_repeats_and_offsets_each_round(self) -> None:
        music = N("C4", Fraction(1, 4)).repeat(3)
        assert isinstance(music, Repeat)
        assert music.duration == Fraction(3, 4)
        assert [event.start for event in music.events()] == [
            Fraction(0), Fraction(1, 4), Fraction(1, 2)
        ]

    def test_repeats_multi_event_sources(self) -> None:
        source = N("C4", 1) + N("D4", 1)
        music = source.repeat(2)
        assert music.duration == 4
        assert summary(music) == [
            (Fraction(0), Fraction(1), "C4"),
            (Fraction(1), Fraction(1), "D4"),
            (Fraction(2), Fraction(1), "C4"),
            (Fraction(3), Fraction(1), "D4"),
        ]

    def test_zero_count_produces_nothing(self) -> None:
        music = N("C4", 1).repeat(0)
        assert music.duration == 0
        assert music.events() == ()

    def test_negative_count_raises(self) -> None:
        with pytest.raises(ValueError, match="Negative repeat count"):
            N("C4", 1).repeat(-1)


class TestTranspose:
    def test_transpose_preserves_velocity(self) -> None:
        assert N("C4", 1, 42).transpose(2).events()[0].velocity == 42

    def test_shifts_pitches_and_keeps_timing(self) -> None:
        music = (
            N("C4", Fraction(1, 2)) + N("E4", Fraction(1, 2))
        ).transpose(2)
        assert isinstance(music, Transpose)
        assert music.duration == 1
        assert summary(music) == [
            (Fraction(0), Fraction(1, 2), "D4"),
            (Fraction(1, 2), Fraction(1, 2), "F#4"),
        ]

    def test_default_spelling_is_sharp(self) -> None:
        music = N("C4", 1).transpose(1)
        assert [event.pitch.name for event in music.events()] == ["C#4"]

    def test_flat_spelling(self) -> None:
        music = N("C4", 1).transpose(1, spelling="flat")
        assert [event.pitch.name for event in music.events()] == ["Db4"]

    def test_zero_semitones_preserves_source_spelling(self) -> None:
        music = N("Db4", 1).transpose(0)
        assert [event.pitch.name for event in music.events()] == ["Db4"]

    def test_rests_silence_does_not_shift_offsets(self) -> None:
        music = (Rest(Fraction(1)) + N("C4", 1)).transpose(2)
        assert summary(music) == [(Fraction(1), Fraction(1), "D4")]

    def test_out_of_range_raises_when_expanded(self) -> None:
        music = N("G9", 1).transpose(1)
        with pytest.raises(ValueError, match="MIDI note out of range"):
            music.events()

    def test_unknown_spelling_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown spelling"):
            Transpose(N("C4", 1), 1, "auto")  # type: ignore[arg-type]

    def test_nested_transposes_compose(self) -> None:
        music = N("C4", 1).transpose(1).transpose(1)
        assert [event.pitch.name for event in music.events()] == ["D4"]


class TestComposition:
    def test_operators_build_composite_fragments(self) -> None:
        a = N("C4", 1)
        b = N("E4", 1)
        c = N("G4", 1)

        sequential = a + b + c
        assert isinstance(sequential, Sequence)
        assert sequential.duration == 3
        assert [event.pitch.name for event in sequential.events()] == [
            "C4", "E4", "G4"
        ]

        parallel = a | (b | c)
        assert isinstance(parallel, Parallel)
        assert parallel.duration == 1
        assert [event.pitch.name for event in parallel.events()] == [
            "C4", "E4", "G4"
        ]

    def test_full_pipeline(self) -> None:
        music = (
            (N("C4", Fraction(1, 4)) + N("D4", Fraction(1, 4))) | N("G3", 1)
        ).repeat(2).transpose(12, spelling="flat")

        assert music.duration == 2
        assert summary(music) == [
            (Fraction(0), Fraction(1, 4), "C5"),
            (Fraction(1, 4), Fraction(1, 4), "D5"),
            (Fraction(0), Fraction(1), "G4"),
            (Fraction(1), Fraction(1, 4), "C5"),
            (Fraction(5, 4), Fraction(1, 4), "D5"),
            (Fraction(1), Fraction(1), "G4"),
        ]
