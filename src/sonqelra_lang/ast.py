"""Immutable syntax tree and source locations for Sonqelra."""
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class Position:
    line: int
    column: int

@dataclass(frozen=True)
class Span:
    filename: str
    start: Position
    end: Position

@dataclass(frozen=True)
class Node:
    kind: str
    span: Span
    value: Any = None
    children: tuple = ()

@dataclass(frozen=True)
class MeterLiteral(Node):
    pass

@dataclass(frozen=True)
class NoteLiteral(Node):
    pass
