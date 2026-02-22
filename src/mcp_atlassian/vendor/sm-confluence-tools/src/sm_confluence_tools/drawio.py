"""Draw.io macro parsing and markdown formatting."""

import base64
import json
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bs4 import BeautifulSoup


def parse_macro_data(el: "BeautifulSoup") -> tuple[str | None, str | None]:
    """Extract attId and diagramName from a draw.io macro element (body.view or editor).

    Tries hidden div with base64 JSON (drawio-macro-data-*) first, then fallback
    to |diagramName=...| in element string for older/editor format.
    """
    att_id: str | None = None
    drawio_name: str | None = None
    for div in el.find_all("div", recursive=True):
        div_id = div.get("id") or ""
        if isinstance(div_id, str) and div_id.startswith("drawio-macro-data-"):
            raw = div.get_text(strip=True)
            if raw:
                try:
                    data = json.loads(base64.b64decode(raw).decode("utf-8"))
                    att_id = data.get("attId")
                    drawio_name = data.get("diagramName")
                except (ValueError, TypeError):
                    pass
            break

    if not drawio_name:
        match = re.search(r"\|diagramName=(.+?)\|", str(el))
        if match:
            drawio_name = match.group(1)

    return (att_id, drawio_name)


def content_to_markdown(content: bytes) -> str:
    """Decode draw.io attachment bytes to UTF-8 and wrap in XML markdown block."""
    try:
        xml_content = content.decode("utf-8")
    except UnicodeDecodeError:
        xml_content = content.decode("utf-8", errors="replace")
    return f"\n```xml\n{xml_content.strip()}\n```\n\n"
