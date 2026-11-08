from fractions import Fraction as F
from xml.etree import ElementTree as ET

import pytest

from sonqelra.backends import sonqelra_to_musicxml
from sonqelra.core import N, Rest, Score, Track, TempoMap, MeterMap, TimeSignature


def test_musicxml_preserves_parts_timing_spelling_and_ties(tmp_path):
    score = Score(
        (Track((Rest(F(3)) + N("Db4", 2)) | N("G4", F(1, 3)) | N("E4", 1), "Piano", "Keys"),
         Track(N("C5", 1), "Flute", "Flute")),
        "标题", TempoMap(((F(0), 120), (F(1, 3), 90))),
        MeterMap(((F(0), TimeSignature(4, 4)), (F(4), TimeSignature(3, 4)))),
    )
    path = tmp_path / "score.musicxml"
    sonqelra_to_musicxml(score, path)
    root = ET.parse(path).getroot()
    assert root.findtext("work/work-title") == "标题"
    assert len(root.findall("part")) == 2
    first, second = root.findall("part/measure")[:2]
    assert first.findtext("attributes/divisions") == "3"
    assert first.findtext("direction[offset]/offset") == "1"
    assert first.find("backup") is not None
    assert next(n for n in first.findall("note") if n.findtext("pitch/step") == "D").findtext("pitch/alter") == "-1"
    assert first.find("note[tie]/tie").attrib["type"] == "start"
    assert second.find("note[tie]/tie").attrib["type"] == "stop"
    assert second.findtext("attributes/time/beats") == "3"
    assert first.findtext("note[time-modification]/time-modification/actual-notes") == "3"


def test_meter_change_must_be_at_measure_boundary(tmp_path):
    score = Score((Track(N("C4", 4), "Piano", "Piano"),), "x",
                  meter_map=MeterMap(((F(0), TimeSignature(4, 4)), (F(2), TimeSignature(3, 4)))))
    with pytest.raises(ValueError, match="measure boundaries"):
        sonqelra_to_musicxml(score, tmp_path / "x.musicxml")
