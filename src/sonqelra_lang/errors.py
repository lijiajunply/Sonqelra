"""Source-located language errors."""
class SonqelraError(Exception):
    def __init__(self, message, span, *, cause=None):
        self.message, self.span, self.cause = message, span, cause
        super().__init__(f"{span.filename}:{span.start.line}:{span.start.column}: {message}")

class LexError(SonqelraError): pass
class ParseError(SonqelraError): pass
class SemanticError(SonqelraError): pass
class ExportError(SonqelraError): pass
