from fractions import Fraction as F
from muse.core.basic import N

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

print(composition.duration)
# 1

for event in composition.events():
    print(event.start, event.pitch.midi, event.duration)