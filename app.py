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
    symbol = request.args.get("symbol", "").strip()
    side = request.args.get("type", "").strip()
    hours = request.args.get("hours", type=int)
    page = max(request.args.get("page", 1, type=int), 1)

    offset = (page - 1) * PAGE_SIZE

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # -------- scanner status --------
            cur.execute("SELECT * FROM scanner_status LIMIT 1")
            status = cur.fetchone()

            # -------- WHERE builder (alerts table) --------
            where = []
            params = {}

            if symbol:
                where.append("a.symbol ILIKE %(symbol)s")
                params["symbol"] = f"%{symbol}%"

            if side:
                where.append("a.type = %(type)s")
                params["type"] = side

            if hours:
                where.append("a.signal_time >= NOW() - INTERVAL '%(hours)s hours'")
                params["hours"] = hours

            where_sql = "WHERE " + " AND ".join(where) if where else ""

            # -------- total alerts (for pagination) --------
            cur.execute(
                f"SELECT COUNT(*) FROM alerts a {where_sql}",
                params
            )
            total_alerts = cur.fetchone()["count"]
            total_pages = max(math.ceil(total_alerts / PAGE_SIZE), 1)

            # -------- combined alerts + performance --------
            cur.execute(
                f"""
                SELECT
                    a.signal_time,
                    a.symbol,
                    a.type,
                    a.price AS entry_price,
                    a.rating,

                    p1.return_pct  AS return_1h,
                    p4.return_pct  AS return_4h,
                    p24.return_pct AS return_24h

                FROM alerts a

                LEFT JOIN alert_performance p1
                  ON p1.alert_id = a.id AND p1.horizon_hours = 1

                LEFT JOIN alert_performance p4
                  ON p4.alert_id = a.id AND p4.horizon_hours = 4

                LEFT JOIN alert_performance p24
                  ON p24.alert_id = a.id AND p24.horizon_hours = 24

                {where_sql}
                ORDER BY a.signal_time DESC
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                {
                    **params,
                    "limit": PAGE_SIZE,
                    "offset": offset,
                }
            )

            rows = cur.fetchall()

    # -------- health --------
    healthy = False
    last_run = None
    now = datetime.now(timezone.utc)

    if status and status.get("last_run"):
        last_run = status["last_run"]
        if isinstance(last_run, date) and not isinstance(last_run, datetime):
            last_run = datetime.combine(
                last_run,
                datetime.min.time(),
                tzinfo=timezone.utc
            )
        healthy = (now - last_run).total_seconds() < 900  # 15 min

    return render_index(
        healthy=healthy,
        last_run=last_run,

        # combined table rows
        rows=rows,

        # pagination
        page=page,
        total_pages=total_pages,

        # filter state
        symbol=symbol,
        type_filter=side,
        hours=hours or ""
    )

@app.route("/health")
def health():
    return "ok"
