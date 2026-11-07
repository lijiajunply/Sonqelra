"""生成一个包含旋律与和弦的双轨 MIDI 文件。"""
from fractions import Fraction

from muse.backends.mido import muse_to_midi
from muse.core import N, Rest, Score, TempoMap, Track

melody = N("C4", 1, 85) + Rest(Fraction(1, 2)) + N("E4", 1, 90) + N("G4", 1)
chords = (N("C3", 2, 60) | N("E3", 2, 60) | N("G3", 2, 60)) + Rest(1)
score = Score(
    tracks=(Track(melody, "Piano", "Melody"), Track(chords, "Violin", "Harmony")),
    title="Muse example",
    tempo_map=TempoMap(((Fraction(0), 100),)),
)

if __name__ == "__main__":
    muse_to_midi(score, "multitrack.mid")
    print("已生成 multitrack.mid")
