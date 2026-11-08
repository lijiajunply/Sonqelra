"""Import the timed notes of a MusicXML partwise score."""
from fractions import Fraction
from pathlib import Path
from xml.etree import ElementTree as ET

from sonqelra.core import Note, Parallel, Pitch, Rest, Sequence
from sonqelra.core.work import Score, Track, TempoMap, MeterMap, TimeSignature, _GM_INSTRUMENTS


def musicxml_to_sonqelra(file: str | Path) -> Score:
    root = ET.parse(file).getroot()
    # MusicXML documents may use a default namespace.
    for element in root.iter():
        element.tag = element.tag.split('}')[-1]
    if root.tag != 'score-partwise':
        raise ValueError('Only MusicXML score-partwise is supported')
    definitions = {p.get('id'): p for p in root.findall('./part-list/score-part')}
    tracks = []
    tempos = {Fraction(0): 120}
    meters = {Fraction(0): TimeSignature(4, 4)}
    for part in root.findall('part'):
        definition = definitions.get(part.get('id'))
        if definition is None:
            raise ValueError('MusicXML part has no score-part definition')
        name = definition.findtext('part-name') or part.get('id') or 'Track'
        program = int(definition.findtext('./midi-instrument/midi-program', '1'))
        channel = int(definition.findtext('./midi-instrument/midi-channel', '1'))
        if not 1 <= program <= 128 or not 1 <= channel <= 16:
            raise ValueError('Invalid MusicXML MIDI program or channel')
        divisions = None
        position = Fraction(0)
        notes = []
        ties = {}
        for measure in part.findall('measure'):
            start = position
            cursor = start
            end = start
            last_start = None
            for item in measure:
                if item.tag == 'attributes':
                    value = item.findtext('divisions')
                    if value is not None:
                        divisions = int(value)
                        if divisions <= 0: raise ValueError('MusicXML divisions must be positive')
                    time = item.find('time')
                    if time is not None:
                        meters[cursor] = TimeSignature(int(time.findtext('beats')), int(time.findtext('beat-type')))
                elif item.tag == 'direction':
                    sound = item.find('sound')
                    if sound is not None and sound.get('tempo') is not None:
                        offset = int(item.findtext('offset', '0'))
                        if offset and not divisions: raise ValueError('MusicXML divisions are required')
                        tempos[cursor + (Fraction(offset, divisions) if offset else 0)] = Fraction(sound.get('tempo'))
                elif item.tag in ('backup', 'forward', 'note'):
                    if item.tag == 'note' and item.find('grace') is not None:
                        raise ValueError('MusicXML grace notes are not supported')
                    if not divisions: raise ValueError('MusicXML divisions are required before durations')
                    duration = Fraction(int(item.findtext('duration')), divisions)
                    if duration <= 0: raise ValueError('MusicXML duration must be positive')
                    if item.tag == 'backup':
                        cursor -= duration
                        if cursor < start: raise ValueError('MusicXML backup precedes measure')
                    elif item.tag == 'forward':
                        cursor += duration
                        end = max(end, cursor)
                    else:
                        chord = item.find('chord') is not None
                        if chord and last_start is None: raise ValueError('MusicXML chord has no preceding note')
                        note_start = last_start if chord else cursor
                        if not chord:
                            last_start = cursor
                            cursor += duration
                        end = max(end, note_start + duration, cursor)
                        pitch_node = item.find('pitch')
                        if pitch_node is not None:
                            alter = Fraction(pitch_node.findtext('alter', '0'))
                            if alter.denominator != 1: raise ValueError('Microtonal MusicXML pitches are not supported')
                            pitch = Pitch(pitch_node.findtext('step'), int(alter), int(pitch_node.findtext('octave')))
                            pitch.midi
                            voice = item.findtext('voice', '1')
                            key = (voice, pitch.step, pitch.accidental, pitch.octave)
                            types = {tie.get('type') for tie in item.findall('tie')}
                            if 'stop' in types:
                                if key not in ties: raise ValueError('Unmatched MusicXML tie stop')
                                old_start, old_duration = ties.pop(key)
                                if old_start + old_duration != note_start: raise ValueError('Non-contiguous MusicXML tie')
                                note_start, duration = old_start, old_duration + duration
                            if 'start' in types: ties[key] = (note_start, duration)
                            else: notes.append(Sequence((Rest(note_start), Note(pitch, duration, 80))))
                        elif item.find('rest') is None:
                            raise ValueError('Unsupported MusicXML note without pitch or rest')
            position = end
        if ties: raise ValueError('Unclosed MusicXML tie')
        tracks.append(Track(Parallel((*notes, Rest(position))), _GM_INSTRUMENTS[program - 1], name, channel == 10))
    if not tracks: raise ValueError('MusicXML score contains no parts')
    return Score(tuple(tracks), root.findtext('./work/work-title') or root.findtext('movement-title') or Path(file).stem,
                 TempoMap(tuple(sorted(tempos.items()))), MeterMap(tuple(sorted(meters.items()))))
