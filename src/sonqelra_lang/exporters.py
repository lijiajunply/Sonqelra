"""Built-in score exporters used by the language runtime."""
from collections.abc import Callable
from types import MappingProxyType

from sonqelra.backends import sonqelra_to_midi, sonqelra_to_musicxml
from sonqelra.core import Score

Exporter = Callable[[Score, str], None]

# The parser and executor do not need to change when adding a format here.
DEFAULT_EXPORTERS = MappingProxyType({
    'midi': sonqelra_to_midi,
    'musicxml': sonqelra_to_musicxml,
})
