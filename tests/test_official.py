"""Tests for official CSV parsers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.providers.base import ErrorCode
from src.providers.official import (
    OfficialProvider,
    _parse_boe_iadb,
    _parse_bundesbank_csv,
    _parse_ism_html,
    _parse_mof_jgb,
    _parse_stat_cpi,
    parse_jp_era_date,
)


def test_parse_jp_era_date():
    assert parse_jp_era_date("R8.9.10").strftime("%Y-%m-%d") == "2026-09-10"
    assert parse_jp_era_date("H31.4.1").strftime("%Y-%m-%d") == "2019-04-01"
    assert parse_jp_era_date("S49.9.24").strftime("%Y-%m-%d") == "1974-09-24"
    assert parse_jp_era_date("not-a-date") is None


def test_parse_mof_jgb():
    csv = (
        "国債金利情報,,,,,,,,,,,,,,,(単位 : %)\n"
        "基準日,1年,2年,3年,4年,5年,6年,7年,8年,9年,10年,15年\n"
        "R8.8.31,1.5,1.7,1.8,2.0,2.2,2.3,2.4,2.6,2.7,2.943,3.5\n"
        "R8.9.10,1.55,1.82,1.95,2.12,2.24,2.35,2.48,2.64,2.78,2.92,3.46\n"
        "R8.9.11,-,-,-,-,-,-,-,-,-,-,-\n"
    ).encode("cp932")
    s = _parse_mof_jgb(csv, "10年")
    assert s is not None
    assert len(s) == 2
    assert float(s.loc["2026-09-10"]) == pytest.approx(2.92)


def test_parse_bundesbank_csv():
    csv = (
        '"",BBSSY.X,BBSSY.X_FLAGS\n'
        "Comment (in english),,\n"
        "2026-09-09,3.39,\n"
        "2026-09-10,3.45,\n"
        "2026-09-11,.,No value available\n"
    ).encode("utf-8")
    s = _parse_bundesbank_csv(csv)
    assert s is not None
    assert len(s) == 2
    assert float(s.iloc[-1]) == pytest.approx(3.45)


def test_parse_boe_iadb():
    csv = (
        "DATE,IUDMNPY\n"
        "08 Sep 2026,5.0979\n"
        "09 Sep 2026,5.1922\n"
    ).encode("utf-8")
    s = _parse_boe_iadb(csv, "IUDMNPY")
    assert s is not None
    assert len(s) == 2
    assert float(s.iloc[-1]) == pytest.approx(5.1922)


def test_parse_ism_html():
    html = """
    <tr><td data-original-value="2026年08月">2026年08月 </td>
        <td data-original-value="54.6">54.6 </td></tr>
    <tr><td data-original-value="2026年07月">2026年07月 </td>
        <td data-original-value="55.6">55.6 </td></tr>
    """.encode("utf-8")
    s = _parse_ism_html(html)
    assert s is not None
    assert len(s) == 2
    assert float(s.loc["2026-08-01"]) == pytest.approx(54.6)
    assert float(s.loc["2026-07-01"]) == pytest.approx(55.6)


def test_parse_stat_cpi():
    csv = (
        "類・品目,総合,食料\n"
        "Group/Item,All items,Food\n"
        "類・品目符号(Group/Item code),0001,0002\n"
        "202606,101.560,102.389\n"
        "202607,102.039,103.122\n"
        "202608,,\n"
    ).encode("cp932")
    s = _parse_stat_cpi(csv, "総合")
    assert s is not None
    assert len(s) == 2
    assert float(s.loc["2026-07-01"]) == pytest.approx(102.039)


def test_official_provider_no_format():
    result = OfficialProvider().fetch({})
    assert result.status == ErrorCode.NO_SYMBOL
    assert result.error == "official_no_format"


def test_official_provider_fetch_ok():
    csv = (
        "DATE,IUDMNPY\n"
        "09 Sep 2026,5.19\n"
    ).encode("utf-8")
    inst = {
        "official_format": "boe_iadb",
        "official_series": "IUDMNPY",
        "official_id": "IUDMNPY",
    }
    with patch("src.providers.official._get_bytes", return_value=csv):
        result = OfficialProvider().fetch(inst)
    assert result.is_ok()
    assert result.resolved_symbol == "IUDMNPY"
    assert float(result.series.iloc[-1]) == pytest.approx(5.19)
