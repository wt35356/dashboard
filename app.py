import os
import psycopg2
import psycopg2.extras
from flask import Flask, render_template
from datetime import datetime, timezone, date

app = Flask(__name__)

# DATABASE_URL must be set in Railway variables
DATABASE_URL = os.environ["DATABASE_URL"]

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

@app.route("/")
def index():
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Scanner status (singleton row)
            cur.execute("SELECT * FROM scanner_status LIMIT 1")
            status = cur.fetchone()

            # Recent alerts
            cur.execute("""
                SELECT symbol, type, signal_time, price, rating
                FROM alerts
                ORDER BY signal_time DESC
                LIMIT 25
            """)
            alerts = cur.fetchall()

    now = datetime.now(timezone.utc)

    healthy = False
    last_run_display = "N/A"

    if status and status.get("last_run"):
        last_run = status["last_run"]

        # Handle DATE vs TIMESTAMP safely
        if isinstance(last_run, date) and not isinstance(last_run, datetime):
            last_run = datetime.combine(
                last_run,
                datetime.min.time(),
                tzinfo=timezone.utc
            )

        last_run_display = last_run.isoformat()
        delta = now - last_run
        healthy = delta.total_seconds() < 900  # 15 minutes

    return render_template(
        "index.html",
        healthy=healthy,
        last_run=last_run_display,
        alerts=alerts,
    )

@app.route("/health")
def health():
    return {"status": "ok"}
