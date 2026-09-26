from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_sets_csrf_cookie_and_security_headers() -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert "aqs_csrf" in r.cookies
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_post_without_csrf_token_is_rejected() -> None:
    fresh = TestClient(app)
    r = fresh.post("/api/v1/health")
    assert r.status_code == 403


def test_post_from_foreign_origin_is_rejected() -> None:
    fresh = TestClient(app)
    token = fresh.get("/api/v1/health").cookies["aqs_csrf"]
    r = fresh.post(
        "/api/v1/health",
        headers={"X-CSRF-Token": token, "Origin": "https://evil.example"},
    )
    assert r.status_code == 403


def test_post_with_matching_token_passes_csrf() -> None:
    fresh = TestClient(app)
    token = fresh.get("/api/v1/health").cookies["aqs_csrf"]
    r = fresh.post(
        "/api/v1/health",
        headers={"X-CSRF-Token": token, "Origin": "http://localhost:5173"},
    )
    assert r.status_code == 405  # got past CSRF; route only allows GET
