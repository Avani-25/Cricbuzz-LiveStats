# **🏏 Cricbuzz LiveStats: Real-Time Cricket Insights & SQL-Based Analytics**

A multi-page Streamlit application that combines live match data from the Cricbuzz API
with a normalized SQL database to deliver live scores, player rankings, 25 analytical SQL
queries, and full CRUD management of player records.

---
**Live demo:** 
<your-app>.streamlit.app  · 

---
**Demo video:** 
<video link>

---
## **Features**

| Page | What it does |
|---|---|
| **Home** | Database metrics, usage guide, and a system health panel (database, API key, quota, logs) |
| **Live Matches** | Live and recent matches with filters, score cards, per-match scorecards on demand, and one-click saving to the database |
| **Top Stats** | Career leaders by format (batting, bowling, all-rounders, fielding) with interactive Plotly charts |
| **SQL Queries** | 25 analytical queries (beginner → advanced) plus a safe custom `SELECT` runner |
| **CRUD Operations** | Create, read, update and delete players and their career stats, with validation and an audit log |

---
## **Engineering highlights**

- ****Quota-aware API usage:**** responses are cached, there is no auto-refresh, a configurable daily call cap protects a public deployment, and the last saved response is used if the API is down.
- ****Safe custom SQL:**** statements are validated (single `SELECT` only), executed on a read-only connection, with a 5-second time limit and a 5,000-row cap.
- ****Transactional CRUD:**** a player and their stats are saved together or not at all; deletes remove dependent rows first, so foreign keys always hold.
- ****Defensive by default:**** parameterized queries everywhere, whitelisted column names, input validation, secrets redacted from logs, friendly error messages with reference IDs.
- ****Self-building:**** on a fresh install the app creates and fills its own database.
- ****Well tested:**** 250+ automated tests, including page smoke tests, a secrets scanner and code-quality gates.

---
## **Screenshots**

| Home | Live Matches |

| ![Home](documentation/screenshots/home.png) | ![Live](documentation/screenshots/live_matches.png) |
| Top Stats | SQL Queries |
| ![Top stats](documentation/screenshots/top_stats.png) | ![SQL](documentation/screenshots/sql_queries.png) |
| CRUD | Analytics charts |
| ![CRUD](documentation/screenshots/crud.png) | ![Charts](documentation/screenshots/charts.png) |

---
## **Tech stack**

Python · Streamlit · SQLite (via SQLAlchemy) · pandas · Plotly · Requests · pytest · Ruff

---
## **Architecture**

```
                 ┌────────────────────────────────┐
                 │  Streamlit UI  (app.py, pages/) │
                 └───────┬──────────────┬─────────┘
                         │              │
             ┌───────────▼───┐    ┌─────▼──────────┐
             │   services/   │    │   sql/         │
             │ live, stats,  │    │ 25 queries     │
             │ crud, health  │    └─────┬──────────┘
             └──┬─────────┬──┘          │
                │         │             │
        ┌───────▼───┐  ┌──▼─────────────▼──┐
        │  api/     │  │ utils/db_connection│
        │ client +  │  │ (one shared engine)│
        │ daily cap │  └──────────┬─────────┘
        └─────┬─────┘             │
              │              ┌────▼─────┐
       Cricbuzz API          │  SQLite  │
       (RapidAPI)            └──────────┘
```

Layers only depend downwards: pages → services → api / utils. Pages never contain SQL or
HTTP calls, and only `api/` talks to the internet.

---
## **Database schema**

Eight tables in third normal form:

```
 series ──< matches >── venues
              │  │
   teams ─────┘  └───── teams            (team1, team2, toss winner, winner)
     │
     └──< players ──< player_career_stats       (one row per player per format)
              │
              ├──< batting_performances >── matches
              └──< bowling_performances >── matches
```

Primary and foreign keys, `CHECK` and `UNIQUE` constraints, and indexes on every column used
in joins and filters. See [`sql/schema.sql`](sql/schema.sql).

---
## **The 25 SQL questions**

| Level | Questions | Techniques |
|---|---|---|
| **Beginner** (Q1–Q8) | Players from India · matches in the last 30 days · top 10 ODI run scorers · venues over 50,000 capacity · wins per team · players per role · highest score per format · series started in 2024 | `WHERE`, `ORDER BY`, `LIMIT`, `GROUP BY` |
| **Intermediate** (Q9–Q16) | All-rounders with 1,000+ runs and 50+ wickets · last 20 completed matches · runs by format · home vs away wins · 100+ partnerships · bowling at venues · batters in close matches · yearly trend since 2020 | joins, subqueries, CTEs, conditional aggregation, `HAVING` |
| **Advanced** (Q17–Q25) | Toss impact · economical limited-overs bowlers · batting consistency · matches by format · weighted player ranking · head-to-head records · recent form · best partnerships · career phase from quarterly trends | window functions (`RANK`, `ROW_NUMBER`, `LAG`), multi-step CTEs, standard deviation |

