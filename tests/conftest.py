import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture(autouse=True)
def mock_shutil_which():
    with mock.patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/ffprobe"
        yield mock_which
