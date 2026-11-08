from fractions import Fraction as F

import pytest

from sonqelra.backends import musicxml_to_sonqelra, sonqelra_to_midi, sonqelra_to_musicxml
from sonqelra.core import N, Rest, Score, Track, TempoMap, MeterMap, TimeSignature
from sonqelra_lang import compile_source, SemanticError


def test_musicxml_roundtrip_ties_voices_and_metadata(tmp_path):
    original = Score((Track((Rest(F(3)) + N('Db4', 2)) | N('G4', F(1, 3)), 'Flute', 'Melody'),),
                     'Example', TempoMap(((F(0), 120), (F(1, 3), 90))),
                     MeterMap(((F(0), TimeSignature(4, 4)), (F(4), TimeSignature(3, 4)))))
    path = tmp_path / 'piece.musicxml'
    sonqelra_to_musicxml(original, path)
    imported = musicxml_to_sonqelra(path)
    assert imported.title == 'Example'
    assert imported.tracks[0].instrument == 'Flute'
    assert sorted((e.start, e.duration, e.pitch.midi) for e in imported.tracks[0].music.iter_events()) == sorted(
        (e.start, e.duration, e.pitch.midi) for e in original.tracks[0].music.iter_events())
    assert imported.tempo_map == original.tempo_map
    assert imported.meter_map == original.meter_map


def test_modules_and_scores_import_only_on_reference(tmp_path):
    score = Score((Track(N('C4', 1), 'Piano', 'Original'),), 'source')
    sonqelra_to_midi(score, str(tmp_path / 'a.mid'))
    sonqelra_to_musicxml(score, tmp_path / 'a.musicxml')
    folder = tmp_path / 'sub'
    folder.mkdir()
    (folder / 'child.sonqelra').write_text('''import midi "../a.mid"
score "child" {
 let duration = 2
 fn make(p: Pitch) -> Music {
 return note(p, duration)
 }
 track "inner" {
 instrument "Piano"
 play module("a")."a".track."Original"
 }
 export midi "unwanted.mid"
}''', encoding='utf-8')
    source = '''import sonqelra "sub/child.sonqelra"
import musicxml "a.musicxml"
score "first" {
 fn make(p: Pitch) -> Music {
 return note(p, 1)
 }
 track "local" {
 instrument "Piano"
 play note(C4, 1)
 }
}
score "combined" {
 import score "first"
 fn use(p: Pitch) -> Music {
 return module('child')."child".fn.make(p)
 }
 track "new" {
  instrument "Piano"
  play use(D4) + score("first").fn.make(E4) + module("a")."source".track."Original" + score("first").track."local"
 }
 export midi "result.mid"
}'''
    result = compile_source(source, filename=str(tmp_path / 'main.sonqelra'))
    assert len(result.scores[1].score.tracks) == 1
    events = list(result.scores[1].score.tracks[0].music.iter_events())
    assert [(e.pitch.midi, e.duration) for e in events] == [(62, 2), (64, 1), (60, 1), (60, 1)]
    assert [e.path for e in result.exports] == ['result.mid']
    assert not (folder / 'unwanted.mid').exists()


def test_import_errors_have_source_location_and_cycles_are_rejected(tmp_path):
    path = tmp_path / 'loop.sonqelra'
    source = 'import sonqelra "loop.sonqelra"'
    path.write_text(source)
    with pytest.raises(SemanticError, match='Circular import') as error:
        compile_source(source, filename=str(path))
    assert error.value.span.start.line == 1
    with pytest.raises(SemanticError, match='Relative import requires'):
        compile_source('import midi "a.mid"')
    with pytest.raises(SemanticError, match='import failed'):
        compile_source('import midi "missing.mid"', filename=str(path))
    with pytest.raises(SemanticError, match='Unknown or ambiguous score'):
        compile_source('score "x" {\n import score "missing"\n}')
    with pytest.raises(SemanticError, match='Unknown module'):
        compile_source('score "x" {\n let x = module("missing")."x".track."y"\n}')
