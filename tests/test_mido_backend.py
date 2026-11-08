from fractions import Fraction

from mido import MidiFile

from sonqelra.backends.mido import sonqelra_to_midi
from sonqelra.core import N, Track
from sonqelra.core.work import Score, TempoMap


def test_midi_export_uses_delta_times_and_bpm(tmp_path):
    music = N("C4", 1) + (N("E4", 1) | N("G4", 1))
    score = Score(
        tracks=(Track(music=music, instrument="Piano", name="Piano"),),
        title="Test",
        tempo_map=TempoMap(((Fraction(0), 120), (Fraction(1), 60))),
    )
    path = tmp_path / "test.mid"
    sonqelra_to_midi(score, str(path))

    track = MidiFile(path).tracks[0]
    tick = 0
    events = []
    for message in track:
        tick += message.time
        if message.type in {"set_tempo", "note_on", "note_off"}:
            events.append((tick, message.type, getattr(message, "note", None),
                           getattr(message, "tempo", None)))
    assert events == [
        (0, "set_tempo", None, 500000),
        (0, "note_on", 60, None),
        (480, "set_tempo", None, 1000000),
        (480, "note_off", 60, None),
        (480, "note_on", 64, None),
        (480, "note_on", 67, None),
        (960, "note_off", 64, None),
        (960, "note_off", 67, None),
    ]


def test_midi_import_handles_polyphony_changes_and_silence(tmp_path):
    from mido import Message, MetaMessage, MidiTrack
    from sonqelra.backends.mido import midi_to_sonqelra
    from sonqelra.core.work import TimeSignature

    midi = MidiFile(ticks_per_beat=480)
    conductor = MidiTrack([
        MetaMessage("set_tempo", tempo=600000),
        MetaMessage("time_signature", numerator=3, denominator=4),
        MetaMessage("set_tempo", tempo=500000, time=480),
    ])
    track = MidiTrack([
        MetaMessage("track_name", name="Parts"),
        Message("program_change", channel=0, program=40),
        Message("note_on", channel=0, note=60, velocity=70, time=240),
        Message("note_on", channel=1, note=64, velocity=90),
        Message("note_off", channel=0, note=60, time=480),
        Message("note_on", channel=1, note=64, velocity=0, time=240),
        MetaMessage("end_of_track", time=480),
    ])
    midi.tracks.extend([conductor, track])
    path = tmp_path / "parts.mid"
    midi.save(path)

    score = midi_to_sonqelra(str(path))
    assert score.title == "parts"
    assert score.tempo_map.tempo == ((Fraction(0), 100), (Fraction(1), 120))
    assert score.meter_map.meter == ((Fraction(0), TimeSignature(3, 4)),)
    assert [track.instrument for track in score.tracks] == ["Violin", "Acoustic Grand Piano"]
    first, second = score.tracks
    assert first.music.duration == second.music.duration == 3
    assert [(e.start, e.duration, e.pitch.midi, e.velocity) for e in first.music.events()] == [
        (Fraction(1, 2), Fraction(1), 60, 70)
    ]
    assert [(e.start, e.duration, e.pitch.midi, e.velocity) for e in second.music.events()] == [
        (Fraction(1, 2), Fraction(3, 2), 64, 90)
    ]


def test_midi_import_round_trip_preserves_notes(tmp_path):
    from sonqelra.backends.mido import midi_to_sonqelra

    music = N("C4", 1, 93) + (N("E4", 2, 71) | N("G4", 1, 65))
    original = Score(tracks=(Track(music=music, instrument="Piano", name="Piano"),), title="Test")
    path = tmp_path / "roundtrip.mid"
    sonqelra_to_midi(original, str(path))
    restored = midi_to_sonqelra(str(path))
    assert sorted(restored.tracks[0].music.events(), key=lambda e: (e.start, e.pitch.midi)) == sorted(
        music.events(), key=lambda e: (e.start, e.pitch.midi)
    )


def test_midi_import_rejects_unclosed_note(tmp_path):
    import pytest
    from mido import Message, MidiTrack
    from sonqelra.backends.mido import midi_to_sonqelra

    midi = MidiFile()
    midi.tracks.append(MidiTrack([Message("note_on", note=60, velocity=80)]))
    path = tmp_path / "unclosed.mid"
    midi.save(path)
    with pytest.raises(ValueError, match="Unclosed notes"):
        midi_to_sonqelra(str(path))


