import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["DATABASE_URL"] = "sqlite:///./test_resolve_aqui.db"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough"

from fastapi.testclient import TestClient
from backend.main import app

def test_health_and_guides():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        guides = client.get("/api/guides")
        assert guides.status_code == 200
        assert len(guides.json()) >= 1

def test_register_login_and_favorites():
    with TestClient(app) as client:
        payload = {"name":"Pessoa Teste","email":"teste@example.com","password":"senha-forte-123"}
        response = client.post("/api/auth/register", json=payload)
        assert response.status_code == 201
        token = response.json()["access_token"]
        headers = {"Authorization":f"Bearer {token}"}
        me = client.get("/api/me", headers=headers)
        assert me.status_code == 200
        guide_id = client.get("/api/guides").json()[0]["id"]
        favorite = client.post(f"/api/favorites/{guide_id}", headers=headers)
        assert favorite.status_code == 204
        saved = client.get("/api/favorites", headers=headers)
        assert saved.status_code == 200
        assert any(item["id"] == guide_id for item in saved.json())
        login = client.post("/api/auth/login", json={"email":payload["email"],"password":payload["password"]})
        assert login.status_code == 200
