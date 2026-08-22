# -*- coding: utf-8 -*-
"""Поиск учебных материалов в открытых базах — легально, без пиратства.

- arXiv (export.arxiv.org) — научные статьи, открытый доступ:
  PDF скачивается и отправляется файлом.
- Open Library (openlibrary.org) — книги: карточка, автор, год, ссылка.
  Полный текст присылаем только когда он официально открыт
  (public domain / has_fulltext).

Ключей API не нужно. Функции парсинга — чистые, покрыты тестами.
"""
from __future__ import annotations

import logging
import ssl
import xml.etree.ElementTree as ET

import aiohttp

logger = logging.getLogger(__name__)


def _ssl_context() -> ssl.SSLContext | bool:
    """Надёжная проверка сертификатов: через certifi, если он есть
    (на Windows/минимальных образах системного хранилища может не быть)."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return True

ARXIV_API = "http://export.arxiv.org/api/query"
OL_API = "https://openlibrary.org/search.json"
NS = {"a": "http://www.w3.org/2005/Atom"}
MAX_PDF_BYTES = 25 * 1024 * 1024  # 25 МБ — страховка от гигантских файлов


# =================== ЧИСТЫЕ ФУНКЦИИ ПАРСИНГА (тестируются) ===================

def parse_arxiv(xml_text: str) -> list[dict]:
    """Ответ arXiv API (Atom XML) → список статей."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    results = []
    for entry in root.findall("a:entry", NS):
        title = (entry.findtext("a:title", "", NS) or "").strip()
        pdf_url = ""
        for link in entry.findall("a:link", NS):
            if link.get("type") == "application/pdf" or link.get("title") == "pdf":
                pdf_url = link.get("href") or ""
                break
        authors = [a.findtext("a:name", "", NS) for a in entry.findall("a:author", NS)]
        published = (entry.findtext("a:published", "", NS) or "")[:4]
        summary = (entry.findtext("a:summary", "", NS) or "").strip()
        if title and pdf_url:
            results.append({
                "title": " ".join(title.split())[:120],
                "authors": ", ".join(a for a in authors if a)[:80],
                "year": published,
                "pdf_url": pdf_url,
                "summary": " ".join(summary.split())[:300],
            })
    return results[:5]


def parse_openlibrary(json_data: dict) -> list[dict]:
    """Ответ Open Library search.json → список книг."""
    results = []
    for doc in (json_data.get("docs") or [])[:5]:
        title = doc.get("title") or ""
        if not title:
            continue
        year = doc.get("first_publish_year")
        author = ", ".join(doc.get("author_name") or [])[:80]
        olid = ""
        for key in (doc.get("cover_edition_key"), doc.get("edition_key", [None])[0] if doc.get("edition_key") else None):
            if key:
                olid = key
                break
        results.append({
            "title": title[:120],
            "authors": author or "—",
            "year": str(year) if year else "—",
            "link": f"https://openlibrary.org{doc.get('key', '')}",
            "has_fulltext": bool(doc.get("has_fulltext")),
            "cover": (f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-M.jpg"
                      if doc.get("cover_i") else None),
        })
    return results


# =================== СЕТЕВЫЕ ЗАПРОСЫ ===================

async def _fetch(url: str, params: dict | None = None,
                 timeout: int = 20) -> tuple[int, bytes]:
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout),
        connector=aiohttp.TCPConnector(ssl=_ssl_context()),
    ) as session:
        async with session.get(url, params=params) as resp:
            return resp.status, await resp.read()


async def search_articles(query: str) -> list[dict]:
    """Научные статьи arXiv по запросу."""
    try:
        status, body = await _fetch(ARXIV_API, {
            "search_query": f"all:{query}",
            "start": 0, "max_results": 5,
        })
        if status != 200:
            return []
        return parse_arxiv(body.decode("utf-8", errors="replace"))
    except Exception as e:
        logger.warning("arxiv search failed: %s", e)
        return []


async def search_books(query: str) -> list[dict]:
    try:
        status, body = await _fetch(OL_API, {"q": query, "limit": 5})
        if status != 200:
            return []
        import json
        return parse_openlibrary(json.loads(body))
    except Exception as e:
        logger.warning("openlibrary search failed: %s", e)
        return []


async def download_pdf(url: str) -> bytes | None:
    """Скачать PDF (до 25 МБ). None — слишком большой или ошибка."""
    try:
        status, data = await _fetch(url, timeout=60)
        if status != 200 or not data.startswith(b"%PDF") or len(data) > MAX_PDF_BYTES:
            if status == 200 and len(data) > MAX_PDF_BYTES:
                logger.info("pdf too large: %s bytes", len(data))
            return None
        return data
    except Exception as e:
        logger.warning("pdf download failed: %s", e)
        return None