def test_multitrack_export_round_trip(tmp_path):
    from sonqelra.backends.mido import midi_to_sonqelra
    from sonqelra.core import MeterMap, Rest, TimeSignature

    melody = N("C4", 1, 65).transpose(2) + Rest(Fraction(1, 2)) + N("E4", 1, 90)
    harmony = (N("C3", 2, 55) | N("G3", 2, 60)) + Rest(Fraction(1))
    original = Score(
        tracks=(Track(melody, "Piano", "Melody"), Track(harmony, "Violin", "Harmony")),
        title="Example",
        tempo_map=TempoMap(((Fraction(0), 100),)),
        meter_map=MeterMap(((Fraction(0), TimeSignature(3, 4)),)),
    )
    path = tmp_path / "multitrack.mid"
    sonqelra_to_midi(original, str(path))
    midi = MidiFile(path)
    assert [[(m.channel, m.program) for m in t if m.type == "program_change"] for t in midi.tracks] == [[(0, 0)], [(1, 40)]]
    restored = midi_to_sonqelra(str(path))
    assert [t.instrument for t in restored.tracks] == ["Acoustic Grand Piano", "Violin"]
    assert restored.tempo_map == original.tempo_map
    assert restored.meter_map == original.meter_map
    for source, result in zip(original.tracks, restored.tracks):
        assert sorted(source.music.events(), key=lambda e: (e.start, e.pitch.midi)) == sorted(result.music.events(), key=lambda e: (e.start, e.pitch.midi))
        assert source.music.duration == result.music.duration


def test_export_rejects_unrepresentable_time_and_ambiguous_notes(tmp_path):
    import pytest

    def export(music):
        sonqelra_to_midi(Score((Track(music, "Piano", "Test"),), "Test"), str(tmp_path / "test.mid"))

    with pytest.raises(ValueError, match="cannot be represented exactly"):
        export(N("C4", Fraction(1, 7)))
    with pytest.raises(ValueError, match="Overlapping notes"):
        export(N("C4", 2) | N("C4", 1))
    with pytest.raises(ValueError, match="velocity"):
        export(N("C4", 1, 0))


def test_export_rejects_too_many_tracks(tmp_path):
    import pytest

    score = Score(tuple(Track(N("C4", 1), "Piano", str(i)) for i in range(16)), "Test")
    with pytest.raises(ValueError, match="15 melodic tracks"):
        sonqelra_to_midi(score, str(tmp_path / "test.mid"))


def test_midi_round_trip_preserves_channel_controls_drums_and_exact_tempo(tmp_path):
    from mido import Message, MetaMessage, MidiTrack
    from sonqelra.backends.mido import midi_to_sonqelra
    from sonqelra.core import ControlChange, PitchBend

    source = MidiFile(ticks_per_beat=480)
    source.tracks.extend([
        MidiTrack([
            MetaMessage("set_tempo", tempo=500001),
            Message("control_change", channel=9, control=64, value=127, time=120),
            Message("pitchwheel", channel=9, pitch=-1024, time=120),
            Message("control_change", channel=9, control=64, value=0, time=480),
        ]),
        MidiTrack([
            Message("program_change", channel=9, program=8),
            Message("note_on", channel=9, note=36, velocity=90),
            Message("note_off", channel=9, note=36, time=480),
        ]),
    ])
    path = tmp_path / "source.mid"
    source.save(path)
    score = midi_to_sonqelra(str(path))
    assert score.tempo_map.tempo == ((Fraction(0), Fraction(60000000, 500001)),)
    assert score.tracks[0].is_percussion
    assert score.tracks[0].controls == (
        ControlChange(Fraction(1, 4), 64, 127), PitchBend(Fraction(1, 2), -1024),
        ControlChange(Fraction(3, 2), 64, 0),
    )
    output = tmp_path / "output.mid"
    sonqelra_to_midi(score, str(output))
    messages = MidiFile(output).tracks[0]
    assert next(m.tempo for m in messages if m.type == "set_tempo") == 500001
    assert next((m.channel, m.program) for m in messages if m.type == "program_change") == (9, 8)
    assert all(m.channel == 9 for m in messages if m.type in {"note_on", "note_off", "control_change", "pitchwheel"})
    restored = midi_to_sonqelra(str(output))
    assert restored.tracks[0].controls == score.tracks[0].controls
    assert restored.tempo_map == score.tempo_map


def test_midi_import_preserves_controls_without_notes(tmp_path):
    from mido import Message, MidiTrack
    from sonqelra.backends.mido import midi_to_sonqelra
    from sonqelra.core import ControlChange

    source = MidiFile()
    source.tracks.append(MidiTrack([Message("control_change", channel=3, control=64, value=127, time=240)]))
    path = tmp_path / "control.mid"
    source.save(path)
    score = midi_to_sonqelra(str(path))
    assert score.tracks[0].controls == (ControlChange(Fraction(1, 2), 64, 127),)
    output = tmp_path / "control-out.mid"
    sonqelra_to_midi(score, str(output))
    assert midi_to_sonqelra(str(output)).tracks[0].controls == score.tracks[0].controls
