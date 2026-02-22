"""Client class for initializing sm-confluence-tools with authentication tokens."""

import logging
import os
from typing import TYPE_CHECKING

from confluence_markdown_exporter.utils.app_data_store import set_setting
from dotenv import load_dotenv

if TYPE_CHECKING:
    from sm_confluence_tools.page import _Page


logger = logging.getLogger(__name__)


class SmConfluenceTools:
    """Main client class for sm-confluence-tools library.

    This class handles authentication initialization and provides access to Page class.
    Users should initialize this class first with their tokens, then use the Page property
    to access page functionality.
    """

    def __init__(
        self,
        confluence_token: str | None = None,
        jira_token: str | None = None,
        confluence_url: str = "https://confluence.app.local/",
        jira_url: str = "https://jira.app.local/",
        verify_ssl: bool = True,
        output_path: str = "./conf-export",
    ):
        """Initialize the sm-confluence-tools client with authentication tokens.

        Args:
            confluence_url: URL of the Confluence server (optional)
            confluence_token: API token for Confluence authentication (leave empty to read from .env)
            jira_url: URL of the Jira server (optional)
            jira_token: API token for Jira authentication (optional, leave empty to read from .env)
            verify_ssl: Whether to verify SSL certificates (default: False)
            output_path: Path for exported files (default: "./conf-export")
        """  # noqa
        load_dotenv()

        # Disable SSL verification for all requests
        set_setting("connection_config.verify_ssl", verify_ssl)

        # Set up authentication (URL and API token)
        confluence_token = confluence_token or os.getenv("CONFLUENCE_TOKEN")
        jira_token = jira_token or os.getenv("JIRA_TOKEN")

        set_setting("auth.confluence.url", confluence_url)
        set_setting("auth.confluence.pat", confluence_token)

        if jira_url and jira_token:
            set_setting("auth.jira.url", jira_url)
            set_setting("auth.jira.pat", jira_token)

        set_setting("export.output_path", output_path)
        set_setting("export.page_path", "{page_title}.md")

    @property
    def Page(self) -> type["_Page"]:
        """Get access to the Page class with current authentication configuration."""
        from sm_confluence_tools.page import _Page

        return _Page
