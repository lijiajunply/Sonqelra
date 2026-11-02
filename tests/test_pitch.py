"""Pitch 的解析、MIDI 换算与等音拼写测试。"""

import pytest

from muse.core.basic import Pitch


class TestParse:
    """Pitch.parse 的格式处理。"""

    @pytest.mark.parametrize(
        ("name", "step", "accidental", "octave"),
        [
            ("C4", "C", 0, 4),
            ("F#3", "F", 1, 3),
            ("Bb5", "B", -1, 5),
            ("A-1", "A", 0, -1),
            ("C##4", "C", 2, 4),
            ("C###4", "C", 3, 4),
            ("Dbb4", "D", -2, 4),
        ],
    )
    def test_parses_scientific_pitch_notation(
        self, name: str, step: str, accidental: int, octave: int
    ) -> None:
        pitch = Pitch.parse(name)
        assert (pitch.step, pitch.accidental, pitch.octave) == (
            step, accidental, octave
        )

    @pytest.mark.parametrize(
        "name",
        ["", "H4", "c4", "C", "C#", "4C", "C#b4", "Cb#4", "C4x"],
    )
    def test_rejects_invalid_notation(self, name: str) -> None:
        with pytest.raises(ValueError, match="Invalid pitch"):
            Pitch.parse(name)


class TestMidi:
    """MIDI 编号与音高之间的换算。"""

    @pytest.mark.parametrize(
        ("name", "midi"),
        [
            ("C-1", 0),
            ("C4", 60),
            ("C#4", 61),
            ("Db4", 61),
            ("B#3", 60),
            ("Cb4", 59),
            ("C##4", 62),
            ("Dbb4", 60),
            ("G9", 127),
        ],
    )
    def test_midi_property(self, name: str, midi: int) -> None:
        assert Pitch.parse(name).midi == midi

    @pytest.mark.parametrize("name", ["C-2", "G#9"])
    def test_midi_out_of_range_raises(self, name: str) -> None:
        with pytest.raises(ValueError, match="outside MIDI range"):
            _ = Pitch.parse(name).midi

    @pytest.mark.parametrize("spelling", ["sharp", "flat"])
    def test_from_midi_round_trips_for_all_notes(self, spelling: str) -> None:
        for midi in range(128):
            pitch = Pitch.from_midi(midi, spelling=spelling)  # type: ignore[arg-type]
            assert pitch.midi == midi
            assert Pitch.parse(pitch.name) == pitch

    def test_from_midi_prefers_sharp_spelling(self) -> None:
        assert Pitch.from_midi(61).name == "C#4"

    def test_from_midi_prefers_flat_spelling(self) -> None:
        assert Pitch.from_midi(61, spelling="flat").name == "Db4"

    def test_from_midi_handles_octave_boundaries(self) -> None:
        assert Pitch.from_midi(0).name == "C-1"
        assert Pitch.from_midi(127).name == "G9"

    @pytest.mark.parametrize("midi", [-1, 128])
    def test_from_midi_rejects_out_of_range(self, midi: int) -> None:
        with pytest.raises(ValueError, match="MIDI note out of range"):
            Pitch.from_midi(midi)

    def test_from_midi_rejects_unknown_spelling(self) -> None:
        with pytest.raises(ValueError, match="Unknown spelling"):
            Pitch.from_midi(60, spelling="auto")  # type: ignore[arg-type]


class TestName:
    """音高记号的序列化。"""

    @pytest.mark.parametrize(
        ("pitch", "name"),
        [
            (Pitch("C", 0, 4), "C4"),
            (Pitch("C", 1, 4), "C#4"),
            (Pitch("B", -1, 3), "Bb3"),
            (Pitch("C", 2, 4), "C##4"),
            (Pitch("D", -3, 4), "Dbbb4"),
        ],
    )
    def test_name(self, pitch: Pitch, name: str) -> None:
        assert pitch.name == name

    def test_str_matches_name(self) -> None:
        assert str(Pitch.parse("F#3")) == "F#3"

    @pytest.mark.parametrize("accidental", [-3, -2, -1, 0, 1, 2, 3])
    def test_name_round_trips_through_parse(self, accidental: int) -> None:
        pitch = Pitch("C", accidental, 4)
        assert Pitch.parse(pitch.name) == pitch

    def test_invalid_step_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid pitch step"):
            Pitch("H", 0, 4)


class TestTranspose:
    """音高移调与拼写选择。"""

    def test_shifts_by_semitones(self) -> None:
        assert Pitch.parse("C4").transpose(2).name == "D4"
        assert Pitch.parse("C4").transpose(12).name == "C5"
        assert Pitch.parse("B4").transpose(1).name == "C5"

    def test_spelling_defaults_to_sharp(self) -> None:
        assert Pitch.parse("C4").transpose(1).name == "C#4"

    def test_spelling_can_prefer_flats(self) -> None:
        assert Pitch.parse("C4").transpose(1, spelling="flat").name == "Db4"
        assert Pitch.parse("E4").transpose(1, spelling="flat").name == "F4"

    def test_zero_semitones_preserves_spelling(self) -> None:
        pitch = Pitch.parse("Db4")
        assert pitch.transpose(0) is pitch
        assert pitch.transpose(0, spelling="sharp").name == "Db4"

    def test_negative_semitones(self) -> None:
        assert Pitch.parse("C4").transpose(-1).name == "B3"
        assert Pitch.parse("C4").transpose(-2, spelling="flat").name == "Bb3"

    @pytest.mark.parametrize("name", ["G9", "C-1"])
    def test_out_of_range_raises(self, name: str) -> None:
        semitones = 1 if name == "G9" else -1
        with pytest.raises(ValueError, match="MIDI note out of range"):
            Pitch.parse(name).transpose(semitones)

    def test_unknown_spelling_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown spelling"):
            Pitch.parse("C4").transpose(1, spelling="auto")  # type: ignore[arg-type]
