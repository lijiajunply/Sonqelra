"""一首简短的 E 小调摇滚练习曲，导出 MIDI 并用 FluidSynth 渲染。"""

import subprocess
from fractions import Fraction as F

from muse.backends.mido import muse_to_midi
from muse.core import N, Rest, Score, TempoMap, Track

# 4/4 拍，16 小节；每个乐句或节奏型均为一小节。
half = F(1, 2)

# 失真吉他主奏：E 小调的重复动机和结尾。
riff_e = (
    N("E4", half, 110) + N("E4", half, 98) + N("G4", 1, 105)
    + N("A4", half, 108) + N("B4", half, 115) + N("G4", 1, 100)
)
riff_g = (
    N("G4", half, 108) + N("G4", half, 96) + N("B4", 1, 105)
    + N("D5", half, 110) + N("B4", half, 100) + N("A4", 1, 98)
)
riff_a = (
    N("A4", half, 110) + N("A4", half, 98) + N("C5", 1, 105)
    + N("B4", half, 100) + N("A4", half, 100) + N("G4", 1, 98)
)
ending = N("B4", half, 110) + N("A4", half, 100) + N("G4", 1, 105) + N("E4", 2, 118)
melody = (riff_e + riff_g + riff_a + riff_e).repeat(3) + riff_e + riff_g + riff_a + ending


def power_chord(root: str, fifth: str):
    """八分音符动力和弦，重复一小节。"""
    return (N(root, half, 95) | N(fifth, half, 90)).repeat(8)


e5 = power_chord("E3", "B3")
g5 = power_chord("G3", "D4")
a5 = power_chord("A3", "E4")
guitar = (e5 + g5 + a5 + e5).repeat(4)

# 电贝斯用根音与五度推动节奏。
def bass_bar(root: str, fifth: str):
    return (
        N(root, 1, 100) + N(root, half, 88) + N(fifth, half, 92)
        + N(root, 1, 98) + N(fifth, half, 90) + N(root, half, 95)
    )


bass = (bass_bar("E2", "B2") + bass_bar("G2", "D3")
        + bass_bar("A2", "E3") + bass_bar("E2", "B2")).repeat(4)

# GM 鼓组：C2 底鼓、D2 军鼓、F#2 闭合踩镲；军鼓落在二、四拍。
kick = N("C2", half, 115) + Rest(F(3, 2)) + N("C2", half, 105) + Rest(F(3, 2))
snare = Rest(1) + N("D2", half, 112) + Rest(F(3, 2)) + N("D2", half, 115) + Rest(half)
hihat = (N("F#2", half, 75) + N("F#2", half, 62)).repeat(4)
drums = (kick | snare | hihat).repeat(16)

score = Score(
    title="Electric Road",
    tracks=(
        Track(music=melody, instrument="Overdriven Guitar", name="Lead Guitar"),
        Track(music=guitar, instrument="Distortion Guitar", name="Rhythm Guitar"),
        Track(music=bass, instrument="Electric Bass (pick)", name="Bass"),
        Track(music=drums, instrument="Piano", name="Drums", is_percussion=True),
    ),
    tempo_map=TempoMap(tempo=((F(0), 140),)),
)

if __name__ == "__main__":
    name = "electric_road"
    muse_to_midi(score, f"{name}.mid")
    subprocess.run(
        [
            "fluidsynth", "-ni", "-F", f"{name}.wav", "-r", "44100",
            "/Users/luckyfish/Documents/music/GeneralUser-GS-main/GeneralUser-GS.sf2",
            f"{name}.mid",
        ],
        check=True,
    )
