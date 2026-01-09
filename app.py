import os
import math
import psycopg2
import psycopg2.extras
from flask import Flask, request
from datetime import datetime, timezone, date
from jinja2 import Template

# ================= APP =================
app = Flask(__name__)

# ================= CONFIG =================
DATABASE_URL = os.environ["DATABASE_URL"]
PAGE_SIZE = 20

# ================= DB =====================
def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ================= RENDER =================
def render_index(**context):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "index.html")

    with open(path, "r", encoding="utf-8") as f:
        template = Template(f.read())

    # IMPORTANT: explicitly pass request
    return template.render(request=request, **context)

# ================= ROUTES =================
@app.route("/")
def index():

    # -------- URL params --------
    symbol = request.args.get("symbol")
    side = request.args.get("type")
    hours = request.args.get("hours", type=int)
    page = max(request.args.get("page", 1, type=int), 1)

    offset = (page - 1) * PAGE_SIZE

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # -------- scanner status --------
            cur.execute("SELECT * FROM scanner_status LIMIT 1")
            status = cur.fetchone()

            # -------- WHERE builder --------
            where = []
            params = {}

            if symbol:
                where.append("symbol ILIKE %(symbol)s")
                params["symbol"] = f"%{symbol}%"

            if side:
                where.append("type = %(type)s")
                params["type"] = side

            if hours:
                where.append("signal_time >= NOW() - INTERVAL '%(hours)s hours'")
                params["hours"] = hours

            where_sql = "WHERE " + " AND ".join(where) if where else ""

            # -------- total alerts (for pagination) --------
            cur.execute(
                f"SELECT COUNT(*) FROM alerts {where_sql}",
                params
            )
            total_alerts = cur.fetchone()["count"]
            total_pages = max(math.ceil(total_alerts / PAGE_SIZE), 1)

            # -------- paginated alerts --------
            cur.execute(
                f"""
                SELECT
                    symbol,
                    type,
                    signal_time,
                    price,
                    rating
                FROM alerts
                {where_sql}
                ORDER BY signal_time DESC
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                {**params, "limit": PAGE_SIZE, "offset": offset}
            )
            alerts = cur.fetchall()

            # -------- latest performance --------
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
                LIMIT 20
            """)
            performance = cur.fetchall()

    # -------- health --------
    healthy = False
    last_run = None
    now = datetime.now(timezone.utc)

    if status and status.get("last_run"):
        last_run = status["last_run"]
        if isinstance(last_run, date) and not isinstance(last_run, datetime):
            last_run = datetime.combine(last_run, datetime.min.time(), tzinfo=timezone.utc)
        healthy = (now - last_run).total_seconds() < 900

    return render_index(
        healthy=healthy,
        last_run=last_run,
        alerts=alerts,
        performance=performance,
        page=page,
        total_pages=total_pages,
        symbol=symbol or "",
        type_filter=side or "",
        hours=hours or ""
    )

@app.route("/health")
def health():
    return "ok"