All queries live in [`sql/queries.py`](sql/queries.py) and can be exported to `sql/queries.sql`.

---
## **Getting started**

**Requirements:** Python 3.x (use the same version you deploy with) and a free
[RapidAPI](https://rapidapi.com) key subscribed to the *Cricbuzz Cricket* API.

```bash
git clone https://github.com/<your-username>/cricbuzz-livestats.git
cd cricbuzz-livestats

python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate

pip install -r requirements-dev.txt
copy .env.example .env           # macOS/Linux: cp .env.example .env
# edit .env and paste your RapidAPI key

python -m scripts.setup_db       # creates tables + sample data
python -m pytest                 # optional: run the test suite
streamlit run app.py
```

The app also builds its own database on first start, so `setup_db` is optional.

### ***Configuration***

All settings are environment variables (a `.env` file locally, or *Secrets* on a host).

| Variable | Purpose | Default |
|---|---|---|
| `RAPIDAPI_KEY` | Your RapidAPI key (**required** for live pages) | - |
| `RAPIDAPI_HOST` | API host | `cricbuzz-cricket.p.rapidapi.com` |
| `API_BASE_URL` | API base URL | `https://cricbuzz-cricket.p.rapidapi.com` |
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///data/cricbuzz.db` |
| `LIVE_CACHE_TTL` | Seconds a live result is reused | `60` |
| `API_DAILY_BUDGET` | Max real API calls per UTC day (`0` = unlimited) | `0` |
| `DEMO_MODE` | Show "changes are temporary" notices | off |
| `AUTO_SETUP` | Build the database automatically on first start | on |
| `DEBUG` | Show technical details on error screens | off |

---
### **Notebooks**

| Notebook | Purpose |
|---|---|
| `00_environment_check` | Verify the setup |
| `01_api_exploration` | Explore the API endpoints and JSON shapes |
| `02_database_setup` | Build the schema and prove the constraints work |
| `data_fetching` | API → pandas → SQL ingestion |
| `03_crud_practice` | CRUD, validation and SQL-injection tests |
| `04`–`06_sql_q…` | The 25 queries, in three notebooks |
| `07_visualization` | Plotly charts for the analytics |

---
## ***Data sources***

- **From the Cricbuzz API (real):** live and recent matches, teams, venues, series, match status
  (winner, margin and toss are parsed from the status text).
- **Generated by `utils/seed_data.py` (sample):** players, career statistics, batting and
  bowling scorecards, plus team countries and venue country/capacity (capacities are
  approximate). Sample rows use IDs of 900,000 and above, and player names are fictional.
  The generator is seeded, so results are reproducible.

---
## ***Testing and quality***

```bash
python -m pytest        # 250+ tests
python -m ruff check .  # lint
```

- Unit tests for validation, CRUD, parsing, statistics and the 25 queries
- **Page smoke tests** that load every page headlessly against a fresh database
- Failure-path tests: API down, saved-response fallback, budget exhausted, corrupt files
- Quality gates: every file compiles, public functions have docstrings, `.env` is git-ignored,
  and **no API key appears in any file or notebook**
- Test coverage of the logic layers: <your coverage %> (measure with `python -m pytest --cov`)

---
## ***Deployment***

Deployed on Streamlit Community Cloud. Secrets are set in the host's *Secrets* settings
(see [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example)). Hosted settings
used: `DEMO_MODE=1`, `API_DAILY_BUDGET=<n>`, `LIVE_CACHE_TTL=900`.

---
## ***Limitations and future work***

- **The hosted database is temporary.** SQLite on a hosted container is rebuilt after a
  restart, so CRUD changes do not last. A production version would use a hosted database
  such as PostgreSQL. This needs some query changes, because a few queries use SQLite
  functions (`date('now', ...)`, `strftime`, two-argument `MIN`/`MAX`, a custom `STDDEV`).
- **Free API quota:** the app deliberately avoids auto-refresh and caps daily calls.
- **Scorecard parsing** follows the API's usual response shape and falls back to raw JSON
  if the format differs.
- **Ideas:** real player and scorecard ingestion within quota, a form-prediction model,
  authentication for the CRUD page, and a persistent hosted database.

---
## ***Acknowledgements***

Match data via the Cricbuzz API on RapidAPI. This project is an educational portfolio
piece and is not affiliated with or endorsed by Cricbuzz.
