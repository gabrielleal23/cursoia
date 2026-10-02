import os
import tempfile

os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ADMIN_PASSWORD"] = "admin-pass"
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

REG = {"fullName": "Ana Pérez", "area": "Plataforma", "cargo": "QA / Pruebas", "nivel": "Básica", "consent": True}
SUMMARY = {
    "step": 2, "done": ["inicio", "m1"], "pre": {"0": 2, "1": 3}, "post": {"0": 4},
    "scores": {"mythsC": 3, "mythsT": 5, "privC": 1, "privT": 2, "quizC": 2, "quizT": 3, "rub": 1},
}


def auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_full_flow():
    with TestClient(app) as c:
        assert c.get("/health").json() == {"status": "ok"}
        assert "Ruta" in c.get("/").text

        # registro exige consentimiento
        assert c.post("/api/register", json={**REG, "consent": False}).status_code == 422
        r = c.post("/api/register", json=REG)
        assert r.status_code == 201
        token, pid = r.json()["token"], r.json()["participant"]["id"]

        # sin token -> 401
        assert c.get("/api/me").status_code == 401
        assert c.get("/api/me", headers=auth(token)).json()["state"] is None

        # guardar progreso
        state = {"step": 2, "notes": "privado", "updatedAt": 123}
        assert c.put("/api/state", headers=auth(token), json={"state": state, "summary": SUMMARY}).status_code == 204
        me = c.get("/api/me", headers=auth(token)).json()
        assert me["state"]["notes"] == "privado"

        # resumen inválido rechazado
        bad = {**SUMMARY, "done": ["hack"]}
        assert c.put("/api/state", headers=auth(token), json={"state": {}, "summary": bad}).status_code == 422

        # reemplazo de módulos / autoevaluación
        s2 = {**SUMMARY, "done": ["inicio"], "pre": {"0": 5}, "post": {}}
        assert c.put("/api/state", headers=auth(token), json={"state": state, "summary": s2}).status_code == 204

        # admin: sin token -> 401, login malo -> 401
        assert c.get("/api/admin/participants").status_code == 401
        assert c.get("/api/admin/participants", headers=auth(token)).status_code == 401
        assert c.post("/api/admin/login", json={"password": "x"}).status_code == 401
        at = c.post("/api/admin/login", json={"password": "admin-pass"}).json()["token"]

        rows = c.get("/api/admin/participants", headers=auth(at)).json()
        assert len(rows) == 1 and rows[0]["id"] == pid
        assert rows[0]["done"] == ["inicio"] and rows[0]["pre"] == {"0": 5} and rows[0]["post"] == {}
        assert rows[0]["scores"]["mythsC"] == 3
        assert "notes" not in str(rows[0])  # el estado privado NO se expone

        # editar perfil
        up = {k: REG[k] for k in ("fullName", "area", "cargo", "nivel")}
        up["area"] = "Integraciones"
        assert c.put("/api/me", headers=auth(token), json=up).json()["area"] == "Integraciones"

        # eliminar
        assert c.delete(f"/api/admin/participants/{pid}", headers=auth(at)).status_code == 204
        assert c.get("/api/me", headers=auth(token)).status_code == 401
        assert c.get("/api/admin/participants", headers=auth(at)).json() == []


def test_admin_token_tampering():
    with TestClient(app) as c:
        assert c.get("/api/admin/me", headers=auth("admin.9999999999.deadbeef")).status_code == 401
