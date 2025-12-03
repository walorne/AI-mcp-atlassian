import os
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, unquote, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict
from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan
from atlassian import Confluence
from dotenv import load_dotenv
from tqdm import tqdm
import logging
import json

load_dotenv()

BASE_URL = os.getenv("CONFLUENCE_BASE_URL")
API_TOKEN = os.getenv("CONFLUENCE_PERSONAL_ACCESS_TOKEN")
VERIFY_SSL = os.getenv("CONFLUENCE_VERIFY_SSL", "True").lower() in ("true", "1", "yes")
ES_HOST = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
ES_INDEX = os.getenv("ES_INDEX_NAME", "confluence-pages")
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "8"))

confluence = Confluence(
    url=BASE_URL,
    token=API_TOKEN,
    verify_ssl=VERIFY_SSL
)
es = Elasticsearch(ES_HOST)

# logging.basicConfig(
#     level=logging.ERROR,  #INFO Или DEBUG, WARNING, ERROR
#     format="%(asctime)s [%(levelname)s] %(message)s",
#     handlers=[
#         logging.FileHandler("link_extractor.log"),  # путь к лог-файлу        
#     ]
# )

# logger = logging.getLogger(__name__)

def filter_links(raw_links):
    """
    Оставляет в списке только элементы, у которых block содержит
    'incoming links' или 'outgoing links' (регистронезависимо).
    
    Аргументы:
      raw_links: List[Dict] с ключами 'block', 'text', 'href'
      
    Возвращает:
      filtered_links: List[Dict] тех же структур, но отфильтрованные.
    """
    filtered = []
    for link in raw_links:
        block = link.get("block", "").lower()
        if "incoming links" in block or "outgoing links" in block:
            filtered.append(link)
    return filtered

def transform_links(filtered_links, internal_host="confluence.app.local"):
    result = []
    for link in filtered_links:
        block = link["block"].lower()
        href = link["href"]
        text = link["text"] or None

        # 1) Определяем направление
        if "incoming links" in block:
            direction = "incoming"
        elif "outgoing links" in block:
            host = urlparse(href).netloc.lower()
            direction = "outgoing_internal" if internal_host in host else "outgoing_external"
        else:
            # пропускаем, если вдруг сюда попало что-то чужое
            continue

        # 2) Парсим page_id, space и title
        page_id = None
        space = None
        title = None

        parsed = urlparse(href)
        path = parsed.path

        if path.endswith("/viewpage.action"):
            # /pages/viewpage.action?pageId=12345
            qs = parse_qs(parsed.query)
            page_id = qs.get("pageId", [None])[0]
            title = text

        elif "/display/" in path:
            # /display/SPACE/TITLE+WITH+PLUSES
            disp = path.split("/display/", 1)[1]
            parts = disp.split("/", 1)
            space = parts[0]
            # декодируем + и %XX
            raw_title = parts[1] if len(parts) > 1 else ""
            title = unquote(raw_title.replace("+", " "))

        else:
            # неизвестный формат — используем просто текст ссылки
            title = text

        # 3) Собираем в словарь
        result.append({
            "page_id":  page_id,
            "space":    space,
            "title":    title,
            "href":     href,
            "direction": direction
        })

    return result

def get_page_metadata(confluence, page_id: str):
    page = confluence.get_page_by_id(page_id, expand='space,version')
    space_key = page.get('space', {}).get('key')
    title     = page.get('title')
    return space_key, title

def get_page_id_by_title(confluence, space: str, title: str) -> Optional[str]:
    page = confluence.get_page_by_title(space, title)
    return page.get('id') if page else None

def safe_get_page_id_by_title(confluence: Confluence, space: str, title: str) -> Optional[str]:
    try:
        page = confluence.get_page_by_title(space, title)
        return page.get('id') if page else None
    except Exception as e:
        #logger.error("Не удалось получить страницу '{title}' в пространстве '{space}': {e}")
        # print(f"Не удалось получить страницу '{title}' в пространстве '{space}': {e}")
        return None

