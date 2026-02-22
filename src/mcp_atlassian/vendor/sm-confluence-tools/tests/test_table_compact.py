"""Test compact table output: short separator and no cell padding."""

from unittest.mock import patch

import pytest

from confluence_markdown_exporter import confluence as cmexp
from sm_confluence_tools.client import SmConfluenceTools

tools = SmConfluenceTools()

_dummy_space = cmexp.Space(key="X", name="X", description="", homepage=0)


@pytest.fixture
def mock_attachments():
    with patch("sm_confluence_tools.attachment._Attachment.from_page_id") as m:
        m.return_value = []
        yield m


@pytest.fixture
def mock_space():
    with patch.object(cmexp.Space, "from_key", return_value=_dummy_space):
        yield


def test_table_compact_separator_and_no_padding(
    mock_attachments: None, mock_space: None
) -> None:
    html = (
        "<table><tr><th>A</th><th>B</th></tr>"
        "<tr><td>foo</td><td>bar</td></tr></table>"
    )
    page_data = {
        "id": 1,
        "title": "T",
        "_expandable": {"space": "space/X"},
        "body": {
            "view": {"value": html},
            "export_view": {"value": html},
            "editor": {"value": ""},
        },
        "ancestors": [{"id": 0}],
        "metadata": {"labels": {"results": []}},
    }
    page = tools.Page.from_json(page_data)
    md = page.markdown
    assert "| --- | --- |" in md
    assert "| A | B |" in md
    assert "| foo | bar |" in md
    for line in md.splitlines():
        if line.strip().startswith("|") and "---" in line:
            assert line == "| --- | --- |", "separator must be short, no column-width alignment"
