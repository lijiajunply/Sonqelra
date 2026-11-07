from collections import defaultdict, deque
from fractions import Fraction
from pathlib import Path

from mido import MidiFile, MidiTrack, MetaMessage, Message, bpm2tempo, tempo2bpm
from muse.core import Note, Parallel, Pitch, Rest, Sequence
from muse.core.work import MeterMap, Score, TempoMap, TimeSignature, Track, _GM_INSTRUMENTS

def midi_to_muse(file: str) -> Score:
    """导入标准 MIDI 文件，时间以四分音符为单位。

    同一轨道中的不同通道或乐器会拆成多条 Muse 轨道。控制器、踏板、
    弯音和打击乐音色等目前无法在 Score 中表示，因此不予转换。
    不支持异步的 type 2 文件和 SMPTE 时间格式。
    """
    midi_file = MidiFile(file)
    if midi_file.type == 2:
        raise ValueError("MIDI type 2 contains independent timelines")
    if midi_file.ticks_per_beat <= 0:
        raise ValueError("SMPTE time division is not supported")

    ticks_per_beat = midi_file.ticks_per_beat
    tempos = {0: 120}
    meters = {0: TimeSignature(4, 4)}
    metadata = []
    tracks = []

    for index, track in enumerate(midi_file.tracks):
        tick = 0
        programs = defaultdict(int)
        active = defaultdict(deque)
        parts = defaultdict(list)
        for msg in track:
            tick += msg.time
            if msg.type in ("set_tempo", "time_signature"):
                metadata.append((tick, index, msg))
            elif msg.type == "program_change":
                programs[msg.channel] = msg.program
            elif msg.type == "note_on" and msg.velocity > 0:
                active[(msg.channel, msg.note)].append(
                    (tick, msg.velocity, programs[msg.channel])
                )
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                key = (msg.channel, msg.note)
                if not active[key]:
                    raise ValueError(f"Unmatched note-off in MIDI track {index}: {key}")
                start, velocity, program = active[key].popleft()
                if tick <= start:
                    raise ValueError(f"Non-positive note duration in MIDI track {index}: {key}")
                parts[(msg.channel, program)].append(
                    Sequence((
                        Rest(Fraction(start, ticks_per_beat)),
                        Note(Pitch.from_midi(msg.note), Fraction(tick - start, ticks_per_beat), velocity),
                    ))
                )
        if any(active.values()):
            raise ValueError(f"Unclosed notes in MIDI track {index}")

        for (channel, program), notes in parts.items():
            name = track.name or f"Track {index + 1}"
            if len(parts) > 1:
                name += f" (channel {channel + 1}, program {program + 1})"
            # Retain silence through the end-of-track marker.
            music = Parallel((*notes, Rest(Fraction(tick, ticks_per_beat))))
            tracks.append(Track(music=music, instrument=_GM_INSTRUMENTS[program], name=name))

    # For simultaneous changes, later events in track order take precedence.
    for tick, _, msg in sorted(metadata, key=lambda item: (item[0], item[1])):
        if msg.type == "set_tempo":
            tempos[tick] = round(tempo2bpm(msg.tempo))
        else:
            meters[tick] = TimeSignature(msg.numerator, msg.denominator)

    if not tracks:
        tracks.append(Track(music=Rest(Fraction(0)), instrument="Piano", name="Track 1"))
    return Score(
        tracks=tuple(tracks),
        title=Path(file).stem,
        tempo_map=TempoMap(tuple((Fraction(t, ticks_per_beat), bpm) for t, bpm in sorted(tempos.items()))),
        meter_map=MeterMap(tuple((Fraction(t, ticks_per_beat), meter) for t, meter in sorted(meters.items()))),
    )

def muse_to_midi(score: Score, file: str) -> None:
    mid = MidiFile()
    for track in score.tracks:
        midi_track = MidiTrack()
        mid.tracks.append(midi_track)

        # Collect absolute timestamps, then convert them to MIDI delta times.
        events = [(0, MetaMessage("track_name", name=track.name))]

        # Add tempo and time signature
        for tempo_change in score.tempo_map.tempo:
            events.append(
                (int(tempo_change[0] * mid.ticks_per_beat), MetaMessage(
                    "set_tempo",
                    tempo=bpm2tempo(tempo_change[1]),
                ))
            )

        for meter_change in score.meter_map.meter:
            events.append(
                (int(meter_change[0] * mid.ticks_per_beat), MetaMessage(
                    "time_signature",
                    numerator=meter_change[1].numerator,
                    denominator=meter_change[1].denominator,
                ))
            )

        # Add notes
        for note in track.music.iter_events():
            events.append(
                (int(note.start * mid.ticks_per_beat), Message(
                    "note_on",
                    note=note.pitch.midi,
                    velocity=note.velocity,
                ))
            )
            events.append(
                (int((note.start + note.duration) * mid.ticks_per_beat), Message(
                    "note_off",
                    note=note.pitch.midi,
                    velocity=0,
                ))
            )
        # Release notes before starting new ones at the same timestamp.
        events.sort(key=lambda event: (event[0], event[1].type == "note_on"))
        previous_tick = 0
        for tick, message in events:
            midi_track.append(message.copy(time=tick - previous_tick))
            previous_tick = tick
    mid.save(file)
