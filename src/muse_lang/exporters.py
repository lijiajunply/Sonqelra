"""Built-in score exporters used by the language runtime."""
from collections.abc import Callable
from types import MappingProxyType

from muse.backends import muse_to_midi, muse_to_musicxml
from muse.core import Score

Exporter = Callable[[Score, str], None]

# The parser and executor do not need to change when adding a format here.
DEFAULT_EXPORTERS = MappingProxyType({
    'midi': muse_to_midi,
    'musicxml': muse_to_musicxml,
})
