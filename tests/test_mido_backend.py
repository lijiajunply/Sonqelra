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
