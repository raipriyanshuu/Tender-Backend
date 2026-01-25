import tempfile

import pytest

from workers.core.errors import PermanentError
from workers.processing.parsers import parse_file


def test_parse_file_unsupported_type():
    with tempfile.NamedTemporaryFile(suffix=".txt") as handle:
        with pytest.raises(PermanentError):
            parse_file(handle.name)
