# Stock Analysis Web App — MVP

An educational project to practice data science and full‑stack skills. MVP includes:
- Price/metrics snapshot
- Historical OHLCV + technical indicators (SMA/EMA/RSI/MACD/Bollinger)
- Interactive chart

## Repo Structure
```
backend/  → FastAPI + yfinance + pandas
frontend/ → Vue 3 (Vite) + Tailwind + Chart.js
```

## Local Dev
1) Start backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

2) Start frontend
```bash
cd frontend
npm i
npm run dev
```

Set `VITE_API_BASE` in `frontend/.env` if your API URL differs.

## Next Steps / Stretch Goals
- Watchlists & alerts (web push / email)
- Compare multiple tickers on the same chart
- Candlesticks + volume overlays
- Basic screener (market cap, P/E, sector)
- Simple backtests (moving‑average crossover)
- Persisted cache (SQLite/DuckDB) + cron refresh
- Authentication and user profiles
- CI (lint, test, format) + Playwright e2e
