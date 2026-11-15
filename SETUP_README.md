# CiteAI — Setup Guide (from a fresh `git clone`)

This guide takes you from an empty machine to a running CiteAI: a **PostgreSQL + pgvector** database, the **Flask backend** (OCR, citation graph, InLegalBERT/sentence-transformer embeddings, retrieval) and the **Next.js website**.

Expect about **30–45 minutes** the first time. Most of that is downloads (about 2–3 GB of Python/ML packages and models) and the one-time corpus preload (about 15 minutes on a laptop CPU).

> What changed recently and why: see [`CHANGES_LOG.md`](./CHANGES_LOG.md).

---

## 0. Architecture at a glance

```text
Browser ── http://localhost:3000 ──▶ Next.js website (website/)
                                         │  (browser calls Flask directly)
                                         ▼
                              Flask API  http://127.0.0.1:8000 (backend/)
                                         │  models: law-ai/InLegalBERT, all-MiniLM-L6-v2
                                         ▼
               PostgreSQL 17 + pgvector  localhost:5432
                 ├─ citeai_auth  (users)
                 └─ citeai_main  (documents, citations, chats, corpus vectors)
```

| Component | Port | Required |
|---|---|---|
| PostgreSQL + pgvector | 5432 | Yes |
| Flask backend | 8000 | Yes |
| Next.js website | 3000 | Yes (for the UI) |
| Gemini API key | — | Optional (document chat, detailed report, "Cite Violations") |
| Tesseract OCR | — | Optional (only for scanned/image-only PDFs) |

---

## 1. Prerequisites

| Tool | Version | Check | Notes |
|---|---|---|---|
| Git | any | `git --version` | |
| Python | **3.11** (3.11 or 3.12 recommended) | `python3.11 --version` | Intel Macs **must** use 3.11/3.12 (see §8) |
| Node.js | **20+** (tested on 23) | `node --version` | npm comes with it |
| Docker Desktop | recent | `docker info` | Easiest way to get PostgreSQL + pgvector. Native install also works (§2B) |
| Tesseract | 5.x | `tesseract --version` | Optional. macOS: `brew install tesseract`; Ubuntu: `sudo apt install tesseract-ocr`; Windows: UB-Mannheim installer |

Free disk space needed: about **6 GB** (venv ≈ 2.5 GB, HF models ≈ 0.7 GB, `node_modules` ≈ 1 GB, Docker image + data ≈ 1 GB).

**Python 3.11 options:** `pyenv install 3.11` (macOS/Linux), python.org installers, or `sudo apt install python3.11 python3.11-venv` (Ubuntu).

---

## 2. Database: PostgreSQL 17 + pgvector

The backend needs **two databases** (`citeai_main`, `citeai_auth`) owned by one user, with the `vector` extension available.

### 2A. Docker (recommended: macOS Intel/Apple Silicon, Linux, Windows)

```bash
docker run -d --name citeai-postgres --restart unless-stopped \
  -e POSTGRES_USER=citeai \
  -e POSTGRES_PASSWORD=change-me \
  -e POSTGRES_DB=citeai_main \
  -p 127.0.0.1:5432:5432 \
  -v citeai-pgdata:/var/lib/postgresql/data \
  pgvector/pgvector:pg17

# wait until it accepts connections, then create the auth DB
until docker exec citeai-postgres pg_isready -U citeai -q; do sleep 1; done
docker exec citeai-postgres psql -U citeai -d citeai_main -c "CREATE DATABASE citeai_auth;"
```

- Data survives restarts in the `citeai-pgdata` Docker volume.
- `--restart unless-stopped` means the database starts automatically whenever Docker Desktop is running.
- If you pick a different password, use it in `backend/.env` too (§3.3).
- **Port 5432 already in use** (a local Postgres is running)? Use `-p 127.0.0.1:5433:5432` and put `:5433` in both URLs in `backend/.env`.

### 2B. Native install (alternative)

- **Ubuntu/Debian:**
  ```bash
  sudo apt install postgresql-17 postgresql-17-pgvector   # via the PGDG apt repo
  sudo -u postgres psql -c "CREATE USER citeai WITH PASSWORD 'change-me' SUPERUSER;"
  sudo -u postgres createdb -O citeai citeai_main
  sudo -u postgres createdb -O citeai citeai_auth
  ```
