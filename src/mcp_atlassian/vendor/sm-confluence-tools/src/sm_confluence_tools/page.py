"""Core classes for working with Confluence pages."""

import functools
import logging
import urllib.parse
from pathlib import Path
from typing import Literal, cast

from atlassian.errors import ApiError
from bs4 import BeautifulSoup
from confluence_markdown_exporter import confluence as cmexp
from confluence_markdown_exporter.utils.app_data_store import get_settings
from confluence_markdown_exporter.utils.table_converter import pad
from requests import HTTPError
from typing_extensions import override

from sm_confluence_tools import drawio, plantuml
from sm_confluence_tools.attachment import _Attachment

logger = logging.getLogger(__name__)


class _Page(cmexp.Page):
    """Enhanced Page class with custom Converter."""

    attachments: list[_Attachment]

    @classmethod
    @functools.lru_cache(maxsize=1000)
    def from_id(cls, page_id: int) -> "_Page":
        try:
            result = cast(
                dict,
                cmexp.confluence.get_page_by_id(
                    page_id,
                    expand="body.view,body.export_view,body.editor,metadata.labels,"
                    "metadata.properties,ancestors",
                ),
            )
            return cls.from_json(result)

        except (ApiError, HTTPError):
            logger.warning(f"Could not access page with ID {page_id}")
            # Return a minimal page object with error information
            return cls(
                id=page_id,
                title="Page not accessible",
                space=cmexp.Space(key="", name="", description="", homepage=0),
                body="",
                body_export="",
                editor2="",
                labels=[],
                attachments=[],
                ancestors=[],
            )

    @classmethod
    @override
    def from_url(cls, page_url: str) -> "_Page":
        """Retrieve a Page object given a Confluence page URL."""
        parsed = urllib.parse.urlparse(page_url)
        path = parsed.path.strip("/")

        # Случай 1: URL с pageId в параметрах
        if "viewpage.action" in path or "pageId" in parsed.query:
            if parsed.query:
                params = urllib.parse.parse_qs(parsed.query)
                page_id: str | None = params.get("pageId", [""])[0]
                if page_id:
                    return _Page.from_id(int(page_id))

        # Случай 2: Короткая ссылка /x/XXXXX
        if path.startswith("x/") or path.startswith("requirements/"):
            try:
                # Пытаемся разрешить короткую ссылку через редирект
                response = cmexp.confluence.session.get(
                    page_url, allow_redirects=True, timeout=10, verify=cmexp.confluence.verify_ssl
                )
                # Извлекаем pageId из финального URL
                final_url = response.url

                final_parsed = urllib.parse.urlparse(final_url)
                if "pageId" in final_parsed.query:
                    params = urllib.parse.parse_qs(final_parsed.query)
                    page_id = params.get("pageId", [""])[0]
                    if page_id:
                        return _Page.from_id(int(page_id))
            except Exception:
                logger.exception(f"url {page_url}")

        # Случай 3: /display/SPACE/TITLE или /display/SPACE
        if path.startswith("display/"):
            space_and_page = path.split("display/")[-1]

            # Разделяем space и page по разделителю /
            parts = space_and_page.split("/", 1)  # Максимум 1 разделение
            space = parts[0] if len(parts) > 0 else None
            page = parts[1] if len(parts) > 1 else None

            # Если есть page, пытаемся найти страницу по space и title
            if page:
                page_title = urllib.parse.unquote(page)
                # Затем заменяем + на пробелы (если остались после декодирования)
                page_title = page_title.replace("+", " ")
                page_id = cmexp.confluence.get_page_id(space, page_title)
                return _Page.from_id(page_id)

            if space:
                space_info = cmexp.confluence.get_space(space, expand="homepage")
                page_id = space_info.get("homepage", {}).get("id", None)
                if page_id:
                    return _Page.from_id(page_id)

        msg = f"Could not parse page URL {page_url}."
        raise ValueError(msg)

    @classmethod
    @override
    def from_json(cls, data: dict) -> "_Page":
        """Create SmPage but replace attachment list with SmAttachment."""
        return cls(
            id=data.get("id", 0),
            title=data.get("title", ""),
            space=cmexp.Space.from_key(
                data.get("_expandable", {}).get("space", "").split("/")[-1]
            ),
            body=data.get("body", {}).get("view", {}).get("value", ""),
            body_export=data.get("body", {}).get("export_view", {}).get("value", ""),
            editor2=data.get("body", {}).get("editor", {}).get("value", ""),
            labels=[
                # Label type is initialized inside the base Page.from_json,
                # we don't need them in a special form, so leave as is.
            ],
            attachments=_Attachment.from_page_id(data.get("id", 0)),
            ancestors=[ancestor.get("id") for ancestor in data.get("ancestors", [])][1:],
        )

    @override
    def export_attachments(self) -> None:
        if get_settings().export.attachment_export_all:
            for attachment in self.attachments:
                attachment.export()
        else:
            for attachment in self.attachments:
                if (
                    attachment.filename.endswith(".drawio")
                    and f"diagramName={attachment.title}" in self.body
                ):
                    print(attachment.title)
                    attachment.export()
                    continue
                if (
                    attachment.filename.endswith(".drawio.png")
                    or attachment.filename.endswith(".drawio")
                ) and attachment.title.replace(" ", "%20") in self.body_export:
                    attachment.export()
                    continue

    @property
    def markdown(self) -> str:
        return self.SmConverter(self).markdown  # type: ignore[no-any-return]

    class SmConverter(cmexp.Page.Converter):
        """Enhanced converter."""

        page: "_Page"

        def __init__(self, page: "_Page"):
            super().__init__(page)

            self.plantuml_counter = 0

            self.body_jira_tables = BeautifulSoup(self.page.body, "html.parser").find_all(
                "div", {"data-macro-name": "jira"}
            )
            self.export_jira_tables = BeautifulSoup(self.page.body_export, "html.parser").find_all(
                "div", {"class": ["jira-table", "jim-error-message-table"]}
            )

        @property
        @override
        def breadcrumbs(self) -> str:
            """Breadcrumbs with links to Confluence pages."""
            base_url = str(get_settings().auth.confluence.url).rstrip("/")
            parts: list[str] = []
            for ancestor_id in self.page.ancestors:
                try:
                    ancestor_id_int = int(ancestor_id)
                    ancestor_page = _Page.from_id(ancestor_id_int)
                    url = f"{base_url}/pages/viewpage.action?pageId={ancestor_id_int}"
                    parts.append(f"[{ancestor_page.title}]({url})")
                except Exception:
                    # In extreme cases, just skip the problematic ancestor
                    continue
            return (" > ".join(parts) + "\n") if parts else ""

        @override
        def convert_jira_table(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            index = self.body_jira_tables.index(el)

            try:
                table = self.export_jira_tables[index]
            except IndexError:
                logger.error(f"Таблица {str(el.copy_self())} не найдена.")
                raise

            result: str = self.process_tag(table, parent_tags)
            return result

        @override
        def convert_table(
            self, el: BeautifulSoup, text: str, parent_tags: list[str]
        ) -> str:
            if el.has_attr("class") and "metadata-summary-macro" in str(el.get("class", "")):
                return self.convert_page_properties_report(el, text, parent_tags)
            rows = [
                cast("list[Tag]", tr.find_all(["td", "th"]))
                for tr in cast("list[Tag]", el.find_all("tr"))
                if tr
            ]
            if not rows:
                return ""
            padded_rows = pad(rows)
            converted = [[self.convert(str(cell)) for cell in row] for row in padded_rows]
            has_header = bool(
                rows[0]
                and all(cell.name == "th" for cell in rows[0])
            )
            if has_header:
                header, data = converted[0], converted[1:]
            else:
                header = [""] * len(converted[0])
                data = converted
            n = len(header)
            sep = "| " + " | ".join("---" for _ in range(n)) + " |"
            lines = [
                "| " + " | ".join(c.strip() for c in header) + " |",
                sep,
                *("| " + " | ".join(cell.strip() for cell in row) + " |" for row in data),
            ]
            return "\n".join(lines) + "\n"

        @override
        def _get_path_for_href(self, path: Path, style: Literal["absolute", "relative"]) -> str:
            """Globally normalize paths in href: always forward slashes."""
            raw: str = super()._get_path_for_href(path, style)
            return raw.replace("\\", "/")

        def convert_span(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            if el.has_attr("data-macro-name"):
                if el["data-macro-name"] == "jira":
                    return self.convert_jira_issue(  # type: ignore[no-any-return]
                        el, text, parent_tags
                    )

                if el["data-macro-name"] == "plantuml":
                    return self.convert_plantuml(el, text, parent_tags)

            return text

        @override
        def convert_plantuml(
            self, el: BeautifulSoup, text: str, parent_tags: list[str]
        ) -> str:  # noqa: PLR0911
            """Convert PlantUML diagrams from editor XML to Markdown code blocks.

            PlantUML diagrams are stored in the editor XML as structured macros with
            the UML definition in a JSON structure inside CDATA sections.
            """
            logger.debug("Processing PlantUML macro")

            # Parse the editor content to find the PlantUML macro
            # The editor2 content is an XML fragment without a root element, so wrap it
            wrapped_editor2 = f"<root>{self.page.editor2}</root>"
            soup_editor2 = BeautifulSoup(wrapped_editor2, "html.parser")  # HTML - not XML!

            # Find the corresponding macro in editor content
            macro_list = soup_editor2.find_all("table", {"data-macro-name": "plantuml"})
            logger.debug(macro_list)

            plantuml_macro = (
                macro_list[self.plantuml_counter]
                if self.plantuml_counter < len(macro_list)
                else None
            )

            if not plantuml_macro:
                logger.warning(
                    f"PlantUML macro number {self.plantuml_counter} not found in editor XML"  # noqa: E713,E501
                )
                return "\n<!-- PlantUML diagram (not found in editor2) -->\n\n"

            self.plantuml_counter += 1

            # Get macro ID for logging
            macro_id = plantuml_macro.get("data-macro-id", "unknown")

            # Extract the <pre> containing the diagram
            plain_text_body = plantuml_macro.find("pre")
            if not plain_text_body:
                logger.warning(f"PlantUML macro {macro_id} has no plain-text-body")
                return "\n<!-- PlantUML diagram (no content found) -->\n\n"

            content = plain_text_body.get_text(strip=True)
            if not content:
                logger.warning(f"PlantUML macro {macro_id} has empty content")
                return "\n<!-- PlantUML diagram (empty content) -->\n\n"

            content = plantuml.expand_includes(content)
            return f"\n```plantuml\n{content}\n```\n\n"

        @override
        def convert_drawio(self, el: BeautifulSoup, text: str, parent_tags: list[str]) -> str:
            """Convert draw.io macro to inline XML block."""
            att_id, drawio_name = drawio.parse_macro_data(el)

            attachment = None
            if att_id:
                attachment = self.page.get_attachment_by_id(str(att_id))
            if attachment is None and drawio_name:
                attachments = self.page.get_attachments_by_title(drawio_name)
                if attachments:
                    attachment = attachments[0]

            if attachment is None:
                name = drawio_name or att_id or "unknown"
                return f"\n<!-- Drawio diagram `{name}` not found -->\n\n"

            content = cast(_Attachment, attachment).get_content()
            if content is None:
                name = drawio_name or att_id or "unknown"
                return f"\n<!-- Drawio diagram `{name}` content unavailable -->\n\n"

            return drawio.content_to_markdown(content)
