"""Tests for draw.io macro parsing and markdown formatting."""

from bs4 import BeautifulSoup

from sm_confluence_tools.drawio import content_to_markdown, parse_macro_data

# Drawio macro (body.view format with base64 JSON)
DRAWIO_MACRO_HTML = """<div style="display:block;" class="conf-macro output-block" data-macro-name="drawio">
    <div class="drawio-macro" id="drawio-macro-content-7ccfe852-ee3b-48a3-9c1b-fd9cae29783d"></div>
    <div id="drawio-macro-data-7ccfe852-ee3b-48a3-9c1b-fd9cae29783d" style="display:none">eyJleHRTcnZJbnRlZ1R5cGUiOiIiLCJnQ2xpZW50SWQiOiIiLCJjcmVhdG9yTmFtZSI6ItCa0LvQsNC00L7QsiDQktC40LrRgtC+0YAg0JLQsNGB0LjQu9GM0LXQstC40YciLCJvdXRwdXRUeXBlIjoiYmxvY2siLCJsYXN0TW9kaWZpZXJOYW1lIjoi0JrQu9Cw0LTQvtCyINCS0LjQutGC0L7RgCDQktCw0YHQuNC70YzQtdCy0LjRhyIsImxhbmd1YWdlIjoiZW4iLCJkaWFncmFtRGlzcGxheU5hbWUiOiIiLCJzRmlsZUlkIjoiIiwiYXR0SWQiOiIxMjMwOTk4MzcwIiwiZGlhZ3JhbU5hbWUiOiLQotC10YHRgiBEcmF3LmlvIiwiYXNwZWN0IjoiIiwibGlua3MiOiJhdXRvIiwiY2VvTmFtZSI6ItCf0LDRgNGB0LjQvdCzINGB0YLRgNCw0L3QuNGG0Ysg0KLQldCh0KIiLCJ0YnN0eWxlIjoidG9wIiwiY2FuQ29tbWVudCI6dHJ1ZSwiZGlhZ3JhbVVybCI6IiIsImNzdkZpbGVVcmwiOiIiLCJib3JkZXIiOnRydWUsIm1heFNjYWxlIjoiMSIsIm93bmluZ1BhZ2VJZCI6MTIyMjc5ODk5MywiZWRpdGFibGUiOnRydWUsImNlb0lkIjoxMjIyNzk4OTkzLCJwYWdlSWQiOiIiLCJsYm94Ijp0cnVlLCJzZXJ2ZXJDb25maWciOnsiZW1haWxwcmV2aWV3IjoiMSJ9LCJvZHJpdmVJZCI6IiIsInJldmlzaW9uIjoyLCJtYWNyb0lkIjoiN2NjZmU4NTItZWUzYi00OGEzLTljMWItZmQ5Y2FlMjk3ODNkIiwicHJldmlld05hbWUiOiLQotC10YHRgiBEcmF3LmlvLnBuZyIsImxpY2Vuc2VTdGF0dXMiOiJPSyIsInNlcnZpY2UiOiIiLCJpc1RlbXBsYXRlIjoiIiwid2lkdGgiOiIxMDcxIiwic2ltcGxlVmlld2VyIjpmYWxzZSwibGFzdE1vZGlmaWVkIjoxNzY4Mjg3MTE4MDAwLCJleGNlZWRQYWdlV2lkdGgiOmZhbHNlLCJvQ2xpZW50SWQiOiIifQ==</div>
</div>"""  # noqa: E501,W191


def test_parse_macro_data_from_conf_export_body_view() -> None:
    """Parse drawio macro with base64 JSON (body.view format from conf-export)."""
    soup = BeautifulSoup(DRAWIO_MACRO_HTML, "html.parser")
    el = soup.find("div", {"data-macro-name": "drawio"})
    assert el is not None

    att_id, diagram_name = parse_macro_data(el)

    assert att_id == "1230998370"
    assert diagram_name == "Тест Draw.io"


def test_parse_macro_data_fallback_diagram_name_parameter() -> None:
    """Fallback: editor/older format with |diagramName=...| in element string."""
    html = '<img data-macro-parameters="border=true|diagramName=My Diagram Name|width=800"/>'
    soup = BeautifulSoup(html, "html.parser")
    el = soup.find("img")

    att_id, diagram_name = parse_macro_data(el)

    assert att_id is None
    assert diagram_name == "My Diagram Name"


def test_parse_macro_data_no_data_returns_none() -> None:
    """Element without drawio data returns (None, None)."""
    soup = BeautifulSoup("<div class='other'>x</div>", "html.parser")
    el = soup.find("div")

    att_id, diagram_name = parse_macro_data(el)

    assert att_id is None
    assert diagram_name is None


def test_content_to_markdown() -> None:
    """Bytes are decoded to UTF-8 and wrapped in xml markdown block."""
    content = b'<mxfile><diagram id="1">test</diagram></mxfile>'
    result = content_to_markdown(content)

    assert result == '\n```xml\n<mxfile><diagram id="1">test</diagram></mxfile>\n```\n\n'


def test_content_to_markdown_unicode_replace_on_decode_error() -> None:
    """Invalid UTF-8 uses replace strategy and still produces markdown block."""
    content = b"<mxfile>\xff\xfe</mxfile>"
    result = content_to_markdown(content)

    assert "```xml" in result
    assert "mxfile" in result
    assert result.endswith("\n```\n\n")
