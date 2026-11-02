from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import TypeAlias

Duration: TypeAlias = Fraction

STEPS = {
    "C": 0, "D": 2, "E": 4, "F": 5,
    "G": 7, "A": 9, "B": 11,
}


@dataclass(frozen=True)
class Pitch:
    step: str
    accidental: int
    octave: int

    def __post_init__(self):
        if self.step not in STEPS:
            raise ValueError("Invalid pitch step")

    @property
    def midi(self) -> int:
        value = (
            12 * (self.octave + 1)
            + STEPS[self.step]
            + self.accidental
        )
        if not 0 <= value <= 127:
            raise ValueError("Pitch outside MIDI range")
        return value

    @classmethod
    def parse(cls, name: str) -> Pitch:
        import re

        match = re.fullmatch(
            r"([A-G])([#b]?)(-?\d+)", name
        )
        if not match:
            raise ValueError(f"Invalid pitch: {name}")

        step, accidental, octave = match.groups()
        offset = {"": 0, "#": 1, "b": -1}
        return cls(step, offset[accidental], int(octave))


@dataclass(frozen=True)
class Event:
    start: Duration
    duration: Duration
    pitch: Pitch


class Music:
    @property
    def duration(self) -> Duration:
        raise NotImplementedError

    def events(self) -> tuple[Event, ...]:
        raise NotImplementedError

    def __add__(self, other: Music) -> Music:
        return Sequence((self, other))

    def __or__(self, other: Music) -> Music:
        return Parallel((self, other))

    def repeat(self, count: int) -> Music:
        if count < 0:
            raise ValueError("Negative repeat count")
        return Repeat(self, count)

    def transpose(self, semitones: int) -> Music:
        return Transpose(self, semitones)


@dataclass(frozen=True)
class Note(Music):
    pitch: Pitch
    length: Duration

    def __post_init__(self):
        if self.length <= 0:
            raise ValueError("Note duration must be positive")

    @property
    def duration(self):
        return self.length

    def events(self):
        return (Event(Fraction(0), self.length, self.pitch),)


@dataclass(frozen=True)
class Rest(Music):
    length: Duration

    def __post_init__(self):
        if self.length < 0:
            raise ValueError("Negative rest duration")

    @property
    def duration(self):
        return self.length

    def events(self):
        return ()


@dataclass(frozen=True)
class Sequence(Music):
    children: tuple[Music, ...]

    @property
    def duration(self):
        return sum(
            (child.duration for child in self.children),
            Fraction(0)
        )

    def events(self):
        result = []
        offset = Fraction(0)

        for child in self.children:
            for event in child.events():
                result.append(Event(
                    event.start + offset,
                    event.duration,
                    event.pitch
                ))
            offset += child.duration

        return tuple(result)


@dataclass(frozen=True)
class Parallel(Music):
    children: tuple[Music, ...]

    @property
    def duration(self):
        return max(
            (child.duration for child in self.children),
            default=Fraction(0)
        )

    def events(self):
        result = []
        for child in self.children:
            result.extend(child.events())
        return tuple(result)


@dataclass(frozen=True)
class Repeat(Music):
    source: Music
    count: int

    @property
    def duration(self):
        return self.source.duration * self.count

    def events(self):
        result = []
        source_events = self.source.events()

        for i in range(self.count):
            offset = self.source.duration * i
            for event in source_events:
                result.append(Event(
                    event.start + offset,
                    event.duration,
                    event.pitch
                ))

        return tuple(result)


@dataclass(frozen=True)
class Transpose(Music):
    source: Music
    semitones: int

    @property
    def duration(self):
        return self.source.duration

    def events(self):
        result = []

        for event in self.source.events():
            midi = event.pitch.midi + self.semitones
            if not 0 <= midi <= 127:
                raise ValueError("Transposed pitch out of range")

            # MVP: canonical sharp spelling
            names = (
                ("C", 0), ("C", 1),
                ("D", 0), ("D", 1),
                ("E", 0), ("F", 0),
                ("F", 1), ("G", 0),
                ("G", 1), ("A", 0),
                ("A", 1), ("B", 0)
            )
            step, accidental = names[midi % 12]
            pitch = Pitch(step, accidental, midi // 12 - 1)

            result.append(Event(
                event.start,
                event.duration,
                pitch
            ))

        return tuple(result)


def N(name: str, length: Duration) -> Note:
    return Note(Pitch.parse(name), Fraction(length))
