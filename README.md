# CiteAI

CiteAI combines a [Flask backend](./backend/) and [Next.js website](./website/) for PDF extraction, citation graphs, legal search, document chat, and analysis. PostgreSQL with pgvector stores users, documents, and retrieval vectors. Use this README for initial setup and validation; use [next_steps.md](./next_steps.md) for the short, separate-terminal run sequence.

## How analysis works

```text
PDF upload
  -> page-aware text extraction (Tesseract fallback for scanned pages)
  -> normalized OCR metadata and citation graph
  -> sentence-transformer and InLegalBERT embeddings
  -> deterministic internal review and optional Gemini report
  -> pgvector corpus retrieval and TRS scoring
  -> persisted analysis result
```

The canonical pipeline lives in [legal_pipeline.py](./backend/app/services/legal_pipeline.py) and is invoked by `POST /api/ocr/process/<document_id>`. Citation nodes link to a title-matched case PDF when the legal-source search finds one, and always offer a Google PDF search link. Chat uses passages from the uploaded PDF and its citation mentions. When a question names a cited case and the legal-source API is configured, it can also retrieve passages from that full judgment.

## One-time setup (Linux/bash)

Run these commands from this checkout. You need Python 3.11 or 3.12, Node.js 20+, npm, PostgreSQL 15+ with pgvector, and internet access for the first model download. Install Tesseract if you will analyze scanned PDFs (`sudo apt install tesseract-ocr` on Ubuntu/Debian). Check the tools:

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest
python3 --version
node --version
npm --version
tesseract --version   # optional for text PDFs
```

### 1. PostgreSQL

This machine has a native PostgreSQL 16 cluster. Start it, then check port 5432:

```bash
sudo pg_ctlcluster 16 main start
pg_isready -h 127.0.0.1 -p 5432
```

On a fresh native installation, create the local development role and both databases. Skip commands for a role or database that already exists. Choose a password when `createuser -P` prompts; use the same password in both backend URLs. The role needs permission to create extensions during initialization.

```bash
sudo -u postgres createuser -P -s citeai
sudo -u postgres createdb -O citeai citeai_main
sudo -u postgres createdb -O citeai citeai_auth
```

Docker is an alternative if you do not use the native cluster. Do not start both on port 5432:

```bash
docker run -d --name citeai-postgres --restart unless-stopped \
  -e POSTGRES_USER=citeai -e POSTGRES_PASSWORD=change-me \
  -e POSTGRES_DB=citeai_main -p 127.0.0.1:5432:5432 \
  -v citeai-pgdata:/var/lib/postgresql/data pgvector/pgvector:pg17
until docker exec citeai-postgres pg_isready -U citeai -q; do sleep 1; done
docker exec citeai-postgres psql -U citeai -d citeai_main -c 'CREATE DATABASE citeai_auth;'
```

Replace `change-me` before using the container outside local development. If port 5432 is occupied, map another host port and use it in both database URLs. [SETUP_README.md](./SETUP_README.md) has platform-specific database notes.

### 2. Backend

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/backend
test -x .venv/bin/python || python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
test -f .env || cp .env.example .env
```

Edit `backend/.env` before initialization:

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | `postgresql+psycopg2://citeai:<password>@localhost:5432/citeai_main` |
| `AUTH_DATABASE_URL` | `postgresql+psycopg2://citeai:<password>@localhost:5432/citeai_auth` |
| `JWT_SECRET_KEY` | A fresh secret from `openssl rand -hex 32` |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` |
| `GEMINI_API_KEY` | Required for document chat and the Gemini internal report |
| `GEMINI_FALLBACK_MODEL` | Optional backend fallback, defaults to `gemini-2.5-flash-lite` for temporary Gemini server failures |
| `INDIAN_KANOON_API_TOKEN` | Required to retrieve full cited judgments for chat; without it, chat uses citations mentioned in the uploaded PDF |

Keep `.env` private. The website's existing Indian Kanoon search proxy handles graph PDF matching separately. Then create schemas, seed the demo account, download both models, and index the bundled corpus:

```bash
.venv/bin/python init_db.py
.venv/bin/python -m flask --app manage warmup-models
.venv/bin/python precompute_corpus.py --pdf-dir ../corpus/legal_pdfs
```

`init_db.py` should end with `✓ All done.` Check that warmup lists both `legalbert` and `sentence-transformer`: that command can exit successfully even if a model failed. Initial downloads and corpus indexing can take several minutes. Run the corpus preload again when the bundled PDFs change; it re-embeds them. Retrieved Global Scores require an indexed corpus.

### 3. Website

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/website
test -f .env.local || cp .env.example .env.local
npm ci
```

