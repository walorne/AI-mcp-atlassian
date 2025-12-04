from unittest.mock import MagicMock, patch
import pytest
from mcp_atlassian.confluence.pages import PagesMixin
from mcp_atlassian.models.confluence import ConfluencePage

class TestPagesMixinExtended:
    """Extended tests for the PagesMixin class (new methods)."""

    @pytest.fixture
    def pages_mixin(self, confluence_client):
        """Create a PagesMixin instance for testing."""
        with patch("mcp_atlassian.confluence.pages.ConfluenceClient.__init__") as mock_init:
            mock_init.return_value = None
            mixin = PagesMixin()
            mixin.confluence = confluence_client.confluence
            mixin.config = confluence_client.config
            mixin.preprocessor = confluence_client.preprocessor
            return mixin

    def test_get_page_full(self, pages_mixin):

        """Test getting full page content (export_view)."""
        # Arrange
        page_id = "full_123"
        pages_mixin.config.url = "https://example.atlassian.net/wiki"
        
        # Mock response with export_view
        page_data = {
            "id": page_id,
            "title": "Full Page",
            "body": {
                "export_view": {"value": "<div class='export'>Full HTML</div>"},
                "storage": {"value": "<p>Storage</p>"}
            },
            "space": {"key": "TEST"},
            "version": {"number": 1}
        }
        pages_mixin.confluence.get_page_by_id.return_value = page_data
        
        # Mock preprocessor
        pages_mixin.preprocessor.process_html_content.return_value = (
            "<div class='export'>Full HTML</div>",
            "Processed Full Markdown"
        )
        
        # Act
        result = pages_mixin.get_page_full(page_id, convert_to_markdown=True)
        
        # Assert
        pages_mixin.confluence.get_page_by_id.assert_called_once_with(
            page_id=page_id,
            expand="body.export_view,version,space,children.attachment"
        )
        assert result.content == "Processed Full Markdown"
        
        # Test with convert_to_markdown=False
        result_html = pages_mixin.get_page_full(page_id, convert_to_markdown=False)
        assert result_html.content == "<div class='export'>Full HTML</div>"

    def test_get_page_full_fallback(self, pages_mixin):
        """Test fallback to storage when export_view is missing."""
        # Arrange
        page_id = "fallback_123"
        pages_mixin.config.url = "https://example.atlassian.net/wiki"
        
        # Mock response WITHOUT export_view but WITH storage
        page_data = {
            "id": page_id,
            "title": "Fallback Page",
            "body": {
                "storage": {"value": "<p>Storage Content</p>"}
            },
            "space": {"key": "TEST"},
            "version": {"number": 1}
        }
        pages_mixin.confluence.get_page_by_id.return_value = page_data
        
        # Mock preprocessor
        pages_mixin.preprocessor.process_html_content.return_value = (
            "<p>Storage Content</p>",
            "Storage Markdown"
        )
        
        # Act
        result = pages_mixin.get_page_full(page_id)
        
        # Assert
        assert result.content == "Storage Markdown"

    def test_get_page_full_by_title(self, pages_mixin):
        """Test getting full page by title."""
        # Arrange
        space = "TEST"
        title = "Title Page"
        pages_mixin.config.url = "https://example.atlassian.net/wiki"
        
        page_data = {
            "id": "title_123",
            "title": title,
            "body": {"export_view": {"value": "<div>HTML</div>"}},
            "space": {"key": space},
            "version": {"number": 1}
        }
        pages_mixin.confluence.get_page_by_title.return_value = page_data
        
        pages_mixin.preprocessor.process_html_content.return_value = (
            "<div>HTML</div>", "MD"
        )
        
        # Act
        result = pages_mixin.get_page_full_by_title(space, title)
        
        # Assert
        pages_mixin.confluence.get_page_by_title.assert_called_once_with(
            space=space, title=title, expand="body.export_view,version"
        )
        assert result.id == "title_123"

