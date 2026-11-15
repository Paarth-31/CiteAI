# Run commands (Linux / bash)

## One-time setup: backend

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/backend
test -x .venv/bin/python || python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
# Set DATABASE_URL, AUTH_DATABASE_URL, JWT_SECRET_KEY, and GEMINI_API_KEY.
nano .env
flask --app manage warmup-models
```

```bash
# Run only if the two PostgreSQL databases are empty or not yet initialized.
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/backend
source .venv/bin/activate
python init_db.py
```

## One-time setup: frontend

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/website
test -f .env.local || cp .env.example .env.local
# Set NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000.
nano .env.local
npm ci
```

## Terminal 1: Flask

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/backend
source .venv/bin/activate
flask --app manage run --host 127.0.0.1 --port 8000
```

## Terminal 2: Next.js

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/website
npm run dev
```

## Terminal 3: health, authentication, and search

```bash
export API_BASE_URL=http://127.0.0.1:8000
curl -sS --fail-with-body "$API_BASE_URL/health" | jq .
curl -sS --fail-with-body "$API_BASE_URL/api/inference/models" | jq .
curl -sS --fail-with-body 'http://127.0.0.1:8000/api/search?q=privacy&page=0' | jq '{count,has_more,page,results}'
curl -I http://127.0.0.1:3000/
```

```bash
export CITEAI_EMAIL=you@example.com
read -rsp 'CiteAI password: ' CITEAI_PASSWORD
echo
```

```bash
# New account only.
curl -sS --fail-with-body -X POST "$API_BASE_URL/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg name 'Test User' --arg email "$CITEAI_EMAIL" --arg password "$CITEAI_PASSWORD" '{name:$name,email:$email,password:$password}')" | jq .
```

```bash
export ACCESS_TOKEN="$(curl -sS --fail-with-body -X POST "$API_BASE_URL/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg email "$CITEAI_EMAIL" --arg password "$CITEAI_PASSWORD" '{email:$email,password:$password}')" | jq -r '.accessToken')"
test -n "$ACCESS_TOKEN"
curl -sS --fail-with-body -H "Authorization: Bearer $ACCESS_TOKEN" "$API_BASE_URL/api/auth/me" | jq .
curl -sS --fail-with-body -H "Authorization: Bearer $ACCESS_TOKEN" "$API_BASE_URL/api/documents" | jq .
```

## Terminal 3: full analysis API test

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/backend
export PDF_PATH=../corpus/legal_pdfs/S_P_Chengalvaraya_Naidu_Dead_By_vs_Jagannath_Dead_By_L_Rs_And_Others_on_27_October_1993.PDF
export UPLOAD_JSON="$(curl -sS --fail-with-body -X POST "$API_BASE_URL/api/documents/upload" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@$PDF_PATH;type=application/pdf")"
export DOCUMENT_ID="$(jq -r '.document.id' <<< "$UPLOAD_JSON")"
test "$DOCUMENT_ID" != null
test -n "$DOCUMENT_ID"

curl -sS --fail-with-body -X POST "$API_BASE_URL/api/ocr/process/$DOCUMENT_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq '{success,document_id,num_nodes,num_edges,internal_analysis,external_inference}'

curl -sS --fail-with-body -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$API_BASE_URL/api/documents/$DOCUMENT_ID" | jq '.document | {id,title,status,hasOcrText,hasCitationGraph,hasAnalysis,hasExternalInference}'
curl -sS --fail-with-body -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$API_BASE_URL/api/ocr/citation-nodes/$DOCUMENT_ID?limit=10" | jq '{total_nodes,showing_top,nodes,edges}'
curl -sS --fail-with-body -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$API_BASE_URL/api/ocr/internal-analysis/$DOCUMENT_ID" | jq .
curl -sS --fail-with-body -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$API_BASE_URL/api/inference/similar/$DOCUMENT_ID" | jq .

# Requires GEMINI_API_KEY in backend/.env and a Flask restart.
curl -sS --fail-with-body -X POST "$API_BASE_URL/api/ocr/query/$DOCUMENT_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H 'Content-Type: application/json' \
  -d '{"query":"What legal principle does this document discuss?"}' | jq '{answer,passages,mode}'
```

## Terminal 3: Add to db API test (separate upload, no citations)

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/backend
export DB_UPLOAD_JSON="$(curl -sS --fail-with-body -X POST "$API_BASE_URL/api/documents/upload" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@$PDF_PATH;type=application/pdf")"
export DB_DOCUMENT_ID="$(jq -r '.document.id' <<< "$DB_UPLOAD_JSON")"
test "$DB_DOCUMENT_ID" != null
test -n "$DB_DOCUMENT_ID"

curl -sS --fail-with-body -X POST "$API_BASE_URL/api/documents/$DB_DOCUMENT_ID/add-to-db" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | jq .
curl -sS --fail-with-body -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$API_BASE_URL/api/documents/$DB_DOCUMENT_ID" | jq '.document | {id,title,status,hasOcrText,hasCitationGraph,ocrMetadata}'
curl -sS --fail-with-body -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$API_BASE_URL/api/ocr/citation-nodes/$DB_DOCUMENT_ID" | jq '{total_nodes,nodes,edges}'
curl -sS --fail-with-body -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$API_BASE_URL/api/search?q=Chengalvaraya&page=0" | jq --arg id "$DB_DOCUMENT_ID" '{count,has_more,page,indexed:any(.results[]; .id == $id),results}'
```

## Local checks

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/backend
source .venv/bin/activate
python -m pytest tests -q
python -m compileall -q app
```

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/website
npm run lint
npx tsc --noEmit
npm run build
```
