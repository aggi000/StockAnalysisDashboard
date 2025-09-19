# Backend (FastAPI)

## Quickstart

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Endpoints:
- `GET /health` – service status
- `GET /api/quote/{ticker}` – snapshot metrics (price, PE, EPS, dividendYield, etc.)
- `GET /api/history/{ticker}?period=1y&interval=1d&indicators=sma,ema,rsi,macd,boll` – OHLCV plus optional indicators

Notes:
- Uses `yfinance` for a quick start. For production-grade data (SLAs/licensing), consider Polygon, Tiingo, or Twelve Data.
