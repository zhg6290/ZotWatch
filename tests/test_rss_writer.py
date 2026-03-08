"""Unit tests for src/rss_writer.py – validates RSS namespace and metadata output."""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from src.models import RankedWork
from src.rss_writer import write_rss

_DC_NS = "http://purl.org/dc/elements/1.1/"
_PRISM_NS = "http://prismstandard.org/namespaces/basic/2.0/"


def _make_work(**kwargs) -> RankedWork:
    defaults = dict(
        source="test",
        identifier="arxiv:2401.00001",
        title="Test Paper Title",
        abstract="An abstract.",
        authors=["Alice Smith", "Bob Jones"],
        doi="10.1234/test.2024.001",
        url="https://arxiv.org/abs/2401.00001",
        published=datetime(2024, 1, 15, tzinfo=timezone.utc),
        venue="Nature",
        metrics={},
        extra={},
        score=0.9,
        similarity=0.8,
        recency_score=0.7,
        metric_score=0.5,
        author_bonus=0.1,
        venue_bonus=0.1,
        label="top",
    )
    defaults.update(kwargs)
    return RankedWork(**defaults)


def _write_and_read(works, **kwargs) -> tuple[str, ET.Element]:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = write_rss(works, Path(tmpdir) / "feed.xml", **kwargs)
        raw = path.read_text(encoding="utf-8")
        tree = ET.parse(str(path))
    return raw, tree.getroot()


class TestRssNamespaces:
    def test_root_declares_dc_namespace(self):
        raw, _ = _write_and_read([_make_work()])
        assert 'xmlns:dc="http://purl.org/dc/elements/1.1/"' in raw

    def test_root_declares_prism_namespace(self):
        raw, _ = _write_and_read([_make_work()])
        assert 'xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/"' in raw

    def test_no_auto_generated_ns_prefix(self):
        raw, _ = _write_and_read([_make_work()])
        assert "ns0:" not in raw
        assert "ns1:" not in raw


class TestRssDcCreator:
    def test_dc_creator_present_for_each_author(self):
        work = _make_work(authors=["Alice Smith", "Bob Jones"])
        raw, root = _write_and_read([work])
        creators = root.findall(f"./channel/item/{{{_DC_NS}}}creator")
        assert len(creators) == 2
        assert creators[0].text == "Alice Smith"
        assert creators[1].text == "Bob Jones"

    def test_no_dc_creator_when_no_authors(self):
        work = _make_work(authors=[])
        raw, root = _write_and_read([work])
        creators = root.findall(f"./channel/item/{{{_DC_NS}}}creator")
        assert creators == []


class TestRssPrismPublicationName:
    def test_prism_publication_name_present(self):
        work = _make_work(venue="Nature")
        raw, root = _write_and_read([work])
        pub_names = root.findall(f"./channel/item/{{{_PRISM_NS}}}publicationName")
        assert len(pub_names) == 1
        assert pub_names[0].text == "Nature"

    def test_category_also_present_for_venue(self):
        work = _make_work(venue="Nature")
        raw, root = _write_and_read([work])
        categories = root.findall("./channel/item/category")
        assert any(c.text == "Nature" for c in categories)

    def test_no_prism_publication_name_when_no_venue(self):
        work = _make_work(venue=None)
        raw, root = _write_and_read([work])
        pub_names = root.findall(f"./channel/item/{{{_PRISM_NS}}}publicationName")
        assert pub_names == []


class TestRssPrismDoi:
    def test_prism_doi_present_when_doi_exists(self):
        work = _make_work(doi="10.1234/test.2024.001")
        raw, root = _write_and_read([work])
        dois = root.findall(f"./channel/item/{{{_PRISM_NS}}}doi")
        assert len(dois) == 1
        assert dois[0].text == "10.1234/test.2024.001"

    def test_no_prism_doi_when_doi_absent(self):
        work = _make_work(doi=None)
        raw, root = _write_and_read([work])
        dois = root.findall(f"./channel/item/{{{_PRISM_NS}}}doi")
        assert dois == []


class TestRssGuid:
    def test_guid_non_url_has_is_permalink_false(self):
        work = _make_work(identifier="arxiv:2401.00001")
        raw, root = _write_and_read([work])
        guid_el = root.find("./channel/item/guid")
        assert guid_el is not None
        assert guid_el.get("isPermaLink") == "false"

    def test_guid_url_has_no_is_permalink_attribute(self):
        work = _make_work(identifier="https://arxiv.org/abs/2401.00001")
        raw, root = _write_and_read([work])
        guid_el = root.find("./channel/item/guid")
        assert guid_el is not None
        assert guid_el.get("isPermaLink") is None


class TestRssValidStructure:
    def test_utf8_xml_declaration_present(self):
        raw, _ = _write_and_read([_make_work()])
        assert raw.startswith("<?xml")
        assert "utf-8" in raw.lower()

    def test_empty_feed_writes_valid_xml(self):
        raw, root = _write_and_read([])
        assert root.tag == "rss"
        assert root.find("channel") is not None
        assert root.findall("./channel/item") == []

    def test_multiple_items(self):
        works = [_make_work(identifier=f"arxiv:240{i}.0000{i}", title=f"Paper {i}") for i in range(3)]
        raw, root = _write_and_read(works)
        items = root.findall("./channel/item")
        assert len(items) == 3
