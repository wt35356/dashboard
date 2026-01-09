@app.route("/")
def index():
    with get_conn() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            # --- scanner status ---
            cur.execute("SELECT * FROM scanner_status LIMIT 1")
            status = cur.fetchone()

            # --- alerts: latest per symbol/type ---
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

            # ================= PERFORMANCE =================

            # 1) Performance table (latest evaluated alerts)
            cur.execute("""
                SELECT
                    alert_id,
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

            # 2) Performance by rating (core metric)
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

        healthy = (now - last_run).total_seconds() < 900

    return render_index(
        healthy=healthy,
        last_run=last_run,
        alerts=alerts,
        performance=performance,
        perf_by_rating=perf_by_rating,
    )
