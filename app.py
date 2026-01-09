import os
import psycopg2
import psycopg2.extras
from flask import Flask
from datetime import datetime, timezone, date
from jinja2 import Template

# ================= APP =================
app = Flask(__name__)   # <<< MUST BE BEFORE @app.route

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

            # --- alerts ---
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
                    ORDER BY symbol, type, signal_time DESC
                ) t
                ORDER BY signal_time DESC
                LIMIT 25
            """)
            alerts = cur.fetchall()

            # --- performance ---
            cur.execute("""
                SELECT
                    symbol,
                    type,
                    rating,
                    entry_price,
                    exit_price,
                    return_pct,
                    exit_time
                FROM alert_performance
                ORDER BY exit_time DESC
                LIMIT 25
            """)
            performance = cur.fetchall()

            cur.execute("""
                SELECT
                    rating,
                    COUNT(*) AS n,
                    ROUND(AVG(return_pct)::numeric, 2) AS avg_return,
                    ROUND(
                        SUM(CASE WHEN return_pct > 0 THEN 1 ELSE 0 END)::numeric
                        / COUNT(*),
                        2
                    ) AS hit_rate
                FROM alert_performance
                GROUP BY rating
                ORDER BY rating
            """)
            perf_by_rating = cur.fetchall()

    # ================= HEALTH =================
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
        healthy = (now - last_run).total_seconds() < 900

    return render_index(
        healthy=healthy,
        last_run=last_run,
        alerts=alerts,
        performance=performance,
        perf_by_rating=perf_by_rating,
    )

@app.route("/health")
def health():
    return "ok"
