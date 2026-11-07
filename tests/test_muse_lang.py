from fractions import Fraction
from pathlib import Path
import runpy
import pytest
from mido import MidiFile
from muse_lang import compile_source, execute_exports, SemanticError, ParseError, ExportError

ROOT = Path(__file__).resolve().parents[1]

def test_example_matches_python_and_exports(tmp_path):
    source = (ROOT / 'examples/asdf.muse').read_text(encoding='utf-8')
    result = compile_source(source, filename='asdf.muse')
    assert list(tmp_path.iterdir()) == []
    actual = result.scores[0].score
    expected = runpy.run_path(str(ROOT / 'examples/asdf.py'))['score']
    assert actual.title == expected.title
    assert actual.tempo_map == expected.tempo_map
    assert actual.meter_map == expected.meter_map
    assert (result.scores[0].key.root, result.scores[0].key.mode) == ('E', 'minor')
    for a, b in zip(actual.tracks, expected.tracks, strict=True):
        assert (a.name, a.instrument, a.is_percussion, a.music.duration) == (b.name, b.instrument, b.is_percussion, b.music.duration)
        def events(track):
            return sorted((e.start, e.duration, e.pitch.midi, e.velocity) for e in track.music.iter_events())
        assert events(a) == events(b)
    execute_exports(result, base_dir=tmp_path)
    assert len(MidiFile(tmp_path / 'electric_road.mid').tracks) == 4

def test_arrays_pipeline_and_meter():
    source = '''score "Example" {
 meter 4/4
 fn build(root: Pitch) -> Music {
  let pattern = [root, root + 4st, root + 7st,]
  return chord(pattern, velocity: 100, duration: 1/2) + sequence(pattern, duration: 1/8)
 }
 let part = build(C4)
   |> repeat(2)
 track piano {
  instrument "Piano"
  play part
 }
}'''
    result = compile_source(source)
    score = result.scores[0].score
    meter = score.meter_map.meter[0][1]
    assert (meter.numerator, meter.denominator) == (4, 4)
    music = score.tracks[0].music
    assert music.duration == 7
    events = list(music.iter_events())
    assert [e.start for e in events[:6]] == [0, 0, 0, 2, Fraction(5, 2), 3]
    assert [e.pitch.midi for e in events[:3]] == [60, 64, 67]

@pytest.mark.parametrize('body', [
 'let x = chord([C4], duration: 1/4, duration: 1/8)',
 'let x = chord([C4], 1/4)',
 'let x = chord([C4], duration: 1/4, bogus: 1)',
 'let x = chord(duration: 1/4, [C4])',
 'let x = []',
 'let x = [C4, 2]',
 'fn bad(x: Pitch) -> Music {\n return missing(x)\n }',
 'fn bad(x: Pitch) -> Music {\n return x\n }',
])
def test_semantic_errors(body):
    source = f'score "x" {{\n{body}\n track t {{\n instrument "Piano"\n play rest(1)\n }}\n}}'
    with pytest.raises(SemanticError): compile_source(source, filename='bad.muse')

def test_duplicate_field_location():
    source = 'score "x" {\n tempo 100\n tempo 120\n}'
    with pytest.raises(SemanticError) as exc: compile_source(source, filename='bad.muse')
    assert (exc.value.span.filename, exc.value.span.start.line, exc.value.span.start.column) == ('bad.muse', 3, 2)

def test_export_duplicate_preflight(tmp_path):
    source = '''score "x" {
 track t {
  instrument "Piano"
  play note(C4, 1)
 }
 export midi "x.mid"
 export midi "./x.mid"
}'''
    with pytest.raises(ExportError): execute_exports(compile_source(source), base_dir=tmp_path)
    assert list(tmp_path.iterdir()) == []

def test_backend_error_is_export_error(tmp_path):
    source = '''score "x" {
 track t {
  instrument "Piano"
  play note(C4, 1, 0)
 }
 export midi "x.mid"
}'''
    result=compile_source(source)
    with pytest.raises(ExportError) as exc: execute_exports(result, base_dir=tmp_path)
    assert exc.value.span.start.line == 6

def test_melody_rest_velocity_rejected():
    with pytest.raises(SemanticError): compile_source('score "x" {\n melody m {\n rest:1/4@5\n }\n}')

def test_no_call_trailing_comma():
    with pytest.raises(ParseError): compile_source('score "x" {\n let x = note(C4, 1,)\n}')


def test_musicxml_and_midi_exports_from_language(tmp_path):
    from xml.etree import ElementTree
    source = '''score "Example" {
 track piano {
  instrument "Piano"
  play note(C4, 1)
 }
 export midi "out.mid"
 export musicxml "out.musicxml"
}'''
    result = compile_source(source)
    assert [plan.format for plan in result.exports] == ['midi', 'musicxml']
    assert list(tmp_path.iterdir()) == []
    execute_exports(result, base_dir=tmp_path)
    assert len(MidiFile(tmp_path / 'out.mid').tracks) == 1
    root = ElementTree.parse(tmp_path / 'out.musicxml').getroot()
    assert root.findtext('work/work-title') == 'Example'
    assert root.findtext('part/measure/note/pitch/step') == 'C'


def test_custom_exporter_and_unknown_format_preflight(tmp_path):
    source = '''score "Example" {
 track piano {
  instrument "Piano"
  play note(C4, 1)
 }
 export midi "out.mid"
 export custom "out.txt"
}'''
    result = compile_source(source, filename='example.muse')
    with pytest.raises(ExportError, match='Unknown export format: custom') as exc:
        execute_exports(result, base_dir=tmp_path)
    assert exc.value.span.start.line == 7
    assert list(tmp_path.iterdir()) == []
    def custom(score, path):
        Path(path).write_text(score.title, encoding='utf-8')
    execute_exports(result, base_dir=tmp_path, exporters={'custom': custom})
    assert (tmp_path / 'out.txt').read_text(encoding='utf-8') == 'Example'
    assert (tmp_path / 'out.mid').exists()


def test_musicxml_cli(tmp_path):
    import subprocess
    import sys
    source = tmp_path / 'song.muse'
    source.write_text('''score "CLI" {
 track piano {
  instrument "Piano"
  play note(C4, 1)
 }
 export musicxml "out.musicxml"
}''', encoding='utf-8')
    subprocess.run([sys.executable, '-m', 'muse_lang', str(source)], check=True, cwd=ROOT)
    assert (tmp_path / 'out.musicxml').exists()
