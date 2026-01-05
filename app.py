import os
import psycopg2
import psycopg2.extras
from flask import Flask
from datetime import datetime, timezone, date
from jinja2 import Template

app = Flask(__name__)

# ================= CONFIG =================
DATABASE_URL = os.environ["DATABASE_URL"]

# ================= DB =====================
def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ================= RENDER =================
def render_index(**context):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "index.html")

    with open(path, "r", encoding="utf-8") as f:
        template = Template(f.read())

    return template.render(**context)

# ================= ROUTES =================
@app.route("/")
def index():
    with get_conn() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            # --- scanner status ---
            cur.execute("SELECT * FROM scanner_status LIMIT 1")
            status = cur.fetchone()

            # --- alerts: latest per symbol/type, sorted newest → oldest ---
            cur.execute("""
                SELECT *
                FROM (
                    SELECT DISTINCT ON (symbol, type)
                        symbol,
                        type,
                        signal_time,
                        price,
                        rating
                    FROM alerts
                    ORDER BY
                        symbol,
                        type,
                        signal_time DESC
                ) t
                ORDER BY signal_time DESC
                LIMIT 25
            """)
            alerts = cur.fetchall()

    # ================= HEALTH LOGIC =================
    now = datetime.now(timezone.utc)
    healthy = False
    last_run = None

    if status and status.get("last_run"):
        last_run = status["last_run"]

        if isinstance(last_run, date) and not isinstance(last_run, datetime):
            last_run = datetime.combine(
                last_run,
                datetime.min.time(),
                tzinfo=timezone.utc
            )

        healthy = (now - last_run).total_seconds() < 900  # 15 minutes

    return render_index(
        healthy=healthy,
        last_run=last_run,
        alerts=alerts,
    )

@app.route("/health")
def health():
    return "ok"
