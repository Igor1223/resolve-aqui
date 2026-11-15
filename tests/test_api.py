import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "sqlite:///./test_resolve_aqui.db"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough"

from fastapi.testclient import TestClient
from backend.main import app

def register(client, email="teste@example.com"):
    return client.post("/api/auth/register", json={
        "name": "Pessoa Teste",
        "email": email,
        "password": "senha-forte-123"
    })

def auth_headers(client, email="teste@example.com"):
    response = register(client, email)
    if response.status_code == 409:
        response = client.post("/api/auth/login", json={
            "email": email, "password": "senha-forte-123"
        })
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def test_health_pages_categories_and_guides():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/").status_code == 200
        assert client.get("/manifest.webmanifest").status_code == 200
        assert client.get("/sw.js").status_code == 200
        assert client.get("/api/categories").status_code == 200
        guides = client.get("/api/guides").json()
        assert len(guides) >= 5
        local = [g for g in guides if g["location_scope"] == "Aracaju-SE"]
        assert len(local) == 1
        assert "Aracaju" in local[0]["title"]
        assert client.get("/api/guides?q=CPF").json()
        assert client.get("/api/guides?category=Saúde").json()
        assert client.get("/api/guides/99999").status_code == 404

def test_registration_login_duplicate_and_invalid_password():
    with TestClient(app) as client:
        payload = {"name":"Pessoa Teste","email":"novo@example.com","password":"senha-forte-123"}
        created = client.post("/api/auth/register", json=payload)
        assert created.status_code == 201
        assert created.json()["token_type"] == "bearer"
        assert client.post("/api/auth/register", json=payload).status_code == 409
        assert client.post("/api/auth/login", json={"email":payload["email"],"password":"errada-123"}).status_code == 401
        assert client.post("/api/auth/login", json={"email":payload["email"],"password":payload["password"]}).status_code == 200
        weak = client.post("/api/auth/register", json={"name":"Ab","email":"curto@example.com","password":"123"})
        assert weak.status_code == 422

def test_authenticated_profile_favorites_and_history():
    with TestClient(app) as client:
        assert client.get("/api/me").status_code == 401
        assert client.get("/api/favorites").status_code == 401
        assert client.get("/api/history").status_code == 401
        assert client.post("/api/assistant", json={"question":"Como faço isso?"}).status_code == 401
        headers = auth_headers(client, "favorito@example.com")
        assert client.get("/api/me", headers=headers).status_code == 200
        guide_id = client.get("/api/guides").json()[0]["id"]
        assert client.post(f"/api/favorites/{guide_id}", headers=headers).status_code == 204
        assert client.post(f"/api/favorites/{guide_id}", headers=headers).status_code == 204
        assert any(g["id"] == guide_id for g in client.get("/api/favorites", headers=headers).json())
        assert client.delete(f"/api/favorites/{guide_id}", headers=headers).status_code == 204
        assert all(g["id"] != guide_id for g in client.get("/api/favorites", headers=headers).json())
        assert client.post("/api/favorites/99999", headers=headers).status_code == 404
        assert client.get("/api/history", headers=headers).json() == []

def test_admin_endpoint_requires_key():
    with TestClient(app) as client:
        payload = {"title":"Teste","category":"Teste","summary":"Resumo","steps":["Passo"],"documents":[],"url":"https://www.gov.br/","warning":"Confirme no canal oficial."}
        assert client.post("/api/admin/guides", json=payload).status_code == 403

def test_assistant_reports_missing_configuration(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with TestClient(app) as client:
        headers = auth_headers(client, "ia@example.com")
        response = client.post("/api/assistant", headers=headers, json={"question":"Como consultar meu CPF?"})
        assert response.status_code == 503
