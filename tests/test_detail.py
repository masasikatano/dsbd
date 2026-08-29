"""Tests for detail page assets."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_detail_html_exists_and_references_common_js():
    detail = ROOT / "docs" / "detail.html"
    assert detail.is_file()
    text = _read(detail)
    assert 'src="common.js"' in text
    assert 'id="chart"' in text


def test_common_js_exists_and_exports_expected_functions():
    common = ROOT / "docs" / "common.js"
    assert common.is_file()
    text = _read(common)
    assert "function drawLine" in text
    assert "function bindHover" in text
    assert "function bindClick" in text
    assert "function lastClass" in text
    assert "function strokeColor" in text
    assert "encodeURIComponent" in text


def test_index_html_loads_common_js_and_has_clickable_sparks():
    index = ROOT / "docs" / "index.html"
    text = _read(index)
    assert 'src="common.js"' in text
    assert "bindClick" in text
    assert "cursor: pointer" in text
