"""Export Sonqelra scores as MusicXML 4.0 partwise documents."""

from fractions import Fraction
from math import lcm
from pathlib import Path
from xml.etree import ElementTree as ET

from sonqelra.core import Event, Score


def _child(parent, name, value=None, **attributes):
    element = ET.SubElement(parent, name, attributes)
    if value is not None:
        element.text = str(value)
    return element


def sonqelra_to_musicxml(score: Score, file: str | Path) -> None:
    """Write a MusicXML score, preserving exact musical timing.

    Meter changes must fall at bar boundaries. MIDI controls and pitch bends
    are not represented; percussion is written as pitched notes.
    """
    events = [list(track.music.iter_events()) for track in score.tracks]
    end = max((Fraction(track.music.duration) for track in score.tracks), default=Fraction(0))
    metadata_end = max(score.tempo_map.tempo[-1][0], score.meter_map.meter[-1][0])
    meters = score.meter_map.meter
    bars = []
    position = Fraction(0)
    meter_index = 0
    while not bars or position < end or position <= metadata_end:
        if meter_index + 1 < len(meters) and meters[meter_index + 1][0] == position:
            meter_index += 1
        signature = meters[meter_index][1]
        bar_end = position + Fraction(4 * signature.numerator, signature.denominator)
        if meter_index + 1 < len(meters) and meters[meter_index + 1][0] < bar_end:
            raise ValueError("MusicXML meter changes must fall on measure boundaries")
        bars.append((position, bar_end, signature, meter_index))
        position = bar_end

    times = [end, *(p for p, _ in score.tempo_map.tempo), *(p for p, _ in meters)]
    for start, stop, _, _ in bars:
        times.extend((start, stop))
    for track_events in events:
        for event in track_events:
            if event.start < 0 or event.start + event.duration > end:
                raise ValueError("Event lies outside the score duration")
            times.extend((Fraction(event.start), Fraction(event.duration)))
    divisions = lcm(*(Fraction(t).denominator for t in times))

    root = ET.Element("score-partwise", version="4.0")
    _child(_child(root, "work"), "work-title", score.title)
    part_list = _child(root, "part-list")
    for index, track in enumerate(score.tracks, 1):
        part_info = _child(part_list, "score-part", id=f"P{index}")
        _child(part_info, "part-name", track.name)
        instrument = _child(part_info, "score-instrument", id=f"I{index}")
        _child(instrument, "instrument-name", track.instrument)
        try:
            program = track.instrument_to_midi_program()
        except ValueError:
            pass
        else:
            midi = _child(part_info, "midi-instrument", id=f"I{index}")
            _child(midi, "midi-program", program + 1)

    for index, track_events in enumerate(events, 1):
        part = _child(root, "part", id=f"P{index}")
        voices: list[list[Event]] = []
        ends: list[Fraction] = []
        for event in sorted(track_events, key=lambda e: (e.start, e.pitch.midi, e.duration)):
            voice = next((i for i, last in enumerate(ends) if last <= event.start), len(ends))
            if voice == len(ends):
                voices.append([])
                ends.append(Fraction(0))
            voices[voice].append(event)
            ends[voice] = event.start + event.duration
        if not voices:
            voices.append([])
        for number, (start, stop, signature, meter_index) in enumerate(bars, 1):
            measure = _child(part, "measure", number=str(number))
            if number == 1 or meters[meter_index][0] == start:
                attributes = _child(measure, "attributes")
                if number == 1:
                    _child(attributes, "divisions", divisions)
                time = _child(attributes, "time")
                _child(time, "beats", signature.numerator)
                _child(time, "beat-type", signature.denominator)
                if number == 1:
                    clef = _child(attributes, "clef")
                    _child(clef, "sign", "G")
                    _child(clef, "line", 2)
            for tempo_start, bpm in score.tempo_map.tempo:
                if start <= tempo_start < stop:
                    direction = _child(measure, "direction")
                    dtype = _child(direction, "direction-type")
                    metronome = _child(dtype, "metronome")
                    _child(metronome, "beat-unit", "quarter")
                    _child(metronome, "per-minute", format(float(bpm), ".15g"))
                    if tempo_start != start:
                        _child(direction, "offset", int((tempo_start - start) * divisions))
                    _child(direction, "sound", tempo=format(float(bpm), ".15g"))
            for voice_index, voice in enumerate(voices, 1):
                if voice_index > 1:
                    _child(_child(measure, "backup"), "duration", int((stop - start) * divisions))
                cursor = start
                for event in voice:
                    event_end = event.start + event.duration
                    if event.start >= stop or event_end <= start:
                        continue
                    onset, offset = max(start, event.start), min(stop, event_end)
                    if onset > cursor:
                        _write_note(measure, None, onset - cursor, divisions, voice_index)
                    _write_note(measure, event, offset - onset, divisions, voice_index,
                                event.start < onset, event_end > offset)
                    cursor = offset
                if cursor < stop:
                    _write_note(measure, None, stop - cursor, divisions, voice_index)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(file, encoding="utf-8", xml_declaration=True)


def _write_note(measure, event, duration, divisions, voice, tie_stop=False, tie_start=False):
    note = _child(measure, "note")
    if event is None:
        _child(note, "rest")
    else:
        pitch = _child(note, "pitch")
        _child(pitch, "step", event.pitch.step)
        if event.pitch.accidental:
            _child(pitch, "alter", event.pitch.accidental)
        _child(pitch, "octave", event.pitch.octave)
    _child(note, "duration", int(duration * divisions))
    if tie_stop:
        _child(note, "tie", type="stop")
    if tie_start:
        _child(note, "tie", type="start")
    _child(note, "voice", voice)
    types = [("maxima", 32), ("long", 16), ("breve", 8), ("whole", 4),
             ("half", 2), ("quarter", 1), ("eighth", Fraction(1, 2)),
             ("16th", Fraction(1, 4)), ("32nd", Fraction(1, 8)),
             ("64th", Fraction(1, 16)), ("128th", Fraction(1, 32)),
             ("256th", Fraction(1, 64)), ("512th", Fraction(1, 128)),
             ("1024th", Fraction(1, 256))]
    chosen = None
    for name, base in types:
        for dots, multiplier in ((0, 1), (1, Fraction(3, 2)), (2, Fraction(7, 4)), (3, Fraction(15, 8))):
            if duration == base * multiplier:
                chosen = (name, dots, None)
                break
        if chosen:
            break
    if chosen is None:
        name, base = min(types, key=lambda item: abs(float(duration / item[1]) - 1))
        ratio = Fraction(duration) / base
        chosen = (name, 0, ratio)
    _child(note, "type", chosen[0])
    for _ in range(chosen[1]):
        _child(note, "dot")
    if chosen[2] is not None:
        modification = _child(note, "time-modification")
        _child(modification, "actual-notes", chosen[2].denominator)
        _child(modification, "normal-notes", chosen[2].numerator)
    if tie_stop or tie_start:
        notations = _child(note, "notations")
        if tie_stop:
            _child(notations, "tied", type="stop")
        if tie_start:
            _child(notations, "tied", type="start")
