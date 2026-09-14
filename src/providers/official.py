"""Official statistical-agency CSV fetches (no API key)."""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

import pandas as pd

from src.providers.base import ErrorCode, FetchResult

log = logging.getLogger(__name__)

TIMEOUT_S = 30
USER_AGENT = "dsbd-dashboard/1.0 (+https://github.com/)"
ERA_OFFSET = {"M": 1867, "T": 1911, "S": 1925, "H": 1988, "R": 2018}
ERA_RE = re.compile(r"^([MTSHR])(\d+)\.(\d+)\.(\d+)$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
YYYYMM_RE = re.compile(r"^(\d{4})(\d{2})$")
BOE_IADB = (
    "https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp"
    "?csv.x=yes&Datefrom={start}&Dateto={end}&SeriesCodes={code}"
    "&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N"
)
BOJ_API = (
    "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
    "?format=json&lang=jp&db={db}&startDate={start}&endDate={end}&code={code}"
)


ISM_YM_VALUE_RE = re.compile(
    r'data-original-value="(\d{4})年(\d{2})月"[^>]*>.*?</td>\s*'
    r'<td[^>]*data-original-value="([0-9]+(?:\.[0-9]+)?)"',
    re.S,
)


class OfficialProvider:
    """Fetches official CSVs (MoF / Bundesbank / BoE / Statistics Bureau CPI),
    BOJ time-series API (Tankan), and the ISM manufacturing PMI HTML table."""

    name = "official"

    def fetch(self, inst: dict) -> FetchResult:
        fmt = inst.get("official_format")
        if not fmt:
            return FetchResult(ErrorCode.NO_SYMBOL, error="official_no_format")
        series = _fetch_series(inst)
        if series is None or series.empty:
            return FetchResult(ErrorCode.NO_DATA, error="official_no_data")
        resolved = inst.get("official_id") or fmt
        return FetchResult(ErrorCode.OK, series, resolved_symbol=resolved)


def _fetch_series(inst: dict) -> pd.Series | None:
    fmt = inst.get("official_format")
    urls = list(inst.get("official_urls") or [])
    if inst.get("official_url"):
        urls.append(inst["official_url"])
    if fmt == "boe_iadb":
        code = inst.get("official_series") or inst.get("official_id")
        if not code:
            return None
        urls = [_boe_url(code)]
    if fmt == "boj_api":
        code = inst.get("official_series") or inst.get("official_id")
        if not code:
            return None
        urls = [_boj_api_url(inst, code)]
    if not urls:
        return None

    parts: list[pd.Series] = []
    for url in urls:
        raw = _get_bytes(url)
        if raw is None:
            raw = _get_bytes(url)
        if raw is None:
            continue
        parsed = _parse(fmt, raw, inst)
        if parsed is not None and not parsed.empty:
            parts.append(parsed)
    if not parts:
        return None
    s = pd.concat(parts)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s if not s.empty else None


def _parse(fmt: str, raw: bytes, inst: dict) -> pd.Series | None:
    if fmt == "mof_jgb":
        return _parse_mof_jgb(raw, inst.get("official_column") or "10年")
    if fmt == "bundesbank_csv":
        return _parse_bundesbank_csv(raw)
    if fmt == "boe_iadb":
        return _parse_boe_iadb(raw, inst.get("official_series") or inst.get("official_id"))
    if fmt == "stat_cpi":
        return _parse_stat_cpi(raw, inst.get("official_column") or "総合")
    if fmt == "ism_html":
        return _parse_ism_html(raw)
    if fmt == "boj_api":
        return _parse_boj_api(raw, inst.get("official_series") or inst.get("official_id"))
    log.warning("unknown official_format %s", fmt)
    return None


def _boj_api_url(inst: dict, code: str, years: int = 8) -> str:
    db = inst.get("official_db") or "CO"
    today = date.today()
    start_year = today.year - years
    start = f"{start_year}01"
    end_q = (today.month - 1) // 3 + 1
    end = f"{today.year}{end_q:02d}"
    return BOJ_API.format(
        db=urllib.parse.quote(str(db)),
        start=start,
        end=end,
        code=urllib.parse.quote(code),
    )


def _parse_boj_api(raw: bytes, series_code: str | None) -> pd.Series | None:
    """Parse BOJ time-series search API JSON (getDataCode)."""
    try:
        payload = json.loads(raw.decode("utf-8-sig", errors="replace"))
    except json.JSONDecodeError:
        return None
    if int(payload.get("STATUS") or 0) != 200:
        log.warning("boj api status %s", payload.get("STATUS"))
        return None
    rows = payload.get("RESULTSET") or []
    chosen = None
    for row in rows:
        if series_code and row.get("SERIES_CODE") != series_code:
            continue
        chosen = row
        break
    if chosen is None and rows:
        chosen = rows[0]
    if not chosen:
        return None
    values_block = chosen.get("VALUES") or {}
    dates_raw = values_block.get("SURVEY_DATES") or []
    vals_raw = values_block.get("VALUES") or []
    dates: list[pd.Timestamp] = []
    values: list[float] = []
    for raw_date, raw_val in zip(dates_raw, vals_raw):
        if raw_val is None:
            continue
        ts = _parse_yyyyqq(raw_date)
        val = _to_float(str(raw_val)) if not isinstance(raw_val, (int, float)) else float(raw_val)
        if ts is None or val is None:
            continue
        dates.append(ts)
        values.append(val)
    return _series(dates, values)


def _parse_yyyyqq(value) -> pd.Timestamp | None:
    """Map BOJ YYYYQQ (quarter) to the survey month (Mar/Jun/Sep/Dec)."""
    text = str(value or "").strip()
    if len(text) != 6 or not text.isdigit():
        return None
    year, quarter = int(text[:4]), int(text[4:6])
    if quarter < 1 or quarter > 4:
        return None
    try:
        return pd.Timestamp(year, quarter * 3, 1)
    except ValueError:
        return None


def _boe_url(code: str, years: int = 2) -> str:
    start = (date.today() - timedelta(days=365 * years + 7)).strftime("%d/%b/%Y")
    end = (date.today() + timedelta(days=1)).strftime("%d/%b/%Y")
    return BOE_IADB.format(start=start, end=end, code=urllib.parse.quote(code))


def parse_jp_era_date(text: str) -> pd.Timestamp | None:
    m = ERA_RE.match(text.strip())
    if not m:
        return None
    era, year, month, day = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
    try:
        return pd.Timestamp(ERA_OFFSET[era] + year, month, day)
    except ValueError:
        return None


def _parse_mof_jgb(raw: bytes, column: str) -> pd.Series | None:
    text = _decode_jp(raw)
    reader = csv.reader(io.StringIO(text))
    header: list[str] | None = None
    col_idx: int | None = None
    dates: list[pd.Timestamp] = []
    values: list[float] = []
    for row in reader:
        if not row:
            continue
        cells = [c.strip() for c in row]
        if header is None and cells and (cells[0] == "基準日" or "10年" in cells):
            header = cells
            try:
                col_idx = header.index(column)
            except ValueError:
                log.warning("mof column %s not found in %s", column, header)
                return None
            continue
        if header is None or col_idx is None:
            continue
        ts = parse_jp_era_date(cells[0])
        if ts is None or col_idx >= len(cells):
            continue
        val = _to_float(cells[col_idx])
        if val is None:
            continue
        dates.append(ts)
        values.append(val)
    return _series(dates, values)


def _parse_bundesbank_csv(raw: bytes) -> pd.Series | None:
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    dates: list[pd.Timestamp] = []
    values: list[float] = []
    for row in reader:
        if not row:
            continue
        key = row[0].strip().lstrip("\ufeff")
        if not ISO_DATE_RE.match(key) or len(row) < 2:
            continue
        val = _to_float(row[1])
        if val is None:
            continue
        dates.append(pd.Timestamp(key))
        values.append(val)
    return _series(dates, values)


def _parse_stat_cpi(raw: bytes, column: str) -> pd.Series | None:
    """Statistics Bureau of Japan nationwide CPI item CSV (zmiYYYYaa.csv).

    Header row starts with 類・品目; monthly rows are YYYYMM in the first column.
    """
    text = _decode_jp(raw)
    reader = csv.reader(io.StringIO(text))
    header: list[str] | None = None
    col_idx: int | None = None
    dates: list[pd.Timestamp] = []
    values: list[float] = []
    for row in reader:
        if not row:
            continue
        cells = [c.strip() for c in row]
        if header is None and cells and (cells[0] in {"類・品目", "Group/Item"} or column in cells):
            header = cells
            try:
                col_idx = header.index(column)
            except ValueError:
                log.warning("stat cpi column %s not found in %s", column, header[:8])
                return None
            continue
        if header is None or col_idx is None:
            continue
        ts = _parse_yyyymm(cells[0])
        if ts is None or col_idx >= len(cells):
            continue
        val = _to_float(cells[col_idx])
        if val is None:
            continue
        dates.append(ts)
        values.append(val)
    return _series(dates, values)


def _parse_yyyymm(text: str) -> pd.Timestamp | None:
    m = YYYYMM_RE.match((text or "").strip())
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if month < 1 or month > 12:
        return None
    try:
        return pd.Timestamp(year, month, 1)
    except ValueError:
        return None


def _parse_ism_html(raw: bytes) -> pd.Series | None:
    """Parse ISM manufacturing PMI monthly table (YYYY年MM月 / value cells)."""
    text = raw.decode("utf-8-sig", errors="replace")
    dates: list[pd.Timestamp] = []
    values: list[float] = []
    for year_s, month_s, val_s in ISM_YM_VALUE_RE.findall(text):
        year, month = int(year_s), int(month_s)
        if month < 1 or month > 12:
            continue
        try:
            ts = pd.Timestamp(year, month, 1)
            val = float(val_s)
        except ValueError:
            continue
        dates.append(ts)
        values.append(val)
    return _series(dates, values)


def _parse_boe_iadb(raw: bytes, series_code: str | None) -> pd.Series | None:
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header: list[str] | None = None
    col_idx = 1
    dates: list[pd.Timestamp] = []
    values: list[float] = []
    for row in reader:
        if not row:
            continue
        cells = [c.strip() for c in row]
        if header is None:
            if cells and "DATE" in cells[0].upper():
                header = cells
                if series_code and series_code in header:
                    col_idx = header.index(series_code)
                elif len(header) > 1:
                    col_idx = 1
            continue
        if col_idx >= len(cells):
            continue
        ts = _parse_boe_date(cells[0])
        val = _to_float(cells[col_idx])
        if ts is None or val is None:
            continue
        dates.append(ts)
        values.append(val)
    return _series(dates, values)


def _parse_boe_date(text: str) -> pd.Timestamp | None:
    for fmt in ("%d %b %Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return pd.Timestamp(pd.to_datetime(text, format=fmt))
        except (ValueError, TypeError):
            continue
    try:
        return pd.Timestamp(pd.to_datetime(text, dayfirst=True))
    except (ValueError, TypeError):
        return None


def _series(dates: list[pd.Timestamp], values: list[float]) -> pd.Series | None:
    if not values:
        return None
    s = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s if not s.empty else None


def _to_float(text: str) -> float | None:
    t = (text or "").strip()
    if not t or t in {".", "-", "NA", "n/a", "N/A"}:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _decode_jp(raw: bytes) -> str:
    for enc in ("cp932", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("cp932", errors="replace")


def _get_bytes(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/csv,*/*"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        log.warning("official HTTP %s for %s", e.code, url)
        return None
    except (urllib.error.URLError, TimeoutError, OSError):
        log.warning("official request failed for %s", url)
        return None
