from fractions import Fraction as F
from muse.backends.mido import muse_to_midi
from muse.core import N, Track
from muse.core.work import Score, Tempo, TimeSignature

melody = (
    N("C4", F(1, 4), velocity=90)
    + N("E4", F(1, 4), velocity=80)
    + N("G4", F(1, 2), velocity=100)
)

harmony = melody.transpose(-12)

score = Score(
    title="My First Music",
    tracks=(
        Track(music=melody, instrument="Piano", name="Piano"),
        Track(music=harmony, instrument="Acoustic Bass", name="Bass"),
    )
)

muse_to_midi(score, "my_first_music.mid")
