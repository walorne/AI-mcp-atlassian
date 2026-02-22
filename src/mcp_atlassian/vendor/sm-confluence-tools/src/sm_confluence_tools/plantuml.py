"""PlantUML-specific utilities."""

import logging
import re

import requests
from confluence_markdown_exporter.utils.app_data_store import get_settings

logger = logging.getLogger(__name__)
_INCLUDE_URL_PATTERN = re.compile(r"!include\s+(https?://\S+)")


def expand_includes(content: str) -> str:
    """Replace !include <url> lines with the fetched file content (one level, no recursion)."""
    lines: list[str] = []
    for line in content.splitlines():
        match = _INCLUDE_URL_PATTERN.search(line)
        if not match:
            lines.append(line)
            continue
        url = match.group(1).rstrip()
        try:
            resp = requests.get(
                url,
                timeout=15,
                verify=get_settings().connection_config.verify_ssl,
            )
            resp.raise_for_status()
            lines.append(resp.text.strip() if resp.text else "")
        except (requests.RequestException, OSError) as e:
            logger.warning("PlantUML !include %s failed: %s", url, e)
            lines.append(line)
    return "\n".join(lines)
