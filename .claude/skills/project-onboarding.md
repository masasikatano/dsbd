# Project Onboarding

Use this skill when a user asks "what is this project?" or "how does it work?".

## Summary

This is a static dashboard site for macro / ETF investment decisions. It fetches end-of-day market data, computes metrics, and renders a single HTML page hosted on GitHub Pages.

## Key Documents

- `README.md` — user-facing setup and deployment instructions
- `architecture.md` — system architecture and data flow
- `spec.md` — v1 specification
- `spec_v2.md` — v2 specification covering missing data sources
- `config/instruments.yaml` — source of truth for all tracked instruments

## Key Code

- `src/update.py` — orchestration
- `src/compute.py` — metrics and derived spreads
- `src/providers/base.py` — `Provider` protocol and `FetchResult`
- `src/providers/yahoo.py`, `fred.py`, `eodhd.py` — data providers
- `docs/index.html` — UI

## Constraints

- **Only Kimi Code edits code.** You may read, explain, and review only.
- UI is a single HTML file with no build step.
- Missing data rows must remain visible as "データなし".
- Tests run with `pytest -q`.
