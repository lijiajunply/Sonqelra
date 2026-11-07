from fractions import Fraction

from mido import MidiFile

from muse.backends.mido import muse_to_midi
from muse.core import N, Track
from muse.core.work import Score, TempoMap


def test_midi_export_uses_delta_times_and_bpm(tmp_path):
    music = N("C4", 1) + (N("E4", 1) | N("G4", 1))
    score = Score(
        tracks=(Track(music=music, instrument="Piano", name="Piano"),),
        title="Test",
        tempo_map=TempoMap(((Fraction(0), 120), (Fraction(1), 60))),
    )
    path = tmp_path / "test.mid"
    muse_to_midi(score, str(path))

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
    from muse.backends.mido import midi_to_muse
    from muse.core.work import TimeSignature

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

    score = midi_to_muse(str(path))
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
    from muse.backends.mido import midi_to_muse

    music = N("C4", 1, 93) + (N("E4", 2, 71) | N("G4", 1, 65))
    original = Score(tracks=(Track(music=music, instrument="Piano", name="Piano"),), title="Test")
    path = tmp_path / "roundtrip.mid"
    muse_to_midi(original, str(path))
    restored = midi_to_muse(str(path))
    assert sorted(restored.tracks[0].music.events(), key=lambda e: (e.start, e.pitch.midi)) == sorted(
        music.events(), key=lambda e: (e.start, e.pitch.midi)
    )


def test_midi_import_rejects_unclosed_note(tmp_path):
    import pytest
    from mido import Message, MidiTrack
    from muse.backends.mido import midi_to_muse

    midi = MidiFile()
    midi.tracks.append(MidiTrack([Message("note_on", note=60, velocity=80)]))
    path = tmp_path / "unclosed.mid"
    midi.save(path)
    with pytest.raises(ValueError, match="Unclosed notes"):
        midi_to_muse(str(path))
