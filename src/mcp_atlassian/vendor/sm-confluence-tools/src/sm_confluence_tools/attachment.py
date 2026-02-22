"""Class for working with Confluence attachments."""

import logging
from pathlib import Path

from confluence_markdown_exporter import confluence as cmexp
from requests import HTTPError
from slugify import slugify
from typing_extensions import override

logger = logging.getLogger(__name__)


class _Attachment(cmexp.Attachment):
    """Enhanced Attachment class with custom export and SSL verification logging."""

    @property
    @override
    def filename(self) -> str:
        return str(slugify(self.title) + self.extension)

    @property
    @override
    def export_path(self) -> Path:
        return Path(slugify(self.title) + self.extension)

    def get_content(self) -> bytes | None:
        """Download attachment content via API without saving to disk.

        Returns:
            The attachment content as bytes, or None if download failed.
        """
        url = str(cmexp.confluence.url + self.download_link)

        try:
            response = cmexp.confluence.get(url, absolute=True, advanced_mode=True)
            response.raise_for_status()
            return response.content  # type: ignore[no-any-return]
        except HTTPError as e:
            logger.warning(f"Failed to get content for attachment '{self.title}': {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error getting attachment '{self.title}': {e}")
            return None
