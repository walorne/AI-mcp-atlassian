"""Extended unit tests for the Confluence FastMCP server (new tools)."""

import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Client, FastMCP
from fastmcp.client import FastMCPTransport
from starlette.requests import Request

from src.mcp_atlassian.confluence import ConfluenceFetcher
from src.mcp_atlassian.confluence.config import ConfluenceConfig
from src.mcp_atlassian.models.confluence.page import ConfluencePage
from src.mcp_atlassian.servers.context import MainAppContext
from src.mcp_atlassian.servers.main import AtlassianMCP
from src.mcp_atlassian.utils.oauth import OAuthConfig

logger = logging.getLogger(__name__)

# Import NEW tools to register
from src.mcp_atlassian.servers.confluence import (
    get_page_full,
    get_page_links,
)

@pytest.fixture
def mock_confluence_fetcher():
    """Create a mocked ConfluenceFetcher instance for testing."""
    mock_fetcher = MagicMock(spec=ConfluenceFetcher)

    # Mock page object
    mock_page = MagicMock(spec=ConfluencePage)
    mock_page.to_simplified_dict.return_value = {
        "id": "123456",
        "title": "Full Page Title",
        "content": {"value": "Full Content"},
    }
    
    # Mock methods
    mock_fetcher.get_page_full.return_value = mock_page
    mock_fetcher.get_page_full_by_title.return_value = mock_page
    
    mock_fetcher.get_page_links.return_value = {
        "incoming": [{"title": "In", "page_id": "1"}],
        "outgoing": [{"title": "Out", "href": "http://out"}]
    }

    return mock_fetcher

@pytest.fixture
def mock_base_confluence_config():
    return ConfluenceConfig(
        url="https://mock.atlassian.net/wiki",
        auth_type="basic",
        username="user",
        api_token="token"
    )

@pytest.fixture
def test_confluence_mcp(mock_confluence_fetcher, mock_base_confluence_config):
    """Create a test FastMCP instance with new tools registered."""

    @asynccontextmanager
    async def test_lifespan(app: FastMCP) -> AsyncGenerator[MainAppContext, None]:
        yield MainAppContext(
            full_confluence_config=mock_base_confluence_config, read_only=False
        )

    test_mcp = AtlassianMCP(
        "TestConfluenceExtended",
        lifespan=test_lifespan,
    )

    confluence_sub_mcp = FastMCP(name="TestConfluenceSubMCP")
    # Register ONLY new tools for this test suite
    confluence_sub_mcp.tool()(get_page_full)
    confluence_sub_mcp.tool()(get_page_links)

    test_mcp.mount("confluence", confluence_sub_mcp)
    return test_mcp

@pytest.fixture
async def client(test_confluence_mcp, mock_confluence_fetcher):
    """Create a FastMCP client."""
    with (
        patch(
            "src.mcp_atlassian.servers.confluence.get_confluence_fetcher",
            AsyncMock(return_value=mock_confluence_fetcher),
        ),
        patch(
            "src.mcp_atlassian.servers.dependencies.get_http_request",
            MagicMock(spec=Request, state=MagicMock()),
        ),
    ):
        client_instance = Client(transport=FastMCPTransport(test_confluence_mcp))
        async with client_instance as connected_client:
            yield connected_client

@pytest.mark.anyio
async def test_get_page_links(client, mock_confluence_fetcher):
    """Test get_page_links tool."""
    response = await client.call_tool("confluence_get_page_links", {"page_id": "123"})
    
    mock_confluence_fetcher.get_page_links.assert_called_once_with("123")
    
    result = json.loads(response[0].text)
    assert "incoming" in result
    assert "outgoing" in result
    assert result["incoming"][0]["title"] == "In"

@pytest.mark.anyio
async def test_get_page_full_by_id(client, mock_confluence_fetcher):
    """Test get_page_full tool by ID."""
    response = await client.call_tool("confluence_get_page_full", {"page_id": "123"})
    
    mock_confluence_fetcher.get_page_full.assert_called_once()
    args, kwargs = mock_confluence_fetcher.get_page_full.call_args
    assert args[0] == "123"
    assert kwargs["convert_to_markdown"] is True
    
    result = json.loads(response[0].text)
    assert result["metadata"]["title"] == "Full Page Title"

@pytest.mark.anyio
async def test_get_page_full_by_title(client, mock_confluence_fetcher):
    """Test get_page_full tool by title."""
    response = await client.call_tool(
        "confluence_get_page_full", 
        {"title": "My Page", "space_key": "DS"}
    )
    
    mock_confluence_fetcher.get_page_full_by_title.assert_called_once()
    args, kwargs = mock_confluence_fetcher.get_page_full_by_title.call_args
    assert args[0] == "DS"
    assert args[1] == "My Page"
    
    result = json.loads(response[0].text)
    assert result["metadata"]["title"] == "Full Page Title"

