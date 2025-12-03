"""Module for parsing Confluence page links from HTML viewinfo."""

import logging
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger("mcp-atlassian")


class ConfluenceLinksParser:
    """Parses links from Confluence viewinfo.action HTML."""

    def __init__(self, base_url: str) -> None:
        """
        Initialize the parser.

        Args:
            base_url: The base URL of the Confluence instance.
        """
        self.base_url = base_url.rstrip("/")
        self.internal_netloc = urlparse(self.base_url).netloc.lower()

    def parse(self, html_content: str, current_url: str) -> dict[str, list[dict]]:
        """
        Parse HTML content from viewinfo.action and extract structured links.

        Args:
            html_content: Raw HTML content from viewinfo.action
            current_url: The URL where content was fetched from (for relative link resolution)

        Returns:
            Dictionary with 'incoming' and 'outgoing' lists.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        raw_links = []

        # Find all links and identify their container panel
        for a in soup.select("a[href]"):
            href = urljoin(current_url, a["href"])
            text = a.get_text(strip=True)

            # Find the nearest panel container
            # In classic Confluence UI, links are grouped in div.basicPanelContainer
            panel = a.find_parent("div", class_="basicPanelContainer")
            if panel:
                title_div = panel.find("div", class_="basicPanelTitle")
                block = (
                    title_div.get_text(strip=True) if title_div else "[untitled block]"
                )
            else:
                block = "[outside panel]"

            raw_links.append(
                {"block": block, "text": text or "[empty text]", "href": href}
            )

        # Filter and transform
        return self._process_links(raw_links)

    def _process_links(self, raw_links: list[dict]) -> dict[str, list[dict]]:
        """Filter and transform raw links into structured data."""
        incoming = []
        outgoing = []

        for link in raw_links:
            block = link.get("block", "").lower()
            href = link["href"]
            text = link["text"]

            direction = None
            if "incoming links" in block:
                direction = "incoming"
            elif "outgoing links" in block:
                # Check if internal or external based on host
                link_host = urlparse(href).netloc.lower()
                if self.internal_netloc in link_host:
                    direction = "outgoing_internal"
                else:
                    direction = "outgoing_external"
            else:
                # Skip links not in relevant blocks
                continue

            # Parse metadata from URL
            metadata = self._parse_url_metadata(href, text)
            
            link_data = {
                "page_id": metadata["page_id"],
                "space": metadata["space"],
                "title": metadata["title"],
                "href": href,
                "type": direction
            }

            if direction == "incoming":
                incoming.append(link_data)
            else:
                outgoing.append(link_data)

        return {"incoming": incoming, "outgoing": outgoing}

    def _parse_url_metadata(self, href: str, text: str) -> dict:
        """Extract page_id, space, and title from URL."""
        page_id = None
        space = None
        title = text  # Default title is link text

        try:
            parsed = urlparse(href)
            path = parsed.path

            if path.endswith("/viewpage.action"):
                # Format: /pages/viewpage.action?pageId=12345
                qs = parse_qs(parsed.query)
                page_id = qs.get("pageId", [None])[0]
                
            elif "/display/" in path:
                # Format: /display/SPACE/TITLE+WITH+PLUSES
                # Example path: /wiki/display/SPACE/Title
                if "/display/" in path:
                    disp_part = path.split("/display/", 1)[1]
                    parts = disp_part.split("/", 1)
                    space = parts[0]
                    if len(parts) > 1:
                        # Decode + and %XX
                        raw_title = parts[1]
                        # First unquote to handle %20 etc, then replace + with space if standard URL decoding didn't handle it
                        title = unquote(raw_title).replace("+", " ")
        except Exception:
            # Fallback to defaults if parsing fails
            pass

        return {
            "page_id": page_id,
            "space": space,
            "title": title
        }

