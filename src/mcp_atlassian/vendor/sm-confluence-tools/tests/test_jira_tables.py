"""Test converting a page with Jira tables."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from sm_confluence_tools.client import SmConfluenceTools

tools = SmConfluenceTools()


@pytest.fixture
def mock_attachments():
    """Fixture для мокирования загрузки вложений.

    Этот fixture предотвращает реальные запросы к серверу Confluence
    при вызове _Attachment.from_page_id() внутри Page.from_json().
    """
    with patch("sm_confluence_tools.attachment._Attachment.from_page_id") as mock:
        mock.return_value = []
        yield mock


def test_convert_jira_tables_when_one_table_is_not_loaded(mock_attachments) -> None:
    """Test reading a page from partially-no-jira-data.json and converting to markdown."""
    # Load the JSON file
    json_path = Path(__file__).parent / "partially-no-jira-data.json"
    with json_path.open(encoding="utf-8") as f:
        page_data = json.load(f)

    # Create a Page object from the JSON data
    page = tools.Page.from_json(page_data)
    markdown = page.markdown

    # Первая таблица не загрузилась
    assert "Проект Jira не существует" in markdown

    # Вторая таблица загрузилась
    assert "Отображение 3 из\n[Проблем:" in markdown
