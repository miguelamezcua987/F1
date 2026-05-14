# F1 Dashboard

A local [Streamlit](https://streamlit.io/) app for exploring Formula 1 sessions: schedules, laps, comparisons, tyre strategy, and telemetry. It uses **FastF1** for historical seasons and the public **[OpenF1](https://openf1.org/)** API for the current season.

## Requirements

- **Python 3.10+** (3.11 or 3.12 recommended)
- Internet access the first time you load a session (FastF1 downloads race data into a cache; OpenF1 calls the live API)

## Get started

### 1. Clone the repository

```bash
git clone https://github.com/miguelamezcua987/F1.git
cd F1
```

### 2. Create a virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

Your browser should open to the local URL Streamlit prints (by default **http://localhost:8501**).

## Project layout

| Path | Purpose |
|------|--------|
| `app.py` | Streamlit entry point |
| `src/f1_utils.py` | FastF1 helpers and on-disk cache under `data/raw/` |
| `src/openf1_client.py` | OpenF1 HTTP client for the current year |
| `notebooks/` | Optional Jupyter exploration |
| `.streamlit/config.toml` | App theme and server defaults |

## Notes

- **First load** for a Grand Prix session can take a while while FastF1 fetches and caches data under `data/raw/` (that folder is gitignored).
- **Secrets**: do not commit API keys. If you add `.streamlit/secrets.toml` locally, it is already listed in `.gitignore`.
