import os
import psycopg2
import psycopg2.extras
from flask import Flask, render_template
from datetime import datetime, timezone

app = Flask(__name__)
DATABASE_URL = os.environ["DATABASE_URL"]

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

@app.route("/")
def index():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM scanner_status LIMIT 1")
            status = cur.fetchone()

            cur.execute("""
                SELECT symbol, type, signal_time, price, rating
                FROM alerts
                ORDER BY signal_time DESC
                LIMIT 25
            """)
            alerts = cur.fetchall()

    now = datetime.now(timezone.utc)

    healthy = False
    if status and status["last_run"]:
        delta = now - status["last_run"]
        healthy = delta.total_seconds() < 900  # 15 min

    return render_template(
        "index.html",
        status=status,
        alerts=alerts,
        healthy=healthy
    )

@app.route("/health")
def health():
    return {"status": "ok"}
