"""PlantUML-specific utilities."""

import logging
import re

import requests
from confluence_markdown_exporter.utils.app_data_store import get_settings

logger = logging.getLogger(__name__)
_INCLUDE_URL_PATTERN = re.compile(r"!include\s+(https?://\S+)")


def _extract_block(content: str, block_ref: str) -> str:
    """Extract one block from PlantUML file: by 0-based index (!0, !1) or by id (!blockname)."""
    blocks: list[str] = []
    pos = 0
    while True:
        start = content.find("@startuml", pos)
        if start == -1:
            break
        end = content.find("@enduml", start)
        if end == -1:
            break
        end += len("@enduml")
        block_content = content[start:end].strip()
        blocks.append(block_content)
        pos = end

    if not blocks:
        return content.strip()

    if block_ref.isdigit():
        idx = int(block_ref)
        if 0 <= idx < len(blocks):
            return blocks[idx]
        return blocks[0]

    id_pattern = re.compile(
        r"@startuml\s*\(\s*id\s*=\s*" + re.escape(block_ref) + r"\s*\)",
        re.IGNORECASE,
    )
    for b in blocks:
        if id_pattern.search(b):
            return b
    return blocks[0]


def expand_includes(content: str) -> str:
    """Replace !include <url> or !include <url>!<block> with fetched content (or extracted block)."""
    lines: list[str] = []
    for line in content.splitlines():
        match = _INCLUDE_URL_PATTERN.search(line)
        if not match:
            lines.append(line)
            continue
        url = match.group(1).rstrip()
        if "!" in url:
            fetch_url, rest = url.split("!", 1)
            block_ref = rest.strip() or None
        else:
            fetch_url = url
            block_ref = None
        try:
            resp = requests.get(
                fetch_url,
                timeout=15,
                verify=get_settings().connection_config.verify_ssl,
            )
            resp.raise_for_status()
            text = resp.text.strip() if resp.text else ""
            if block_ref and text:
                text = _extract_block(text, block_ref)
            lines.append(text)
        except (requests.RequestException, OSError) as e:
            logger.warning("PlantUML !include %s failed: %s", url, e)
            lines.append(line)
    return "\n".join(lines)