def enrich_links(confluence, all_links):
    enriched = []
    for link in all_links:
        pid   = link['page_id']
        space = link['space']
        title = link['title']
        href  = link['href']
        dirc  = link['direction']

        if dirc in ("incoming", "outgoing_internal"):
            if pid and (not space or not title):
                try:
                    fetched_space, fetched_title = get_page_metadata(confluence, pid)
                    space = space or fetched_space
                    title = title or fetched_title
                except Exception:
                    pass
            if not pid and space and title:
                try:
                    pid = get_page_id_by_title(confluence, space, title)
                except Exception:
                    pass
        else:
            pid   = hashlib.md5(href.encode('utf-8')).hexdigest()
            space = 'outgoing_external'

        # 🛠 Гарантируем, что всё — строки, не списки
        enriched.append({
            "page_id":   str(pid) if pid is not None else None,
            "space":     str(space) if space is not None else None,
            "title":     str(title) if title is not None else None,
            "href":      str(href) if href is not None else None,
            "direction": str(dirc) if dirc is not None else None
        })
    return enriched

def parse_links(page_id: str) -> list[dict]:

    confluence = Confluence(
        url=BASE_URL,
        token=API_TOKEN,
        verify_ssl=VERIFY_SSL
    )

    # ----------------------------------------------
    # Prepare request session
    # ----------------------------------------------
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {API_TOKEN}",
        "Accept": "application/json"
    })
    session.verify = VERIFY_SSL

    info_url = f"{BASE_URL}/pages/viewinfo.action"
    resp_info = session.get(info_url, params={"pageId": page_id})
    resp_info.raise_for_status()
    page_info_html = resp_info.text

    soup = BeautifulSoup(page_info_html, 'lxml')
    links = []

    for a in soup.select('a[href]'):
        # Абсолютный URL и текст ссылки
        href = urljoin(resp_info.url, a['href'])
        text = a.get_text(strip=True)

        # Ищем ближайший контейнер-панель
        panel = a.find_parent("div", class_="basicPanelContainer")
        if panel:
            # Извлекаем заголовок этой панели
            title_div = panel.find("div", class_="basicPanelTitle")
            block = title_div.get_text(strip=True) if title_div else "[без названия блока]"
        else:
            block = "[вне панели]"

        links.append({
            "block": block,
            "text":  text or "[пустой текст]",
            "href":  href
        })

    filtered_links = filter_links(links)
    all_links = transform_links(filtered_links)

    # --- 3. Обогащаем: дополняем через API и хешируем внешние ---
    final_links = enrich_links(confluence, all_links)
    # final_links содержит уже гарантированно валидные page_id/space/title и направление.
    #print(f"[DEBUG] Parsed {len(links)} links, {len(filtered_links)} filtered, {len(final_links)} enriched")
    return final_links

def update_page_links(doc_id: str, links: List[Dict]):
     # Debug output: inspect first few link dicts
    # sample = links[:3]
    # debug_str = json.dumps(sample, ensure_ascii=False, indent=2)
    # print(f"[DEBUG] Updating doc {doc_id} with links (sample up to 3): {debug_str}")
    # Actual update
    es.update(index=ES_INDEX, id=doc_id, body={
        "doc": {
            "page_links": links,
            "processed_steps": "LINKED"
        }
    })

def load_updated_page_ids(space_key: Optional[str] = None) -> List[str]:
    query = {
        "bool": {
            "must": [
                {"term": {"processed_steps": "UPLOADED"}}
            ]
        }
    }
    if space_key:
        query["bool"]["must"].append({"term": {"space_key": space_key}})

    hits = scan(
        es,
        index=ES_INDEX,
        query={"query": query},
        # _source=["page_id"]
    )
    return [h["_id"] for h in hits]

def process_all(space_key: Optional[str] = None):
    doc_ids = load_updated_page_ids(space_key)
    print(f"Found {len(doc_ids)} UPDATED pages")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for doc_id in doc_ids:
            futures[executor.submit(parse_links, doc_id)] = doc_id

        for future in tqdm(as_completed(futures), total=len(futures), desc="Parsing links"):
            doc_id = futures[future]
            try:
                links = future.result()
                update_page_links(doc_id, links)
            except Exception as e:
                print(f"Failed to parse/update page {doc_id}: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parse and store page links in Elasticsearch")
    parser.add_argument("--space", help="Optional space_key to restrict pages", default=None)
    args = parser.parse_args()

    process_all(args.space)
