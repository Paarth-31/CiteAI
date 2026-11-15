"""Opt-in live API test. Creates and deletes only its own sample uploads/chats.

Run with Flask already started:
    python smoke_test.py --email demo@example.com --require-gemini
The password is read from CITEAI_TEST_PASSWORD or prompted without echo.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import time
import uuid

import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--require-gemini", action="store_true")
    parser.add_argument("--pdf", type=Path, default=Path(__file__).resolve().parent.parent / "corpus/legal_pdfs/S_P_Chengalvaraya_Naidu_Dead_By_vs_Jagannath_Dead_By_L_Rs_And_Others_on_27_October_1993.PDF")
    args = parser.parse_args()
    password = os.getenv("CITEAI_TEST_PASSWORD") or getpass.getpass("Test account password: ")
    session = requests.Session()
    base = args.base_url.rstrip("/")
    documents: list[str] = []
    chats: list[str] = []
    passed = 0

    def call(method, path, *, expected=200, **kwargs):
        nonlocal passed
        started = time.monotonic()
        response = session.request(method, base + path, timeout=300, **kwargs)
        data = response.json()
        if response.status_code != expected:
            raise AssertionError(f"{method} {path}: {response.status_code} {data.get('error', data.get('msg', 'unexpected response'))}")
        passed += 1
        print(f"PASS {method} {path} ({time.monotonic() - started:.1f}s)", flush=True)
        return data

    try:
        call("GET", "/health")
        call("POST", "/api/documents/upload", expected=401)
        login = call("POST", "/api/auth/login", json={"email": args.email, "password": password})
        session.headers["Authorization"] = "Bearer " + login["accessToken"]
        call("GET", "/api/auth/me")
        call("PUT", "/api/auth/me", json={"name": login["user"]["name"]})
        call("PUT", "/api/auth/me", json={"name": ""}, expected=400)
        renewed = call("POST", "/api/auth/refresh", headers={"Authorization": "Bearer " + login["refreshToken"]})
        session.headers["Authorization"] = "Bearer " + renewed["accessToken"]

        for mode in ("database", "analysis"):
            title = "citeaismoke" + uuid.uuid4().hex
            with args.pdf.open("rb") as pdf:
                uploaded = call("POST", "/api/documents/upload", files={"file": (title + ".pdf", pdf, "application/pdf")}, expected=201)
            doc_id = uploaded["document"]["id"]
            documents.append(doc_id)
            if mode == "database":
                result = call("POST", f"/api/documents/{doc_id}/add-to-db")
                assert result["chunks_indexed"] > 0
                repeated = call("POST", f"/api/documents/{doc_id}/add-to-db")
                assert repeated["corpus_document_id"] == result["corpus_document_id"]
                detail = call("GET", f"/api/documents/{doc_id}")["document"]
                assert detail["hasOcrText"] and not detail["hasCitationGraph"] and not detail["citations"]
                graph = call("GET", f"/api/ocr/citation-nodes/{doc_id}")
                assert not graph["nodes"]
            else:
                result = call("POST", f"/api/ocr/process/{doc_id}")
                assert result["num_nodes"] > 0
                assert result["external_inference"]["source"] == "pgvector"
                assert result["external_inference"]["retrieved_cases"], "Seed a retrieval corpus before the smoke test"
                if args.require_gemini:
                    assert result["internal_analysis"]["analysis_mode"] == "gemini", result["internal_analysis"].get("summary")
                    assert result["internal_analysis"]["claims"]
                graph = call("GET", f"/api/ocr/citation-nodes/{doc_id}")
                assert graph["nodes"]
                call("GET", f"/api/ocr/internal-analysis/{doc_id}")
                call("GET", f"/api/inference/similar/{doc_id}")
                inferred = call("POST", f"/api/inference/similar/{doc_id}", json={"top_k": 5, "force": True})
                assert inferred["results"]["legal"]["retrieved_cases"]
                similar = call("GET", f"/api/search/similar-documents/{doc_id}")
                assert any(row["id"] == documents[0] for row in similar["results"])
                if args.require_gemini:
                    answer = call("POST", f"/api/ocr/query/{doc_id}", json={"query": "What does the court say about fraud?"})
                    assert answer["answer"] and answer["passages"]
                chat = call("POST", "/api/chats", json={"title": "Smoke test", "documentId": doc_id}, expected=201)["chat"]
                chats.append(chat["id"])
                call("POST", f"/api/chats/{chat['id']}/messages", json={"role": "user", "content": "Smoke test message"}, expected=201)
                call("GET", f"/api/chats/{chat['id']}")
            search = call("GET", "/api/search", params={"q": title, "page": 0})
            assert any(row["id"] == doc_id for row in search["results"])
        print(json.dumps({"passed_requests": passed, "status": "passed"}), flush=True)
    finally:
        for chat_id in chats:
            call("DELETE", f"/api/chats/{chat_id}")
        for doc_id in reversed(documents):
            call("DELETE", f"/api/documents/{doc_id}")
        session.close()


if __name__ == "__main__":
    main()
