#!/usr/bin/env python3
import json
import os
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8787"))
DB_PATH = os.path.join(os.path.dirname(__file__), "guanglun_card_submissions.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS submissions (
          id TEXT PRIMARY KEY,
          created_at TEXT NOT NULL,
          emp_id TEXT NOT NULL,
          name TEXT NOT NULL,
          en_name TEXT NOT NULL,
          dept TEXT NOT NULL,
          photo_data_url TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def row_to_record(row):
    return {
        "id": row["id"],
        "createdAt": row["created_at"],
        "employeeData": {
            "empId": row["emp_id"],
            "name": row["name"],
            "enName": row["en_name"],
            "dept": row["dept"],
        },
        "photoDataURL": row["photo_data_url"],
    }


class Handler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def _json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/health":
            self._json(200, {"ok": True})
            return
        if self.path == "/api/submissions":
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM submissions ORDER BY datetime(created_at) DESC"
            ).fetchall()
            conn.close()
            self._json(200, {"items": [row_to_record(r) for r in rows]})
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self):
        if self.path != "/api/submissions":
            self._json(404, {"error": "Not found"})
            return
        try:
            body = self._read_json()
            employee = body.get("employeeData") or {}
            emp_id = str(employee.get("empId", "")).strip()
            name = str(employee.get("name", "")).strip()
            en_name = str(employee.get("enName", "")).strip()
            dept = str(employee.get("dept", "")).strip()
            photo = str(body.get("photoDataURL", "")).strip()
            rec_id = str(body.get("id", f"card_{int(datetime.now().timestamp()*1000)}")).strip()
            created_at = str(body.get("createdAt", datetime.utcnow().isoformat())).strip()
            if not all([emp_id, name, en_name, dept, photo]):
                self._json(400, {"error": "Missing required fields"})
                return
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM submissions WHERE emp_id = ?", (emp_id,))
            conn.execute(
                """
                INSERT INTO submissions (id, created_at, emp_id, name, en_name, dept, photo_data_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (rec_id, created_at, emp_id, name, en_name, dept, photo),
            )
            conn.commit()
            conn.close()
            self._json(201, {"ok": True, "id": rec_id})
        except Exception as exc:
            self._json(500, {"error": str(exc)})

    def do_DELETE(self):
        prefix = "/api/submissions/"
        if not self.path.startswith(prefix):
            self._json(404, {"error": "Not found"})
            return
        rec_id = unquote(self.path[len(prefix) :]).strip()
        if not rec_id:
            self._json(400, {"error": "Missing id"})
            return
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM submissions WHERE id = ?", (rec_id,))
        conn.commit()
        conn.close()
        self._json(200, {"ok": True})


if __name__ == "__main__":
    init_db()
    print(f"Guanglun card server running on http://{HOST}:{PORT}")
    print(f"SQLite DB: {DB_PATH}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
