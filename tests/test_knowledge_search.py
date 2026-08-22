# -*- coding: utf-8 -*-
"""Тесты поиска материалов: парсеры arXiv и Open Library."""
from services.knowledge_search import parse_arxiv, parse_openlibrary

ARXIV_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v1</id>
    <title>Attention Is All You  Need</title>
    <summary> The dominant sequence transduction models...</summary>
    <published>2024-01-15T00:00:00Z</published>
    <author><name>A. Author</name></author>
    <author><name>B. Author</name></author>
    <link href="http://arxiv.org/abs/2401.12345" rel="alternate"/>
    <link title="pdf" href="http://arxiv.org/pdf/2401.12345v1" type="application/pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.99999v1</id>
    <title>No PDF Here</title>
    <published>2023-05-05T00:00:00Z</published>
    <link href="http://arxiv.org/abs/2401.99999" rel="alternate"/>
  </entry>
</feed>"""

OL_SAMPLE = {
    "docs": [
        {
            "title": "Algebra",
            "author_name": ["I. M. Gelfand"],
            "first_publish_year": 1993,
            "key": "/works/OL123W",
            "has_fulltext": True,
            "cover_i": 555,
        },
        {"title": "", "key": "/works/OL9W"},
    ],
    "numFound": 2,
}


class TestArxivParser:
    def test_extracts_entry_with_pdf(self):
        items = parse_arxiv(ARXIV_SAMPLE)
        assert len(items) == 1                      # без PDF не попадает
        a = items[0]
        assert a["title"] == "Attention Is All You Need"  # склеил пробелы
        assert a["year"] == "2024"
        assert "A. Author" in a["authors"]
        assert a["pdf_url"].endswith("2401.12345v1")

    def test_bad_xml(self):
        assert parse_arxiv("не xml") == []


class TestOpenLibraryParser:
    def test_extracts_book(self):
        items = parse_openlibrary(OL_SAMPLE)
        assert len(items) == 1                      # пустой title отсеян
        b = items[0]
        assert b["title"] == "Algebra"
        assert b["year"] == "1993"
        assert b["link"] == "https://openlibrary.org/works/OL123W"
        assert b["has_fulltext"] is True
        assert "555" in (b["cover"] or "")

    def test_empty_docs(self):
        assert parse_openlibrary({"docs": []}) == []
        assert parse_openlibrary({}) == []
