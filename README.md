# Market Conditions Dashboard

Static GitHub Pages dashboard with two deliberately separate models:

- **Economic Conditions**: economic and monetary/credit data only.
- **Investor Sentiment**: market-derived fear/risk-appetite measures only.
- **S&P 500**: display-only; it never enters the Economic Conditions model.

## Architecture

GitHub Actions runs `scripts/update_data.py`, writes 10 years of precomputed daily history to `data/dashboard.json`, commits the JSON back to the repository, and GitHub Pages serves the static site. The browser only reads the prepared JSON, so it should load quickly.

## Deploy

1. Create a GitHub repository and push/upload this project.
2. Go to **Settings → Pages**.
3. Choose **Deploy from a branch**, your default branch (`main`), and `/ (root)`.
4. Open **Actions** and manually run **Update dashboard data** once.
5. If the Action cannot push, go to **Settings → Actions → General → Workflow permissions** and allow read/write repository permission.

## Local preview

Generate data:

```bash
python3 scripts/update_data.py
```

Serve the directory:

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000`.

## Current model inputs

Economic: M2, bank credit, business lending, corporate profits, industrial production, payrolls, retail sales, real disposable income, CPI, durable-goods orders, effective federal-funds rate.

Sentiment v1: VIX, high-yield option-adjusted spread, St. Louis Fed Financial Stress Index, S&P 500 short-term momentum, NASDAQ short-term momentum.

The sentiment model is intentionally separate. Future direct sentiment sources such as put/call ratios and survey history can be added without touching the economic engine.

## Historical note

History is capped at 10 years. Economic series can be revised after release; this version uses conservative release lags but is not yet a full ALFRED vintage-perfect reconstruction. Going forward, each scheduled run creates a contemporaneous repository record.
