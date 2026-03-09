"""
Report: Unprocessed backlog in ticket_insights (NO LLM).

Goal:
  Explain what remains with processing_phase IS NULL:
  - how much is actually eligible for the pipeline (conversation present + len>100)
  - age distribution (month buckets)
  - status/via_channel/clinic_id coverage
  - conversation shape (length buckets, no-dialog indicator)
  - spam indicators (CJK chars)

Usage:
  python scripts/report_unprocessed_backlog.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

from dotenv import load_dotenv


def _connect():
    import psycopg2

    load_dotenv()
    host = os.getenv("VOX_POPULAR_HOST")
    port = os.getenv("VOX_POPULAR_PORT")
    db = os.getenv("VOX_POPULAR_DB")
    user = os.getenv("VOX_POPULAR_USER")
    pwd = os.getenv("VOX_POPULAR_PASSWORD")

    if not host:
        raise RuntimeError("VOX_POPULAR_HOST not set. Check .env / environment variables.")

    conn = psycopg2.connect(host=host, port=port, dbname=db, user=user, password=pwd)
    conn.autocommit = True
    return conn


def _print_kv(k: str, v):
    print(f"{k:35s} {v}")


def main() -> int:
    # Ensure UTF-8 output on Windows terminals
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    conn = _connect()
    cur = conn.cursor()

    print("=" * 90)
    print("UNPROCESSED BACKLOG REPORT (ticket_insights) — NO LLM")
    print(f"Generated at: {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 90)

    # ------------------------------------------------------------------
    # 0) Global counts
    # ------------------------------------------------------------------
    cur.execute("SELECT COUNT(*) FROM ticket_insights")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM ticket_insights WHERE processing_phase IS NOT NULL")
    processed = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM ticket_insights WHERE processing_phase IS NULL")
    unprocessed = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM ticket_insights
        WHERE processing_phase IS NULL
          AND full_conversation IS NOT NULL
          AND LENGTH(full_conversation) > 100
        """
    )
    eligible = cur.fetchone()[0]

    _print_kv("TOTAL tickets", f"{total:,}")
    _print_kv("Processed (phase NOT NULL)", f"{processed:,} ({processed/total*100:.1f}%)")
    _print_kv("Unprocessed (phase NULL)", f"{unprocessed:,} ({unprocessed/total*100:.1f}%)")
    _print_kv(
        "Eligible for pipeline (NULL + conv>100)",
        f"{eligible:,} ({eligible/max(unprocessed,1)*100:.1f}% of NULL-phase)",
    )
    _print_kv(
        "NOT eligible (NULL but conv missing/short)",
        f"{unprocessed-eligible:,} ({(unprocessed-eligible)/max(unprocessed,1)*100:.1f}% of NULL-phase)",
    )

    # ------------------------------------------------------------------
    # 1) Age distribution (created_at)
    # ------------------------------------------------------------------
    print("\n" + "-" * 90)
    print("AGE DISTRIBUTION (ticket_created_at)")
    print("-" * 90)

    cur.execute(
        "SELECT MIN(ticket_created_at), MAX(ticket_created_at) FROM ticket_insights WHERE processing_phase IS NULL"
    )
    mn, mx = cur.fetchone()
    _print_kv("Unprocessed created_at MIN", mn)
    _print_kv("Unprocessed created_at MAX", mx)

    cur.execute(
        """
        SELECT DATE_TRUNC('month', ticket_created_at) AS month, COUNT(*)
        FROM ticket_insights
        WHERE processing_phase IS NULL
        GROUP BY 1
        ORDER BY 1
        """
    )
    rows = cur.fetchall()
    print("\nUnprocessed by month:")
    for month, n in rows:
        print(f"  {month:%Y-%m}  {n:>7,}  ({n/max(unprocessed,1)*100:>5.1f}%)")

    # ------------------------------------------------------------------
    # 2) Status / channel / clinic_id coverage
    # ------------------------------------------------------------------
    print("\n" + "-" * 90)
    print("BACKLOG PROFILE (status / via_channel / clinic_id)")
    print("-" * 90)

    cur.execute(
        "SELECT status, COUNT(*) FROM ticket_insights WHERE processing_phase IS NULL GROUP BY status ORDER BY COUNT(*) DESC"
    )
    print("\nstatus (unprocessed):")
    for status, n in cur.fetchall():
        print(f"  {str(status):20s} {n:>7,} ({n/max(unprocessed,1)*100:>5.1f}%)")

    cur.execute(
        "SELECT via_channel, COUNT(*) FROM ticket_insights WHERE processing_phase IS NULL GROUP BY via_channel ORDER BY COUNT(*) DESC"
    )
    print("\nvia_channel (unprocessed):")
    for ch, n in cur.fetchall():
        print(f"  {str(ch):20s} {n:>7,} ({n/max(unprocessed,1)*100:>5.1f}%)")

    cur.execute(
        """
        SELECT
          COUNT(*) FILTER (WHERE clinic_id IS NULL OR clinic_id = 0) AS no_clinic,
          COUNT(*) FILTER (WHERE clinic_id IS NOT NULL AND clinic_id > 0) AS has_clinic
        FROM ticket_insights
        WHERE processing_phase IS NULL
        """
    )
    no_clinic, has_clinic = cur.fetchone()
    _print_kv("\nclinic_id missing/0 (unprocessed)", f"{no_clinic:,} ({no_clinic/max(unprocessed,1)*100:.1f}%)")
    _print_kv("clinic_id present>0 (unprocessed)", f"{has_clinic:,} ({has_clinic/max(unprocessed,1)*100:.1f}%)")

    # ------------------------------------------------------------------
    # 3) Conversation shape diagnostics
    # ------------------------------------------------------------------
    print("\n" + "-" * 90)
    print("CONVERSATION SHAPE (unprocessed)")
    print("-" * 90)

    cur.execute(
        """
        SELECT
          COUNT(*) FILTER (WHERE full_conversation IS NULL) AS null_conv,
          COUNT(*) FILTER (WHERE full_conversation IS NOT NULL AND LENGTH(full_conversation) <= 100) AS short_conv,
          COUNT(*) FILTER (WHERE full_conversation IS NOT NULL AND full_conversation NOT LIKE '%:%') AS no_colon_conv,
          COUNT(*) FILTER (WHERE full_conversation ~ '[\\u4e00-\\u9fff]') AS has_cjk
        FROM ticket_insights
        WHERE processing_phase IS NULL
        """
    )
    null_conv, short_conv, no_colon, has_cjk = cur.fetchone()
    _print_kv("full_conversation NULL", f"{null_conv:,} ({null_conv/max(unprocessed,1)*100:.1f}%)")
    _print_kv("full_conversation len<=100", f"{short_conv:,} ({short_conv/max(unprocessed,1)*100:.1f}%)")
    _print_kv("full_conversation no ':'", f"{no_colon:,} ({no_colon/max(unprocessed,1)*100:.1f}%)")
    _print_kv("contains CJK chars (spam)", f"{has_cjk:,} ({has_cjk/max(unprocessed,1)*100:.1f}%)")

    cur.execute(
        """
        WITH bucketed AS (
          SELECT
            CASE
              WHEN full_conversation IS NULL THEN 'NULL'
              WHEN LENGTH(full_conversation) <= 100 THEN '<=100'
              WHEN LENGTH(full_conversation) <= 500 THEN '101-500'
              WHEN LENGTH(full_conversation) <= 2000 THEN '501-2000'
              ELSE '>2000'
            END AS bucket
          FROM ticket_insights
          WHERE processing_phase IS NULL
        )
        SELECT bucket, COUNT(*)
        FROM bucketed
        GROUP BY bucket
        ORDER BY
          CASE bucket
            WHEN 'NULL' THEN 0
            WHEN '<=100' THEN 1
            WHEN '101-500' THEN 2
            WHEN '501-2000' THEN 3
            ELSE 4
          END
        """
    )
    print("\nfull_conversation length buckets (unprocessed):")
    for bucket, n in cur.fetchall():
        print(f"  {bucket:10s} {n:>7,} ({n/max(unprocessed,1)*100:>5.1f}%)")

    # ------------------------------------------------------------------
    # 4) If eligible backlog is small, show a quick sample IDs
    # ------------------------------------------------------------------
    print("\n" + "-" * 90)
    print("SAMPLES (eligible backlog)")
    print("-" * 90)

    cur.execute(
        """
        SELECT zendesk_ticket_id, ticket_created_at, status, via_channel, clinic_id,
               LENGTH(full_conversation) AS conv_len
        FROM ticket_insights
        WHERE processing_phase IS NULL
          AND full_conversation IS NOT NULL
          AND LENGTH(full_conversation) > 100
        ORDER BY ticket_created_at DESC
        LIMIT 10
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("No eligible tickets (unexpected if eligible > 0).")
    else:
        print("Top 10 most recent eligible tickets:")
        for tid, created_at, status, ch, clinic_id, conv_len in rows:
            print(
                f"  #{tid} | {created_at:%Y-%m-%d} | status={status} | channel={ch} | clinic_id={clinic_id} | conv_len={conv_len}"
            )

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

