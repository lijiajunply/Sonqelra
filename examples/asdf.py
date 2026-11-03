from fractions import Fraction as F
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
    tempo=Tempo(120),
    time_signature=TimeSignature(4, 4),
    tracks=(
        Track("Piano", "Piano", melody),
        Track("Bass", "Acoustic Bass", harmony),
    )
)