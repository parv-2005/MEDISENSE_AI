"""End-to-end API tests. MongoDB is in-memory (mongomock), Gemini is faked at the
dependency boundary, ChromaDB and the OCR pipeline run for real."""
import hashlib
import json
import math

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.database import get_db
from app.main import create_app
from app.services.gemini_client import get_gemini
from app.services.rag.vector_store import VectorStore, get_vector_store

ANALYSIS_JSON = {
    "report_type": "Complete Blood Count",
    "summary": "Mild anaemia.",
    "findings": [{"parameter": "Hemoglobin", "value": "10.2 g/dL", "reference_range": "12-16", "status": "low",
                  "explanation": "Low."}],
    "abnormal_flags": ["Hemoglobin low"],
    "insights": ["i"],
    "recommendations": ["r"],
    "urgency": "routine",
    "disclaimer": "Not medical advice.",
}


class FakeGemini:
    model_name = "fake-gemini"

    def __init__(self):
        self.prompts: list[str] = []

    def generate_text(self, prompt: str, system_instruction: str | None = None, json_schema=None) -> str:
        self.prompts.append(prompt)
        if json_schema is not None:
            return json.dumps(ANALYSIS_JSON)
        return "Your haemoglobin is 10.2 g/dL which is low [1]."

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            vec = [0.0] * 64
            for w in t.lower().split():
                vec[int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1
            n = math.sqrt(sum(v * v for v in vec)) or 1
            out.append([v / n for v in vec])
        return out


@pytest.fixture
def fake_gemini():
    return FakeGemini()


@pytest.fixture
def client(tmp_path, fake_gemini, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    from app.config import get_settings
    get_settings.cache_clear()

    app = create_app(connect_db=False)
    mock_db = AsyncMongoMockClient()["medisense_test"]
    store = VectorStore(persist_dir=tmp_path / "chroma", embed=fake_gemini.embed)

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_gemini] = lambda: fake_gemini
    app.dependency_overrides[get_vector_store] = lambda: store
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture
def digital_pdf_bytes():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Complete Blood Count report for patient. Hemoglobin 10.2 g/dL (12.0-16.0) LOW.\n"
                               "WBC 7.1 x10^3/uL (4.0-11.0). Platelets 250 x10^3/uL (150-400).", fontsize=11)
    return doc.tobytes()


def register(client, email="ana@example.com", password="Sup3rSecret!"):
    r = client.post("/api/auth/register", json={"name": "Ana", "email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ auth
def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_register_returns_token_and_user_without_password(client):
    data = register(client)
    assert data["access_token"]
    assert data["user"]["email"] == "ana@example.com"
    assert "password" not in json.dumps(data)


def test_duplicate_email_is_rejected(client):
    register(client)
    r = client.post("/api/auth/register", json={"name": "Ana", "email": "ana@example.com", "password": "Sup3rSecret!"})
    assert r.status_code == 409


def test_login_with_valid_and_invalid_credentials(client):
    register(client)
    ok = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "Sup3rSecret!"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post("/api/auth/login", json={"email": "ana@example.com", "password": "nope-nope"})
    assert bad.status_code == 401


def test_me_requires_valid_token(client):
    token = register(client)["access_token"]
    assert client.get("/api/auth/me", headers=auth_headers(token)).json()["email"] == "ana@example.com"
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=auth_headers("garbage")).status_code == 401


# ------------------------------------------------------------------ reports
def test_upload_saves_file_and_metadata(client, digital_pdf_bytes, tmp_path):
    token = register(client)["access_token"]
    r = client.post("/api/reports/upload", headers=auth_headers(token),
                    files={"file": ("cbc.pdf", digital_pdf_bytes, "application/pdf")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "uploaded"
    assert body["original_filename"] == "cbc.pdf"
    assert (tmp_path / "uploads" / body["stored_filename"]).exists()

    listing = client.get("/api/reports", headers=auth_headers(token)).json()
    assert [x["id"] for x in listing] == [body["id"]]


def test_upload_rejects_unsupported_type(client):
    token = register(client)["access_token"]
    r = client.post("/api/reports/upload", headers=auth_headers(token),
                    files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_reports_are_private_to_their_owner(client, digital_pdf_bytes):
    t1 = register(client, email="a@example.com")["access_token"]
    t2 = register(client, email="b@example.com")["access_token"]
    rid = client.post("/api/reports/upload", headers=auth_headers(t1),
                      files={"file": ("cbc.pdf", digital_pdf_bytes, "application/pdf")}).json()["id"]
    assert client.get(f"/api/reports/{rid}", headers=auth_headers(t2)).status_code == 404
    assert client.get("/api/reports", headers=auth_headers(t2)).json() == []


def test_full_pipeline_extract_analyze_ask(client, digital_pdf_bytes, fake_gemini):
    token = register(client)["access_token"]
    h = auth_headers(token)
    rid = client.post("/api/reports/upload", headers=h,
                      files={"file": ("cbc.pdf", digital_pdf_bytes, "application/pdf")}).json()["id"]

    # 3. Text extraction (digital branch)
    r = client.post(f"/api/reports/{rid}/extract", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "extracted"
    assert r.json()["extraction_method"] == "digital"
    assert "Hemoglobin 10.2 g/dL" in r.json()["extracted_text"]

    # 4. AI analysis (Gemini, faked) stored in analyses collection
    r = client.post(f"/api/reports/{rid}/analyze", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["analysis"]["findings"][0]["status"] == "low"
    assert "Hemoglobin 10.2 g/dL" in fake_gemini.prompts[0]
    got = client.get(f"/api/reports/{rid}/analysis", headers=h)
    assert got.status_code == 200 and got.json()["analysis"]["summary"] == "Mild anaemia."
    assert client.get(f"/api/reports/{rid}", headers=h).json()["status"] == "analyzed"

    # 5. RAG follow-up
    r = client.post(f"/api/reports/{rid}/ask", headers=h, json={"question": "Is my hemoglobin low?"})
    assert r.status_code == 200, r.text
    assert "10.2" in r.json()["answer"]
    assert r.json()["sources"] and "Hemoglobin" in r.json()["sources"][0]["text"]
    history = client.get(f"/api/reports/{rid}/qa", headers=h).json()
    assert len(history) == 1 and history[0]["question"] == "Is my hemoglobin low?"


def test_analyze_before_extract_fails_clearly(client, digital_pdf_bytes):
    token = register(client)["access_token"]
    h = auth_headers(token)
    rid = client.post("/api/reports/upload", headers=h,
                      files={"file": ("cbc.pdf", digital_pdf_bytes, "application/pdf")}).json()["id"]
    r = client.post(f"/api/reports/{rid}/analyze", headers=h)
    assert r.status_code == 409
    assert client.get(f"/api/reports/{rid}/analysis", headers=h).status_code == 404


def test_delete_report_removes_everything(client, digital_pdf_bytes, tmp_path):
    token = register(client)["access_token"]
    h = auth_headers(token)
    body = client.post("/api/reports/upload", headers=h,
                       files={"file": ("cbc.pdf", digital_pdf_bytes, "application/pdf")}).json()
    client.post(f"/api/reports/{body['id']}/extract", headers=h)
    assert client.delete(f"/api/reports/{body['id']}", headers=h).status_code == 204
    assert client.get(f"/api/reports/{body['id']}", headers=h).status_code == 404
    assert not (tmp_path / "uploads" / body["stored_filename"]).exists()
