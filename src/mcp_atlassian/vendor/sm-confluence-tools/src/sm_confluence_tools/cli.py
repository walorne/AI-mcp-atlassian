"""CLI for exporting pages from terminal."""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from dotenv import load_dotenv

from .client import SmConfluenceTools

if TYPE_CHECKING:
    from .page import _Page

if sys.platform.startswith("win"):
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())


def _run_with_timeout(
    func: Callable[..., Any],
    timeout_sec: int,
    logger: logging.Logger,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Run function with timeout. Returns None on timeout."""
    result: list[Any] = [None]
    exception: list[Optional[BaseException]] = [None]

    def target() -> None:
        try:
            result[0] = func(*args, **kwargs)
        except Exception as e:
            exception[0] = e

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout_sec)

    if thread.is_alive():
        logger.error(f"Операция превысила таймаут {timeout_sec} секунд")
        return None
    if exception[0]:
        raise exception[0]
    return result[0]


def _safe_save_markdown(
    page: "_Page",
    markdown_file: Path,
    timeout_sec: int,
    logger: logging.Logger,
) -> bool:
    """Save markdown with timeout and fallback on error."""
    try:
        logger.info("Попытка сохранения Markdown контента...")

        def save_md() -> bool:
            markdown_file.write_text(page.markdown, encoding="utf-8")
            return True

        success = _run_with_timeout(save_md, timeout_sec, logger)
        if success:
            logger.info(f"Markdown контент сохранен: {markdown_file}")
            return True
        logger.warning("Таймаут при сохранении Markdown")
        return False
    except Exception as e:
        logger.warning(f"Ошибка при сохранении Markdown: {str(e)}")
        fallback = f"""# {page.title}

## Ошибка извлечения Markdown

**Ошибка:** {str(e)}

## Доступная информация

- **ID страницы:** {page.id}
- **Пространство:** {page.space}
- **Количество предков:** {len(page.ancestors)}
- **Количество вложений:** {len(page.attachments)}

## HTML контент

HTML контент доступен в файле: content.html
"""  # noqa

        try:
            markdown_file.write_text(fallback, encoding="utf-8")
            logger.info(f"Сохранен fallback файл для Markdown: {markdown_file}")
            return True
        except Exception as fallback_err:
            logger.error(f"Не удалось создать fallback файл: {str(fallback_err)}")
            return False


def _save_page_data(
    page: "_Page",
    page_id: int,
    output_dir: Path,
    timeout_sec: int,
    logger: logging.Logger,
) -> bool:
    """Save metadata, HTML, Markdown, editor2, attachments.json."""
    try:
        safe_title = page.title[:50].replace("/", "_").replace("\\", "_")
        page_dir = output_dir / f"page_{page_id}_{safe_title}"
        page_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Сохраняем данные в директорию: {page_dir}")

        export_path = getattr(page, "export_path", None)

        metadata = {
            "id": page.id,
            "title": page.title,
            "space": str(page.space) if page.space else None,
            "ancestors": page.ancestors,
            "labels": [str(lbl) for lbl in page.labels] if page.labels else [],
            "attachments_count": len(page.attachments),
            "export_path": str(export_path) if export_path else None,
            "timestamp": datetime.now().isoformat(),
            "timeout_used": timeout_sec,
        }
        (page_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Метаданные сохранены: metadata.json")

        (page_dir / "body.html").write_text(page.body, encoding="utf-8")
        (page_dir / "export.html").write_text(page.body_export, encoding="utf-8")

        if not _safe_save_markdown(page, page_dir / "content.md", timeout_sec, logger):
            logger.warning("Не удалось сохранить Markdown контент")

        if getattr(page, "editor2", None):
            try:
                (page_dir / "editor2.xml").write_text(page.editor2, encoding="utf-8")
                logger.info("Editor2 данные сохранены: editor2.xml")
            except Exception as e:
                logger.warning(f"Не удалось сохранить Editor2 данные: {str(e)}")

        if page.attachments:
            attachments_info = [
                {
                    "id": att.id,
                    "title": att.title,
                    "file_id": getattr(att, "file_id", None),
                    "media_type": getattr(att, "media_type", None),
                    "size": getattr(att, "size", None),
                }
                for att in page.attachments
            ]
            (page_dir / "attachments.json").write_text(
                json.dumps(attachments_info, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("Информация о вложениях сохранена: attachments.json")

        logger.info(f"Основные данные страницы {page_id} сохранены")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных страницы {page_id}: {str(e)}")
        return False


def _export_page(
    page: "_Page",
    page_id: int,
    output_dir: Path,
    timeout_sec: int,
    logger: logging.Logger,
) -> bool:
    """Export page with attachments (with timeout), optionally copy to output_dir."""
    from confluence_markdown_exporter.utils.app_data_store import set_setting

    try:
        logger.info("Начинаем экспорт страницы...")
        safe_title = page.title[:50].replace("/", "_").replace("\\", "_")
        export_dir = output_dir / f"page_{page_id}_{safe_title}" / "export"
        export_dir.mkdir(parents=True, exist_ok=True)

        set_setting("export.output_path", str(export_dir))

        def do_export() -> bool:
            page.export()
            return True

        success = _run_with_timeout(do_export, timeout_sec, logger)
        if success is None:
            logger.warning("Таймаут при экспорте страницы")
            return False

        export_path = getattr(page, "export_path", None)
        if export_path and Path(export_path).exists():
            try:
                for fp in Path(export_path).rglob("*"):
                    if fp.is_file():
                        rel = fp.relative_to(export_path)
                        dest = export_dir / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(fp, dest)
                logger.info(f"Экспортированные файлы скопированы в: {export_dir}")
            except Exception as e:
                logger.warning(f"Ошибка при копировании экспортированных файлов: {str(e)}")
        else:
            # Files were written to get_settings().export.output_path (export_dir)
            logger.info(f"Экспорт сохранен в: {export_dir}")
        return True
    except Exception:
        logger.exception(f"Ошибка при экспорте страницы {page_id}")
        return False
    finally:
        # Restore export path to output_dir (client was initialized with it)
        set_setting("export.output_path", str(output_dir))


def _process_page(
    client: SmConfluenceTools,
    page_id: int,
    output_dir: Path,
    timeout_sec: int,
    log_level: str,
) -> bool:
    """Full cycle: parse, save data, export. Returns True if page was loaded and data saved."""
    logger = logging.getLogger("sm_confluence_tools.cli")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    logger.info(f"=== Начинаем обработку страницы {page_id} ===")

    def create_page() -> "_Page":
        return client.Page.from_id(page_id)

    page = _run_with_timeout(create_page, timeout_sec, logger)
    if page is None:
        logger.error("Не удалось получить страницу. Прерываем обработку.")
        return False

    logger.info(f"Страница найдена: '{page.title}' (ID: {page.id})")
    logger.info(f"Пространство: {page.space}")
    logger.info(f"Количество предков: {len(page.ancestors)}")
    logger.info(f"Количество меток: {len(page.labels)}")
    logger.info(f"Количество вложений: {len(page.attachments)}")

    if not _save_page_data(page, page_id, output_dir, timeout_sec, logger):
        logger.error("Не удалось сохранить данные страницы.")
        return False

    try:
        if not _export_page(page, page_id, output_dir, timeout_sec, logger):
            logger.warning("Экспорт страницы завершился с ошибкой, но основные данные сохранены.")
    except Exception as e:
        logger.warning(f"Ошибка при экспорте: {str(e)}")

    logger.info(f"=== Обработка страницы {page_id} завершена ===")
    return True


def _run_config_menu() -> int:
    """Launch confluence-markdown-exporter config menu. Returns exit code."""
    cmd = shutil.which("confluence-markdown-exporter")
    if not cmd:
        # Same venv: Scripts/confluence-markdown-exporter[.exe] next to python
        scripts_dir = Path(sys.executable).resolve().parent
        for name in ("confluence-markdown-exporter.exe", "confluence-markdown-exporter"):
            candidate = scripts_dir / name
            if candidate.exists():
                cmd = str(candidate)
                break
    if not cmd:
        print(
            "Error: confluence-markdown-exporter не найден."
            " Установите: pip install confluence-markdown-exporter"
        )
        return 1
    try:
        return subprocess.run(
            [cmd, "config"],
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
        ).returncode
    except Exception as e:
        print(f"Error: не удалось запустить меню настроек: {e}")
        return 1


def main() -> None:
    """Export page with attachments (sm-cf-export command)."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Экспорт страниц и вложений из Confluence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  sm-cf-export 1222798993
  sm-cf-export "https://confluence.app.local/pages/viewpage.action?pageId=1222798993"
  sm-cf-export --page-id 1222798993 --timeout 60 --log-level DEBUG
  sm-cf-export --page-id 1187947337 --timeout 10 --output-dir ./conf-export

Настройки:
  sm-cf-export config
        """,
    )
    parser.add_argument(
        "page_id_or_url",
        nargs="?",
        default=None,
        help="ID страницы, URL страницы или 'config' для настройки (меню в командной строке)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Таймаут операций в секундах (по умолчанию: 60)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./conf-export",
        help="Директория для сохранения результатов (по умолчанию: ./conf-export)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Уровень логирования (по умолчанию: INFO)",
    )
    args = parser.parse_args()

    page_arg: Optional[str] = args.page_id_or_url
    if page_arg is None:
        print("Error: Укажите ID страницы, URL или 'config'")
        print("""
Usage:
       sm-cf-export [--timeout N] [--output-dir DIR] [--log-level LEVEL] [page_id_or_url]
       sm-cf-export config
        """.strip())
        sys.exit(1)

    if page_arg.strip().lower() == "config":
        sys.exit(_run_config_menu())

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("sm_confluence_tools.cli")

    confluence_token = os.getenv("CONFLUENCE_TOKEN")
    jira_token = os.getenv("JIRA_TOKEN")
    if not confluence_token:
        print("Error: Please set CONFLUENCE_TOKEN environment variable")
        print("You can copy .env.example to .env and fill in your credentials")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"sm_cf_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(getattr(logging, args.log_level.upper()))
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(file_handler)

    client = SmConfluenceTools(
        confluence_token=confluence_token,
        jira_token=jira_token,
        output_path=str(output_dir),
    )

    try:
        page_id_int = int(page_arg)
        page_id = page_id_int
    except ValueError:
        page = client.Page.from_url(page_arg)
        page_id = page.id

    success = _process_page(
        client,
        page_id,
        output_dir,
        timeout_sec=args.timeout,
        log_level=args.log_level,
    )

    if success:
        print(f"\n[SUCCESS] Парсинг страницы {page_id} завершен!")
        print(f"[INFO] Результаты сохранены в: {output_dir}")
        print(f"[INFO] Логи сохранены в: {log_file}")
        sys.exit(0)
    else:
        print(f"\n[ERROR] Ошибка при парсинге страницы {page_id}")
        print(f"[INFO] Подробности в логах: {log_file}")
        print(f"[INFO] Попробуйте увеличить таймаут: --timeout {args.timeout * 2}")
        sys.exit(1)
