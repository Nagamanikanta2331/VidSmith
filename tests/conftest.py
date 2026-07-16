from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def mock_shutil_which():
    with mock.patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/bin/ffprobe"
        yield mock_which
