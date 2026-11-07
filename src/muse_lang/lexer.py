"""Tokenize Muse source while retaining exact source locations."""
from dataclasses import dataclass
import re
from .ast import Position, Span
from .errors import LexError

@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    span: Span

def lex(source, filename='<string>'):
    tokens = []
    i = 0
    line = col = 1
    depth = 0
    def emit(kind, value, start, end):
        tokens.append(Token(kind, value, Span(filename, start, end)))
    while i < len(source):
        start = Position(line, col)
        c = source[i]
        if c in ' \t\r':
            i += 1; col += 1; continue
        if c == '\n':
            i += 1; line += 1; col = 1
            if not depth: emit('NL', '\n', start, Position(line, col))
            continue
        if source.startswith('//', i):
            while i < len(source) and source[i] != '\n': i += 1; col += 1
            continue
        if c == '"':
            i += 1; col += 1; value = ''
            while i < len(source) and source[i] != '"':
                ch = source[i]
                if ch == '\n': raise LexError('Unterminated string', Span(filename, start, Position(line, col)))
                if ch == '\\':
                    i += 1; col += 1
                    if i >= len(source) or source[i] not in '\\"nrt': raise LexError('Invalid string escape', Span(filename, start, Position(line, col)))
                    ch = {'n':'\n','r':'\r','t':'\t'}.get(source[i], source[i])
                value += ch; i += 1; col += 1
            if i == len(source): raise LexError('Unterminated string', Span(filename, start, Position(line, col)))
            i += 1; col += 1; emit('STRING', value, start, Position(line, col)); continue
        m = re.match(r'[A-Za-z_][A-Za-z_0-9#]*(?:-\d+)?|-?\d+st|-?\d+', source[i:])
        if m:
            word = m.group(); i += len(word); col += len(word)
            if re.fullmatch(r'[A-G](?:#+|b+)?-?\d+', word): kind = 'PITCH'
            elif re.fullmatch(r'-?\d+st', word): kind = 'INTERVAL'
            elif re.fullmatch(r'-?\d+', word): kind = 'INT'
            elif re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', word): kind = 'IDENT'
            elif re.fullmatch(r'[A-G](?:#+|b+)', word): kind = 'IDENT'
            else: raise LexError(f'Invalid token {word!r}', Span(filename, start, Position(line, col)))
            emit(kind, word, start, Position(line, col)); continue
        # Positive intervals start with digits and require longest match.
        if source.startswith('|>', i) or source.startswith('->', i):
            value = source[i:i+2]; i += 2; col += 2; emit(value, value, start, Position(line, col)); continue
        if c in '{}()[],:@=+|/<>':
            i += 1; col += 1
            if c in '([': depth += 1
            elif c in ')]': depth = max(0, depth - 1)
            emit(c, c, start, Position(line, col)); continue
        raise LexError(f'Unexpected character {c!r}', Span(filename, start, Position(line, col+1)))
    pos = Position(line, col); emit('EOF', '', pos, pos)
    return tuple(tokens)