- **macOS Apple Silicon:** `brew install postgresql@17 pgvector && brew services start postgresql@17`, then create the user and databases as above with `psql postgres`.
- **macOS Intel:** Homebrew no longer fully supports Intel Macs (it compiles everything from source and that's unreliable). **Use Docker (2A).**
- **Windows:** Use Docker (2A), or the EDB PostgreSQL installer plus a pgvector build for Windows.

> `init_db.py` runs `CREATE EXTENSION vector, pg_trgm, unaccent, pgcrypto`. With a native install the `citeai` user needs permission to create extensions (superuser, or have a superuser run them once).

---

## 3. Backend (Flask)

### 3.1 Clone

```bash
git clone <your-remote-url> CiteAI
cd CiteAI/backend
```

### 3.2 Virtual environment + dependencies

**macOS / Linux**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt      # 5–15 min, downloads torch etc.
python -m pip check                             # should print "No broken requirements found."
```

**Windows (PowerShell)** (manual commands; the bundled `.ps1` scripts are outdated)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

> **Intel Mac note:** `requirements.txt` automatically pins `numpy<2`, `pandas<3`, `pyarrow<20` and `transformers<4.50` on Intel Macs, because torch 2.2.2 is the newest torch available there. Nothing extra to do, but don't upgrade those packages by hand.

### 3.3 Configure `backend/.env`

```bash
cp .env.example .env
```

Then edit `.env`:

| Variable | What to set | Default in example |
|---|---|---|
| `DATABASE_URL` | Main DB URL | `postgresql+psycopg2://citeai:change-me@localhost:5432/citeai_main` |
| `AUTH_DATABASE_URL` | Auth DB URL | `…/citeai_auth` |
| `JWT_SECRET_KEY` | **A long random secret.** Generate with `openssl rand -hex 32` or `python -c "import secrets;print(secrets.token_hex(32))"` | placeholder, **change it** |
| `CORS_ORIGINS` | Origins allowed to call the API | `http://localhost:3000,http://127.0.0.1:3000` |
| `UPLOAD_FOLDER` | Where PDFs are stored (relative paths resolve from `backend/`) | `storage/uploads` |
| `MAX_UPLOAD_SIZE_MB` | Upload limit | `50` |
| `MODEL_DEVICE` | `auto`, `cpu`, or `cuda` | `auto` |
| `GEMINI_API_KEY` | Optional. Enables document Q&A chat + detailed internal report | empty |
| `GEMINI_MODEL` | Gemini model name | `gemini-2.5-flash` |

The database URLs must match the user, password and port from §2.

### 3.4 Create tables and seed data

```bash
python init_db.py
```

Expected output ends with `✓ All done.` It creates:
- extensions `vector`, `pg_trgm`, `unaccent`, `pgcrypto` on both databases
- all tables, full-text-search triggers and vector indexes
- the demo account **`demo@example.com` / `password123`**
- 4 baseline cases (Puttaswamy, Gobind, Maneka Gandhi, sample case)

It's safe to run again; existing rows are skipped.

### 3.5 Download the ML models (one time, about 700 MB)

```bash
flask --app manage warmup-models
```

Expected:
```text
Loading InLegalBERT...
  InLegalBERT loaded.
Loading sentence-transformer...
  Sentence-transformer loaded.

Loaded: ['legalbert', 'sentence-transformer']
```
Models are cached in `~/.cache/huggingface/`. A one-time line `No sentence-transformers model found … Creating a new one with mean pooling` on the very first run is harmless.

### 3.6 Preload the retrieval corpus (one time, about 15 min)

Retrieval ("Global Scores" / similar cases) searches a precomputed corpus. Load the 24 bundled PDFs (judgments, the Constitution, criminal-law texts):

```bash
python precompute_corpus.py --pdf-dir ../corpus/legal_pdfs
```

Expected: `Found 24 PDF(s) …` then `Completed. docs=24, chunks=4860, domain=legal`.
Progress is mostly silent; the large statute PDFs (Constitution, Criminal 1–3) take the longest.

Optional extras:
```bash
# Add a Hugging Face dataset (large download; try --limit first)
python precompute_corpus.py --hf-dataset ninadn/indian-legal --hf-split train --limit 1000

# Wipe and rebuild the corpus
python precompute_corpus.py --reset-domain --pdf-dir ../corpus/legal_pdfs
```

### 3.7 Run the tests (optional but recommended)

```bash
python -m pytest tests -q        # expect: 10 passed
```

### 3.8 Start the backend

```bash
# macOS / Linux (from anywhere)
bash backend/start_server.sh

# or, from backend/ with the venv active (any OS)
python -m flask --app manage run --host 127.0.0.1 --port 8000
```

Check it:
```bash
curl http://127.0.0.1:8000/health
# {"models_loaded":[],"status":"ok"}  ← models load lazily on first use
```

> Flask doesn't auto-reload. **Restart it after editing backend code or `.env`.**

---

## 4. Website (Next.js)

Open a **second terminal**:

```bash
cd CiteAI/website
cp .env.example .env.local
npm ci                       # exact versions from package-lock.json
npm run dev
```

Open **http://localhost:3000**.

`website/.env.local`:

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Flask URL, default `http://127.0.0.1:8000` |
| `GEMINI_API_KEY` | Optional. Needed only for the **Cite Violations** button (not in the example file, so add it yourself) |

Restart `npm run dev` after changing `.env.local`.

Production build check (optional):
```bash
npm run lint && npx tsc --noEmit && npm test && npm run build
```

---

## 5. Verify everything works

### 5.1 Automated end-to-end test (backend)

With Flask running, from `backend/`:
```bash
CITEAI_TEST_PASSWORD=password123 python smoke_test.py --email demo@example.com
```
Expect `{"passed_requests": 24, "status": "passed"}`. It creates and then deletes its own test documents. Add `--require-gemini` if you configured a Gemini key.

### 5.2 Manual test in the browser

1. **Sign in:** `demo@example.com` / `password123` (or register).
2. **Analyze:** upload `corpus/legal_pdfs/Babu_vs_State_Of_Kerala_on_11_August_2010.PDF` and click **Analyze document** (about 10–20 s).
3. Open the document and check each tab:
   - **Source Network:** citation graph with edges from the judgment to the cases it cites.
   - **Global Scores:** up to 20 related corpus documents with TRS and similarity scores.
   - **Logic Analysis:** coherence score and flagged issues (see Known issues in `CHANGES_LOG.md`).
   - **Chat:** needs `GEMINI_API_KEY`.
4. **Add to db:** upload another PDF and click **Add to db**. It's indexed for search with no citation graph.
5. **Search page:** search `privacy` for the baseline cases, or search the title of your upload.

---

## 6. Day-to-day usage

**Start** (after a reboot):
```bash
# 1. Start Docker Desktop (the citeai-postgres container starts with it)
#    or: docker start citeai-postgres
# 2. Terminal 1
bash backend/start_server.sh
# 3. Terminal 2
cd website && npm run dev
```

**Stop:** `Ctrl+C` in both terminals. The database can keep running, or `docker stop citeai-postgres`.

**Reset the database completely** (deletes all users, uploads metadata and corpus):
```bash
docker rm -f citeai-postgres && docker volume rm citeai-pgdata
rm -rf backend/storage/uploads
# then repeat §2A, §3.4 and §3.6
```

**Inspect the database:**
```bash
docker exec -it citeai-postgres psql -U citeai -d citeai_main
#   \dt                                    list tables
#   select title, status from documents;
#   select count(*) from corpus_chunks;
```

---

## 7. What is (and isn't) committed to git

| Path | In git? | Why |
|---|---|---|
| `backend/.env.example`, `website/.env.example` | ✅ | Templates, no secrets |
| `backend/.env`, `website/.env.local`, `_env*` | ❌ | Secrets (JWT key, Gemini key, DB password) |
| `backend/.venv/`, `website/node_modules/`, `website/.next/` | ❌ | Rebuilt by §3.2 / §4 |
| `backend/storage/` (uploaded PDFs) | ❌ | User data |
| `corpus/legal_pdfs/*` (24 files) | ✅ | Already tracked. **New** PDFs added there are ignored unless you run `git add -f` |
| HF model weights (`*.bin`, `*.safetensors`, `.cache/`) | ❌ | Downloaded by §3.5 |

Before pushing, `git status` should show no `.env`, `_env`, `.venv` or `storage/` paths.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `A module that was compiled using NumPy 1.x cannot be run in NumPy 2…` | NumPy 2 installed on an Intel Mac | `pip install -r requirements.txt` again (the Intel pins apply), or `pip install "numpy<2" "pandas<3" "pyarrow<20"` |
| `InLegalBERT failed: … upgrade torch to at least v2.6` | transformers ≥4.50 with torch <2.6 | Intel Mac: `pip install "transformers<4.50"`. Other platforms: `pip install -U torch` |
| `pyarrow requires NumPy 2.0 or newer` | pyarrow too new for NumPy 1 | `pip install "pyarrow<20"` |
| `connection refused … 5432` | Database not running | Start Docker Desktop / `docker start citeai-postgres` |
| `password authentication failed for user "citeai"` | `.env` password ≠ container password | Fix the URLs in `backend/.env` |
| `database "citeai_auth" does not exist` | Skipped the second `CREATE DATABASE` | Run the last command of §2A |
| `FATAL: vector is required but not installed` (from `init_db.py`) | Postgres without pgvector | Use the `pgvector/pgvector:pg17` image, or install `postgresql-17-pgvector` |
| UI: "Cannot reach the backend" | Flask not running / wrong URL | Start Flask; check `NEXT_PUBLIC_API_BASE_URL`; restart `npm run dev` |
| Browser console CORS error | Frontend origin not allowed | Add it to `CORS_ORIGINS` in `backend/.env` and restart Flask |
| "Your session has expired" | Access token (30 min) and refresh token expired, or `JWT_SECRET_KEY` changed | Sign in again |
| Global Scores is empty | Corpus not loaded | Run §3.6 |
| `OCR processing failed: No text could be extracted…` | Scanned PDF and no Tesseract | Install Tesseract (§1) |
| Chat says `GEMINI_API_KEY is not configured` | No key | Add `GEMINI_API_KEY` to `backend/.env`, restart Flask |
| `Address already in use` on 8000/3000 | Old server still running | `lsof -nP -iTCP:8000 -sTCP:LISTEN` then `kill <pid>` (or use another port) |
| Code/env changes have no effect | Flask doesn't auto-reload | Restart Flask |

---

## 9. Useful reference

- API endpoint list: [`backend/README.md`](./backend/README.md)
- Pipeline implementation: [`backend/app/services/legal_pipeline.py`](./backend/app/services/legal_pipeline.py)
- Change history and known issues: [`CHANGES_LOG.md`](./CHANGES_LOG.md)
- Flask CLI helpers: `flask --app manage status`, `flask --app manage warmup-models`, `flask --app manage seed`
