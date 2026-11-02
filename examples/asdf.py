from fractions import Fraction as F
from muse.core import N, Track
from muse.core.work import Score

theme = (
    N("C4", F(1, 4))
    + N("D4", F(1, 4))
    + N("E4", F(1, 4))
    + N("G4", F(1, 4))
)

harmony = (
    N("E4", F(1, 2))
    + N("G4", F(1, 2))
)

composition = theme | harmony

track = Track(music=composition, instrument="Piano", name="My Track")

score = Score(tracks=(track,), title="My Score")

print(score)
# 1

for event in composition.events():
    print(event.start, event.pitch.midi, event.duration)