from unittest import mock

from vidsmith.utils.environment import js_runtimes_option


def test_js_runtimes_option_with_override():
    opt = js_runtimes_option("/custom/node")
    assert opt == {"node": {"binary": "/custom/node"}}


@mock.patch("vidsmith.utils.environment.available_js_runtime")
def test_js_runtimes_option_default_deno(mock_avail):
    mock_avail.return_value = "deno"
    opt = js_runtimes_option()
    assert opt == {}


@mock.patch("vidsmith.utils.environment.available_js_runtime")
def test_js_runtimes_option_node(mock_avail):
    mock_avail.return_value = "node"
    opt = js_runtimes_option()
    assert opt == {"node": {}}
