# Run CiteAI in separate terminals

Complete the one-time setup in [README.md](./README.md) first. Keep these terminals open while using the application.

## Terminal 1 — PostgreSQL

For the native PostgreSQL 16 cluster on this machine:

```bash
sudo pg_ctlcluster 16 main start
pg_isready -h 127.0.0.1 -p 5432
```

If you set up the Docker database instead, run `docker start citeai-postgres` in this terminal and check it with `pg_isready -h 127.0.0.1 -p 5432`.

## Terminal 2 — Flask backend

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest
bash backend/start_server.sh
```

## Terminal 3 — Next.js website

```bash
cd /home/paarth/Projects/CiteAI/IML/CiteAI-latest/website
npm run dev -- --port 3000
```

Open <http://localhost:3000>. The API runs at <http://127.0.0.1:8000>.
