import subprocess

from muse.backends.mido import muse_to_midi
from muse.core import N, Score, TempoMap, Track

# 时值以四分音符为一拍：1 是四分音符，1/2 是八分音符。
from fractions import Fraction as F


# C 大调，4/4 拍。每个乐句占一小节，按原曲重复一次。
phrase_1 = N("C4", 1, 95) + N("D4", 1, 95) + N("E4", 1, 95) + N("C4", 1, 95)
phrase_2 = N("E4", 1, 95) + N("F4", 1, 95) + N("G4", 2, 95)
phrase_3 = (
    N("G4", F(1, 2), 95) + N("A4", F(1, 2), 95)
    + N("G4", F(1, 2), 95) + N("F4", F(1, 2), 95)
    + N("E4", 1, 95) + N("C4", 1, 95)
)
phrase_4 = N("C4", 1, 95) + N("G3", 1, 95) + N("C4", 2, 95)
melody = phrase_1.repeat(2) + phrase_2.repeat(2) + phrase_3.repeat(2) + phrase_4.repeat(2)

# 每小节一个和弦；用 | 让音符同时发声。
c_major = N("C3", 4, 55) | N("E3", 4, 55) | N("G3", 4, 55)
g_major = N("G2", 4, 55) | N("B2", 4, 55) | N("D3", 4, 55)
chords = c_major.repeat(6) + g_major + c_major

# 低音与和弦同步，给旋律提供稳定的节拍。
c_bass = (N("C2", 2, 70) + N("G2", 2, 65))
g_bass = (N("G1", 2, 70) + N("D2", 2, 65))
bass = c_bass.repeat(6) + g_bass + c_bass

score = Score(
    title="Two Tigers",
    tracks=(
        Track(music=melody, instrument="Piano", name="Melody"),
        Track(music=chords, instrument="Piano", name="Chords"),
        Track(music=bass, instrument="Piano", name="Bass"),
    ),
    tempo_map=TempoMap(tempo=((F(0), 100),)),
)

if __name__ == "__main__":
    name = 'two_tigers'
    muse_to_midi(score, f"{name}.mid")
    subprocess.run(
        [
            "fluidsynth", "-ni", "-F", f"{name}.wav", "-r", "44100",
            "/Users/luckyfish/Documents/music/GeneralUser-GS-main/GeneralUser-GS.sf2",
            f"{name}.mid",
        ],
        check=True,
    )