Set `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` in `website/.env.local`. The **Cite Violations** route runs in Next.js and needs its own server-side `GEMINI_API_KEY`; the backend key is not read automatically. The route defaults to `gemini-2.5-flash`, retries a temporary 503 once, then tries `gemini-2.5-flash-lite`. `GEMINI_MODEL` and `GEMINI_FALLBACK_MODEL` can override those choices. Keep `.env.local` private and restart Next.js after changing it.

## Start the application

Keep three terminals open:

**Terminal 1 — PostgreSQL** (use your native cluster or Docker container):

```bash
sudo pg_ctlcluster 16 main start
pg_isready -h 127.0.0.1 -p 5432
```

For Docker, use `docker start citeai-postgres` instead of `pg_ctlcluster`.

**Terminal 2 — Flask API:**

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest
bash backend/start_server.sh
```

**Terminal 3 — Next.js website:**

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/website
npm run dev -- --port 3000
```

Open <http://localhost:3000>. Flask listens at <http://127.0.0.1:8000>. To stop the two app servers, press `Ctrl+C` in their terminals. The database can remain running.

## Validate the installation

With the services running, check health from a fourth terminal:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -I http://localhost:3000/
```

Run source checks when you change code. Stop the Next.js development server before `npm run build`, then restart it for browser checks:

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/backend
.venv/bin/python -m pytest tests -q
cd ../website
npm test
npm run lint
npx tsc --noEmit
npm run build
```

For a live API check, keep Flask and PostgreSQL running. `init_db.py` seeds `demo@example.com` / `password123` on a fresh database; use the existing password if that user was already present. The smoke test creates and deletes its own documents and chat:

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/backend
.venv/bin/python smoke_test.py --email demo@example.com --require-gemini
```

Enter the account password when prompted. Expect a final JSON object with `"status": "passed"`. Omit `--require-gemini` only if Gemini is not configured.

In the browser, sign in, upload a text PDF from `corpus/legal_pdfs/`, and choose **Analyze document**. Inspect **Source Network**, **Global Scores**, **Logic Analysis**, and **Chat**. Select a cited-case node: **Workspace Analysis** shows a passage from the title-matched judgment, any Article or Section explicitly present in that passage, and a link to the case PDF. If the judgment cannot be retrieved, it shows the citation's surrounding text from your uploaded PDF instead. Ask chat about the uploaded document and a named cited case; expand its evidence sections to distinguish citing passages from full judgment passages. Upload another PDF with **Add to db** and search its title in **Legal Search**. Check **Cite Violations** with the website Gemini key. Tesseract can be checked with an image-only PDF.

## Troubleshooting

- If Flask cannot connect to PostgreSQL, run `pg_isready -h 127.0.0.1 -p 5432` and check both database URLs and their password.
- If Global Scores is empty, complete the corpus preload.
- If model warmup omits either model, restore internet access and rerun it.
- If the browser cannot reach Flask, check `NEXT_PUBLIC_API_BASE_URL` and `CORS_ORIGINS`, then restart both servers.
- If **Logic Analysis** reports a Gemini connection or server error, check DNS/HTTPS from the machine running Flask. After restoring access, click **Retry Gemini report**; a current fallback report remains saved until retried.
- If you still see 111,712 review signals or the old "Run Global Scores" Workspace card, stop the old Flask and Next.js processes, start this checkout using [next_steps.md](./next_steps.md), and hard-refresh the browser. Logic Analysis now recomputes legacy saved reports on first open; its **Retry Gemini report** button retries temporary Gemini failures without reprocessing the PDF. The explicit port 3000 command fails if an old Next.js server still owns that port instead of silently using another port.
- If **Cite Violations** says its key is missing, set `GEMINI_API_KEY` in `website/.env.local` and restart Next.js. A Gemini 503 after retries means the external service is busy; try again later.
- If a citation has no direct PDF button, no exact title match was found. Use its Google PDF search link. Full cited-judgment chat passages also require the backend legal-source token.

See [backend/README.md](./backend/README.md) for API endpoints. The concise daily commands are in [next_steps.md](./next_steps.md).
