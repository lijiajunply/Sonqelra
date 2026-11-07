"""Source-located language errors."""
class MuseError(Exception):
    def __init__(self, message, span, *, cause=None):
        self.message, self.span, self.cause = message, span, cause
        super().__init__(f"{span.filename}:{span.start.line}:{span.start.column}: {message}")

class LexError(MuseError): pass
class ParseError(MuseError): pass
class SemanticError(MuseError): pass
class ExportError(MuseError): pass
