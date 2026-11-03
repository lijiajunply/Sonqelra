from mido import MidiFile, MidiTrack, MetaMessage, Message, bpm2tempo
from muse.core.work import Score

def midi_to_muse(file: str) -> Score:
    pass

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
