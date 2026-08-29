# Architecture

## Overview

This is a static dashboard site for macro / ETF investment decisions. It fetches end-of-day market data from Yahoo Finance (primary), FRED (fallback / special series), and EODHD (symbols Yahoo does not serve daily), computes five metrics per instrument, and renders a single HTML page.

```
GitHub Actions (weekdays 21:30 UTC + manual)
  → python -m src.update
  → docs/data/latest.json
  → commit & push to main [skip ci]

GitHub Pages (main /docs)
  → docs/index.html fetches latest.json
  → renders tables and sparklines
```

## Directory Layout

```
config/instruments.yaml   # Source of truth for instruments
src/
  update.py               # Orchestration: config → fetch → derive → JSON
  compute.py              # Metric calculations and derived spreads
  providers/
    base.py               # Provider protocol, FetchResult, ErrorCode
    __init__.py           # Provider registry
    yahoo.py              # Yahoo Finance provider with batch cache
    fred.py               # FRED observations provider
    eodhd.py              # EODHD end-of-day provider
docs/
  index.html              # UI (single file, no build step)
  data/latest.json        # Generated snapshot
tests/                    # pytest suite
```

## Data Flow

1. `src.update.run()` loads `config/instruments.yaml`.
2. It builds a provider registry (`YahooProvider`, `FredProvider`, `EodhdProvider`).
3. It warms the Yahoo cache by batch-downloading all symbols that may be fetched through Yahoo.
4. For each non-derived instrument:
   - Resolve the provider by `provider` field (`yahoo` is default).
   - Call `provider.fetch(inst)` → `FetchResult`.
   - Apply provider-specific fallbacks (Yahoo → FRED, FRED → Yahoo) in the orchestrator, keeping providers decoupled.
   - Build an `ok` item with metrics + history, or a `missing` item with an error code.
5. For each derived instrument (`provider: derived`):
   - Try to compute a spread series from stored dependency series.
   - If series are unavailable, fall back to subtracting the latest values of the dependencies.
6. `build_payload()` produces `latest.json` with metadata, counts, sections, and items.

## Provider Interface

```python
class Provider(Protocol):
    name: str
    def fetch(self, inst: dict) -> FetchResult: ...

@dataclass(frozen=True)
class FetchResult:
    status: str                      # ErrorCode.OK or other
    series: pd.Series | None = None
    resolved_symbol: str | None = None
    error: str | None = None
```

Providers are registered in `src/providers/__init__.py`:

```python
def build_provider_registry() -> dict[str, Provider]:
    return {
        YahooProvider.name: YahooProvider(),
        FredProvider.name: FredProvider(),
        EodhdProvider.name: EodhdProvider(),
    }
```

## Metrics

For each instrument with a valid price / yield series:

- `last`: latest close
- `chg_1d_pct`: day-over-day change (%)
- `ytd_pct`: year-to-date change (%)
- `pos_52w_pct`: position within the last 252 sessions (%)
- `dev_200d_pct`: deviation from 200-session moving average (%)
- `vol_1y_pct`: annualized volatility from log returns (%)

Derived instruments (`us_2s10s`, `us_10s30s`) compute the spread between two underlying instruments.

## Failure Policy

- Per-instrument `try/except`; failures are logged and the row is kept with `status: missing`.
- UI shows "データなし" for missing rows but never removes the row.
- The job only fails when **all** instruments are missing (`ok_count == 0`).
- Missing API keys result in `missing` rows for the affected provider, not a hard failure.

## Frontend

`docs/index.html` is a single static file. It fetches `data/latest.json` and renders:

- A header with generation time and missing count banner.
- A grid of "must" priority cards with sparklines.
- Per-section tables with all instruments.

No build tools, bundlers, or external JS/CSS are used.

## Adding a New Instrument

1. Add an entry to `config/instruments.yaml` with:
   - `id`, `section`, `market`, `name`
   - `provider` (default `yahoo`)
   - `symbol` and optional `symbol_fallbacks`
   - `priority`, `unit`, optional `thresholds`, optional `note`
2. If the data comes from FRED, set `provider: fred` and `fred_series`.
3. If the data comes from EODHD, set `provider: eodhd` and `eodhd_symbol`.
4. Run `python -m src.update` and check `docs/data/latest.json`.
5. Run `pytest -q`.
