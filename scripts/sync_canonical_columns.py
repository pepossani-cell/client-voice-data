"""
Sync canonical columns in vox_popular.ticket_insights for reprocessed tickets.

Canonical (empirically correct):
  - product_area   (Produto L1 v3)
  - service_type   (Atendimento v3)

App-facing columns currently in drift:
  - product_area_l1
  - atendimento_type

This script aligns product_area_l1 := product_area and
atendimento_type := service_type for tickets with processing_phase IS NOT NULL.

Usage:
  python -X utf8 scripts/sync_canonical_columns.py          # dry-run (counts only)
  python -X utf8 scripts/sync_canonical_columns.py --apply  # execute update
"""

from __future__ import annotations

import argparse
import os
import sys


def _safe_stdout_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _connect():
    import psycopg2
    from dotenv import load_dotenv

    load_dotenv()
    host = os.getenv("VOX_POPULAR_HOST")
    port = os.getenv("VOX_POPULAR_PORT")
    db = os.getenv("VOX_POPULAR_DB")
    user = os.getenv("VOX_POPULAR_USER")
    pwd = os.getenv("VOX_POPULAR_PASSWORD")

    if not host or not db or not user or not pwd:
        missing = [k for k in ("VOX_POPULAR_HOST", "VOX_POPULAR_DB", "VOX_POPULAR_USER", "VOX_POPULAR_PASSWORD") if not os.getenv(k)]
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")

    kwargs = {"host": host, "dbname": db, "user": user, "password": pwd}
    if port:
        kwargs["port"] = port

    conn = psycopg2.connect(**kwargs)
    conn.autocommit = False
    return conn


def _fetchone(cur, sql: str, params=None):
    if params is None:
        cur.execute(sql)
    else:
        cur.execute(sql, params)
    return cur.fetchone()


def _has_columns(cur, *column_names: str) -> bool:
    row = _fetchone(
        cur,
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_name = 'ticket_insights'
          AND column_name = ANY(%s)
        """,
        [list(column_names)],
    )
    return int(row[0]) == len(column_names)


def _print_kv(k: str, v) -> None:
    print(f"{k:45s} {v}")


def _count_mismatches(cur) -> tuple[int, int]:
    row = _fetchone(
        cur,
        """
        SELECT
          COUNT(*) FILTER (WHERE product_area_l1 IS NOT NULL AND product_area IS NOT NULL AND product_area_l1 <> product_area) AS mismatch_product,
          COUNT(*) FILTER (WHERE atendimento_type IS NOT NULL AND service_type IS NOT NULL AND atendimento_type <> service_type) AS mismatch_atendimento
        FROM ticket_insights
        WHERE processing_phase IS NOT NULL
        """,
    )
    return int(row[0]), int(row[1])


def main() -> int:
    _safe_stdout_utf8()
    parser = argparse.ArgumentParser(description="Sync canonical columns for reprocessed tickets")
    parser.add_argument("--apply", action="store_true", help="Apply updates (default is dry-run)")
    args = parser.parse_args()

    conn = _connect()
    cur = conn.cursor()

    print("=" * 80)
    print("SYNC CANONICAL COLUMNS (product_area_l1 / atendimento_type)")
    print("=" * 80)

    if not _has_columns(cur, "product_area_l1", "atendimento_type", "product_area", "service_type"):
        print("[SKIP] Required compatibility/canonical columns are not all present in ticket_insights.")
        conn.rollback()
        conn.close()
        return 0

    # Preflight: count rows in scope
    row = _fetchone(
        cur,
        """
        SELECT
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE processing_phase IS NOT NULL) AS processed,
          COUNT(*) FILTER (WHERE processing_phase IS NOT NULL AND product_area IS NOT NULL) AS processed_with_product,
          COUNT(*) FILTER (WHERE processing_phase IS NOT NULL AND service_type IS NOT NULL) AS processed_with_service
        FROM ticket_insights
        """,
    )
    total, processed, with_product, with_service = row
    _print_kv("Total tickets", f"{total:,}")
    _print_kv("Processed (processing_phase NOT NULL)", f"{processed:,}")
    _print_kv("Processed with product_area", f"{with_product:,}")
    _print_kv("Processed with service_type", f"{with_service:,}")

    mm_prod, mm_at = _count_mismatches(cur)
    _print_kv("Mismatches before (product_area_l1)", f"{mm_prod:,}")
    _print_kv("Mismatches before (atendimento_type)", f"{mm_at:,}")

    if not args.apply:
        print("\n[DRY RUN] No changes applied. Re-run with --apply to execute.")
        conn.rollback()
        conn.close()
        return 0

    # Execute update
    print("\n[APPLY] Updating product_area_l1 and atendimento_type for processed tickets...")
    cur.execute(
        """
        UPDATE ticket_insights
        SET
          product_area_l1 = product_area,
          atendimento_type = service_type
        WHERE processing_phase IS NOT NULL
          AND (
            product_area_l1 IS DISTINCT FROM product_area
            OR atendimento_type IS DISTINCT FROM service_type
          )
        """
    )
    updated = cur.rowcount
    conn.commit()
    _print_kv("Rows updated", f"{updated:,}")

    # Post-check
    mm_prod_after, mm_at_after = _count_mismatches(cur)
    _print_kv("Mismatches after (product_area_l1)", f"{mm_prod_after:,}")
    _print_kv("Mismatches after (atendimento_type)", f"{mm_at_after:,}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

