# India Trade & Market Pulse

A free-to-host static dashboard focused on:

- India import-export news and trade-policy signals
- India and global business / finance tracking
- Indian stock-market monitoring with a pathway to broader Nifty 500 coverage

## Why this setup

This project is designed to stay free and simple:

- Frontend: static HTML, CSS, and JavaScript
- Hosting: GitHub Pages
- Hourly refresh: GitHub Actions scheduled workflow
- Data sources: public RSS feeds plus public quote endpoints

For public repositories, GitHub-hosted Actions minutes are free, and GitHub Pages can host the static site without a paid server:

- [GitHub Actions billing](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions)
- [GitHub Pages](https://pages.github.com/)

## Project structure

- `index.html`: dashboard shell
- `assets/styles.css`: visual design and responsive layout
- `assets/app.js`: client-side rendering and in-browser hourly refresh
- `scripts/generate_dashboard.py`: hourly data snapshot generator
- `config/news_feeds.json`: editable list of trade / business RSS feeds
- `config/seed_symbols.json`: starter Indian stock watchlist fallback
- `data/dashboard.json`: generated snapshot consumed by the site
- `.github/workflows/hourly-refresh.yml`: scheduled hourly refresh job

## Deploy for free

1. Push this repository to GitHub.
2. Keep it public if you want the cleanest free setup.
3. In GitHub, open `Settings -> Pages`.
4. Set the source to `Deploy from a branch`.
5. Pick the `master` branch and `/ (root)` folder.
6. Save, then open the generated Pages URL.
7. In `Actions`, enable workflows if GitHub asks.
8. Run the `Hourly dashboard refresh` workflow once manually so the first live snapshot is created.

## How the hourly refresh works

- GitHub Actions runs every hour at minute `07`.
- The workflow calls `python scripts/generate_dashboard.py`.
- The script fetches:
  - India import-export RSS results
  - India business / finance RSS results
  - Global business / finance RSS results
  - Indian stock quotes from a public Yahoo Finance endpoint
- The workflow updates `data/dashboard.json` and pushes the refresh back to the repo.
- GitHub Pages serves the latest file automatically.
- The browser also re-fetches `data/dashboard.json` every hour while the page is open.
- Every article card includes a clickable source link plus a detailed summary generated from the feed description text when available.

## Reliability notes

- The hourly workflow uses `cron: "7 * * * *"` so it avoids the busiest `00` minute of the hour, which GitHub documents as more delay-prone for scheduled jobs.
- GitHub scheduled workflows only run from the default branch, so keep `.github/workflows/hourly-refresh.yml` on your default branch.
- GitHub documents that scheduled workflows in public repositories can be disabled after 60 days of no repository activity, so this project includes `.github/workflows/keepalive.yml` to add an empty commit only when the repo is getting close to that inactivity limit.

## Stock-market coverage note

The app tries to scale to broader Nifty 500 coverage automatically by downloading the NSE constituents CSV first. If that file is unavailable, it falls back to the starter watchlist in `config/seed_symbols.json`.

That means the app is free, but market-data completeness depends on which public endpoints are reachable at runtime. If you later want stricter or guaranteed full-universe coverage, the next step would be swapping in a paid or authenticated market-data source.

## Customize it

- Edit `config/news_feeds.json` to add or remove feeds
- Edit `config/seed_symbols.json` to prioritize the companies you care about most
- Change the workflow schedule in `.github/workflows/hourly-refresh.yml`
- Adjust the number of displayed stocks in `scripts/generate_dashboard.py`
