"""Tests for PlantUML include expansion."""

from unittest.mock import MagicMock, patch

from sm_confluence_tools.plantuml import expand_includes


def test_expand_includes_without_include_returns_unchanged() -> None:
    """Content without !include is returned unchanged."""
    content = "@startuml\nclass Foo\n@enduml"
    assert expand_includes(content) == content


def test_expand_includes_replaces_url_with_fetched_content() -> None:
    """!include <url> line is replaced with fetched content."""
    content = "@startuml\n!include https://example.com/common.puml\n@enduml"
    mock_response = MagicMock()
    mock_response.text = "class Bar"
    mock_response.raise_for_status = MagicMock()

    with (
        patch("sm_confluence_tools.plantuml.requests.get", return_value=mock_response),
        patch("sm_confluence_tools.plantuml.get_settings") as mock_settings,
    ):
        mock_settings.return_value.connection_config.verify_ssl = True
        result = expand_includes(content)

    assert result == "@startuml\nclass Bar\n@enduml"


def test_expand_includes_on_fetch_failure_keeps_original_line() -> None:
    """When fetch fails, original !include line is kept."""
    content = "@startuml\n!include https://example.com/missing.puml\n@enduml"

    with (
        patch(
            "sm_confluence_tools.plantuml.requests.get",
            side_effect=ConnectionError("Connection refused"),
        ),
        patch("sm_confluence_tools.plantuml.get_settings") as mock_settings,
    ):
        mock_settings.return_value.connection_config.verify_ssl = True
        result = expand_includes(content)

    assert result == content
