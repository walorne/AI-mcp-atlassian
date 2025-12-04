import pytest
from mcp_atlassian.preprocessing.links import ConfluenceLinksParser

@pytest.fixture
def parser():
    return ConfluenceLinksParser("https://confluence.example.com")

def test_parse_incoming_links(parser):
    html = """
    <div class="basicPanelContainer">
        <div class="basicPanelTitle">Incoming Links</div>
        <div class="basicPanelBody">
            <ul>
                <li>
                    <a href="/pages/viewpage.action?pageId=123">Referring Page</a>
                </li>
            </ul>
        </div>
    </div>
    """
    result = parser.parse(html, "https://confluence.example.com/pages/viewinfo.action?pageId=999")
    
    assert len(result["incoming"]) == 1
    link = result["incoming"][0]
    assert link["title"] == "Referring Page"
    assert link["page_id"] == "123"
    assert link["type"] == "incoming"

def test_parse_outgoing_internal_links(parser):
    html = """
    <div class="basicPanelContainer">
        <div class="basicPanelTitle">Outgoing Links</div>
        <div class="basicPanelBody">
            <ul>
                <li>
                    <a href="/display/SPACE/My+Page">Internal Page</a>
                </li>
            </ul>
        </div>
    </div>
    """
    result = parser.parse(html, "https://confluence.example.com/pages/viewinfo.action?pageId=999")
    
    assert len(result["outgoing"]) == 1
    link = result["outgoing"][0]
    assert link["title"] == "My Page"  # + decoded to space
    assert link["space"] == "SPACE"
    assert link["type"] == "outgoing_internal"

def test_parse_outgoing_external_links(parser):
    html = """
    <div class="basicPanelContainer">
        <div class="basicPanelTitle">Outgoing Links</div>
        <div class="basicPanelBody">
            <ul>
                <li>
                    <a href="https://google.com">Google</a>
                </li>
            </ul>
        </div>
    </div>
    """
    result = parser.parse(html, "https://confluence.example.com/pages/viewinfo.action?pageId=999")
    
    assert len(result["outgoing"]) == 1
    link = result["outgoing"][0]
    assert link["href"] == "https://google.com"
    assert link["type"] == "outgoing_external"

def test_url_decoding_with_plus(parser):
    # Test specific case for URL decoding with + and %XX
    # Example: /display/SPACE/Page+With%2BPlus
    # Should become "Page With+Plus" (first + -> space, then %2B -> +)
    
    href = "/display/SPACE/Page+With%2BPlus"
    text = "Link Text"
    metadata = parser._parse_url_metadata(href, text)
    
    assert metadata["title"] == "Page With+Plus"
    assert metadata["space"] == "SPACE"

