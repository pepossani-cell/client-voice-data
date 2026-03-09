"""
Audit: vox_popular.ticket_insights (PostgreSQL) — Phase 3.x empirical checks.

Goal:
  Validate schema + distributions directly from the database (no "docs-only" assumptions).

Usage:
  python -X utf8 scripts/audit_ticket_insights_vox_popular.py
  python -X utf8 scripts/audit_ticket_insights_vox_popular.py --top-n 20
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Iterable, Sequence


def _safe_stdout_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _print_section(title: str) -> None:
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)


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
    conn.autocommit = True
    return conn


def _fetchall(cur, sql: str, params: Sequence | None = None):
    if params is None:
        cur.execute(sql)
    else:
        cur.execute(sql, params)
    return cur.fetchall()


def _fetchone(cur, sql: str, params: Sequence | None = None):
    if params is None:
        cur.execute(sql)
    else:
        cur.execute(sql, params)
    return cur.fetchone()


@dataclass(frozen=True)
class PhaseStats:
    phase: str
    total: int


def _print_kv(key: str, value) -> None:
    print(f"{key:45s} {value}")


def _as_phase_label(phase: str | None) -> str:
    return phase if phase is not None else "NULL"


def main() -> int:
    _safe_stdout_utf8()

    parser = argparse.ArgumentParser(description="Empirical audit of vox_popular.ticket_insights")
    parser.add_argument("--top-n", type=int, default=15, help="Top N categories to print")
    args = parser.parse_args()

    conn = _connect()
    cur = conn.cursor()

    _print_section("0) BASELINE COUNTS")
    total = _fetchone(cur, "SELECT COUNT(*) FROM ticket_insights")[0]
    processed = _fetchone(cur, "SELECT COUNT(*) FROM ticket_insights WHERE processing_phase IS NOT NULL")[0]
    unprocessed = total - processed
    eligible = _fetchone(
        cur,
        """
        SELECT COUNT(*)
        FROM ticket_insights
        WHERE processing_phase IS NULL
          AND full_conversation IS NOT NULL
          AND LENGTH(full_conversation) > 100
        """,
    )[0]
    _print_kv("TOTAL tickets", f"{total:,}")
    _print_kv("Processed (processing_phase NOT NULL)", f"{processed:,} ({processed/total*100:.1f}%)")
    _print_kv("Unprocessed (processing_phase NULL)", f"{unprocessed:,} ({unprocessed/total*100:.1f}%)")
    _print_kv("Eligible backlog (NULL + conv>100)", f"{eligible:,} ({eligible/max(unprocessed,1)*100:.1f}% of NULL)")

    _print_section("1) PROCESSING_PHASE DISTRIBUTION")
    rows = _fetchall(
        cur,
        """
        SELECT processing_phase, COUNT(*) AS n
        FROM ticket_insights
        GROUP BY processing_phase
        ORDER BY n DESC
        """,
    )
    for phase, n in rows:
        lbl = _as_phase_label(phase)
        print(f"{lbl:25s} {n:>9,} ({n/total*100:>5.1f}%)")

    _print_section("2) SCHEMA: KEY COLUMNS (EXISTENCE + TYPES)")
    key_cols = [
        "zendesk_ticket_id",
        "ticket_created_at",
        "ticket_updated_at",
        "status",
        "subject",
        "tags",
        "clinic_id",
        "clinic_id_source",
        "assignee_name",
        "is_claudinha_assigned",
        "via_channel",
        # Taxonomy / Phase 3
        "product_area",
        "product_area_l2",
        "root_cause",
        "service_type",
        "is_proactive",
        "has_interaction",
        "processing_phase",
        # LLM vars
        "sentiment",
        "key_themes",
        "conversation_summary",
        "customer_effort_score",
        "frustration_detected",
        "churn_risk_flag",
        "llm_confidence",
        "llm_model",
        "llm_processed_at",
        # Conversation
        "full_conversation",
        # Versioning
        "version",
        "loaded_at",
    ]

    cols = _fetchall(
        cur,
        """
        SELECT column_name, data_type, character_maximum_length, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'ticket_insights'
        """,
    )
    cols_map = {c[0]: c for c in cols}
    missing = [c for c in key_cols if c not in cols_map]
    if missing:
        _print_kv("[WARN] Missing expected columns", ", ".join(missing))

    for c in key_cols:
        meta = cols_map.get(c)
        if not meta:
            continue
        _, dtype, maxlen, nullable = meta
        suffix = f"({maxlen})" if maxlen else ""
        print(f"{c:25s} {dtype}{suffix:12s} nullable={nullable}")

    # Validate "validation script" assumptions (known drift candidate)
    drift_cols = ["created_at", "updated_at", "tier1_override", "product_area_l1", "atendimento_type"]
    drift_present = _fetchall(
        cur,
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'ticket_insights'
          AND column_name = ANY(%s)
        ORDER BY column_name
        """,
        [drift_cols],
    )
    _print_kv("Columns referenced by some scripts but present?", ", ".join([r[0] for r in drift_present]) or "(none)")

    # If these columns exist, check if they're actually populated and consistent.
    if {"product_area_l1", "atendimento_type"}.issubset(set(cols_map.keys())):
        _print_section("2b) EXTRA COLUMNS FOUND: product_area_l1 / atendimento_type (FILL + CONSISTENCY)")
        row = _fetchone(
            cur,
            """
            SELECT
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE product_area_l1 IS NULL) AS product_area_l1_null,
              COUNT(*) FILTER (WHERE product_area_l1 IS NOT NULL) AS product_area_l1_filled,
              COUNT(*) FILTER (WHERE atendimento_type IS NULL) AS atendimento_type_null,
              COUNT(*) FILTER (WHERE atendimento_type IS NOT NULL) AS atendimento_type_filled
            FROM ticket_insights
            """,
        )
        tot, l1_null, l1_fill, at_null, at_fill = row
        _print_kv("product_area_l1 filled", f"{l1_fill:,} ({l1_fill/tot*100:.1f}%)")
        _print_kv("atendimento_type filled", f"{at_fill:,} ({at_fill/tot*100:.1f}%)")

        rows = _fetchall(
            cur,
            """
            SELECT
              processing_phase,
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE product_area_l1 IS NULL) AS l1_null,
              COUNT(*) FILTER (WHERE atendimento_type IS NULL) AS at_null
            FROM ticket_insights
            GROUP BY processing_phase
            ORDER BY total DESC
            """,
        )
        print("\nNULL rates by phase:")
        for phase, totp, l1n, atn in rows:
            lbl = _as_phase_label(phase)
            print(f"  {lbl:22s} total={totp:>9,} | product_area_l1 NULL={l1n:>9,} | atendimento_type NULL={atn:>9,}")

        # Consistency checks (only where both sides are non-NULL)
        mismatch_l1 = _fetchone(
            cur,
            """
            SELECT COUNT(*)
            FROM ticket_insights
            WHERE processing_phase IS NOT NULL
              AND product_area_l1 IS NOT NULL
              AND product_area IS NOT NULL
              AND product_area_l1 <> product_area
            """,
        )[0]
        mismatch_at = _fetchone(
            cur,
            """
            SELECT COUNT(*)
            FROM ticket_insights
            WHERE processing_phase IS NOT NULL
              AND atendimento_type IS NOT NULL
              AND service_type IS NOT NULL
              AND atendimento_type <> service_type
            """,
        )[0]
        _print_kv("Mismatches: product_area_l1 vs product_area (processed)", f"{mismatch_l1:,}")
        _print_kv("Mismatches: atendimento_type vs service_type (processed)", f"{mismatch_at:,}")

        print(f"\nTop {args.top_n} values for product_area_l1 (overall):")
        rows = _fetchall(
            cur,
            """
            SELECT COALESCE(product_area_l1, 'NULL') AS v, COUNT(*) AS n
            FROM ticket_insights
            GROUP BY 1
            ORDER BY n DESC
            LIMIT %s
            """,
            [args.top_n],
        )
        for v, n in rows:
            print(f"  {v:25s} {n:>9,} ({n/tot*100:>5.1f}%)")

        print(f"\nTop {args.top_n} values for atendimento_type (overall):")
        rows = _fetchall(
            cur,
            """
            SELECT COALESCE(atendimento_type, 'NULL') AS v, COUNT(*) AS n
            FROM ticket_insights
            GROUP BY 1
            ORDER BY n DESC
            LIMIT %s
            """,
            [args.top_n],
        )
        for v, n in rows:
            print(f"  {v:25s} {n:>9,} ({n/tot*100:>5.1f}%)")

        if mismatch_l1:
            print(f"\nTop {args.top_n} mismatch pairs: product_area_l1 <> product_area (processed)")
            rows = _fetchall(
                cur,
                """
                SELECT product_area_l1, product_area, COUNT(*) AS n
                FROM ticket_insights
                WHERE processing_phase IS NOT NULL
                  AND product_area_l1 IS NOT NULL
                  AND product_area IS NOT NULL
                  AND product_area_l1 <> product_area
                GROUP BY 1, 2
                ORDER BY n DESC
                LIMIT %s
                """,
                [args.top_n],
            )
            for l1, pa, n in rows:
                print(f"  {l1:15s} != {pa:20s} n={n:,}")

        if mismatch_at:
            print(f"\nTop {args.top_n} mismatch pairs: atendimento_type <> service_type (processed)")
            rows = _fetchall(
                cur,
                """
                SELECT atendimento_type, service_type, COUNT(*) AS n
                FROM ticket_insights
                WHERE processing_phase IS NOT NULL
                  AND atendimento_type IS NOT NULL
                  AND service_type IS NOT NULL
                  AND atendimento_type <> service_type
                GROUP BY 1, 2
                ORDER BY n DESC
                LIMIT %s
                """,
                [args.top_n],
            )
            for at, st, n in rows:
                print(f"  {at:20s} != {st:20s} n={n:,}")

    _print_section("3) CONSTRAINTS (CHECKS)")
    checks = _fetchall(
        cur,
        """
        SELECT conname, pg_get_constraintdef(oid) AS def
        FROM pg_constraint
        WHERE conrelid = 'ticket_insights'::regclass
          AND contype = 'c'
        ORDER BY conname
        """,
    )
    for name, definition in checks:
        # Keep output short: print name + a few key contains checks
        if name == "check_root_cause_values":
            must_have = ["Contratacao_Acompanhamento", "Contratacao_Suporte_Paciente", "Unclear"]
            has = {k: (k in definition) for k in must_have}
            legacy_markers = ["'unclear'", "'not_applicable'", "'debt_collection'", "'Contratacao'"]
            legacy_has = {k: (k in definition) for k in legacy_markers}
            print(f"{name}:")
            print(f"  contains v3.2 keys: {has}")
            print(f"  contains legacy markers: {legacy_has}")
        else:
            print(f"{name}")

    _print_section("4) PRODUCT_AREA: LEGACY vs V3 (EMPIRICAL)")
    legacy_only = ("BNPL_Cobranca", "BNPL_Financiamento", "BNPL_Suporte", "SaaS_Operacional", "SaaS_Billing", "Venda")
    v3_only = ("BNPL", "SaaS", "Onboarding")

    rows = _fetchall(
        cur,
        """
        SELECT
          (processing_phase IS NOT NULL) AS processed,
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE product_area = ANY(%s)) AS v3_only,
          COUNT(*) FILTER (WHERE product_area = ANY(%s)) AS legacy_only,
          COUNT(*) FILTER (WHERE product_area = 'POS') AS pos,
          COUNT(*) FILTER (WHERE product_area = 'Indeterminado') AS indeterminado,
          COUNT(*) FILTER (WHERE product_area IS NULL) AS nulls
        FROM ticket_insights
        GROUP BY processed
        ORDER BY processed DESC
        """,
        [list(v3_only), list(legacy_only)],
    )
    for processed_flag, tot, v3n, legn, posn, indn, nulln in rows:
        label = "processed" if processed_flag else "unprocessed"
        print(f"{label:12s} total={tot:,} | v3_only={v3n:,} | legacy_only={legn:,} | POS={posn:,} | Indeterminado={indn:,} | NULL={nulln:,}")

    print(f"\nTop {args.top_n} product_area values (overall):")
    rows = _fetchall(
        cur,
        """
        SELECT COALESCE(product_area, 'NULL') AS product_area, COUNT(*) AS n
        FROM ticket_insights
        GROUP BY 1
        ORDER BY n DESC
        LIMIT %s
        """,
        [args.top_n],
    )
    for v, n in rows:
        print(f"  {v:25s} {n:>9,} ({n/total*100:>5.1f}%)")

    _print_section("4b) QUAL PRODUTO ESTÁ MAIS CORRETO? (CONSISTÊNCIA vs NATUREZA EXCLUSIVA)")
    # Use only root_causes that are single-product by definition (per taxonomy spec / pipeline override).
    bnpl_exclusive = (
        "Simulacao_Credito",
        "Contratacao_Acompanhamento",
        "Contratacao_Suporte_Paciente",
        "Endosso_Repasse",
        "Cobranca_Ativa",
    )
    saas_exclusive = (
        "Subscription_Pagamento",
        "Subscription_Cancelamento",
        "Migracao",
    )
    rows = _fetchall(
        cur,
        """
        WITH processed AS (
          SELECT *
          FROM ticket_insights
          WHERE processing_phase IS NOT NULL
        )
        SELECT
          'BNPL_exclusive' AS bucket,
          COUNT(*) AS n,
          COUNT(*) FILTER (WHERE product_area = 'BNPL') AS product_area_ok,
          COUNT(*) FILTER (WHERE product_area_l1 = 'BNPL') AS product_area_l1_ok
        FROM processed
        WHERE root_cause = ANY(%s)
        UNION ALL
        SELECT
          'SaaS_exclusive' AS bucket,
          COUNT(*) AS n,
          COUNT(*) FILTER (WHERE product_area = 'SaaS') AS product_area_ok,
          COUNT(*) FILTER (WHERE product_area_l1 = 'SaaS') AS product_area_l1_ok
        FROM processed
        WHERE root_cause = ANY(%s)
        """,
        [list(bnpl_exclusive), list(saas_exclusive)],
    )
    for bucket, n, pa_ok, l1_ok in rows:
        pa_pct = pa_ok / max(1, n) * 100
        l1_pct = l1_ok / max(1, n) * 100
        print(f"{bucket:15s} n={n:>8,} | product_area ok={pa_ok:>8,} ({pa_pct:>5.1f}%) | product_area_l1 ok={l1_ok:>8,} ({l1_pct:>5.1f}%)")

    print("\nPer-root_cause breakdown (BNPL-exclusive):")
    rows = _fetchall(
        cur,
        """
        SELECT
          root_cause,
          COUNT(*) AS n,
          COUNT(*) FILTER (WHERE product_area <> 'BNPL') AS product_area_wrong,
          COUNT(*) FILTER (WHERE product_area_l1 <> 'BNPL') AS product_area_l1_wrong
        FROM ticket_insights
        WHERE processing_phase IS NOT NULL
          AND root_cause = ANY(%s)
        GROUP BY 1
        ORDER BY n DESC
        """,
        [list(bnpl_exclusive)],
    )
    for rc, n, pa_w, l1_w in rows:
        print(f"  {rc:28s} n={n:>7,} | product_area wrong={pa_w:>6,} | product_area_l1 wrong={l1_w:>6,}")

    print("\nPer-root_cause breakdown (SaaS-exclusive):")
    rows = _fetchall(
        cur,
        """
        SELECT
          root_cause,
          COUNT(*) AS n,
          COUNT(*) FILTER (WHERE product_area <> 'SaaS') AS product_area_wrong,
          COUNT(*) FILTER (WHERE product_area_l1 <> 'SaaS') AS product_area_l1_wrong
        FROM ticket_insights
        WHERE processing_phase IS NOT NULL
          AND root_cause = ANY(%s)
        GROUP BY 1
        ORDER BY n DESC
        """,
        [list(saas_exclusive)],
    )
    for rc, n, pa_w, l1_w in rows:
        print(f"  {rc:28s} n={n:>7,} | product_area wrong={pa_w:>6,} | product_area_l1 wrong={l1_w:>6,}")

    _print_section("4c) DEEP DIVE: mismatch product_area_l1='Onboarding' vs product_area='BNPL' (processed)")
    row = _fetchone(
        cur,
        """
        SELECT
          COUNT(*) AS n,
          COUNT(*) FILTER (WHERE tags ILIKE '%venda_%') AS has_venda_tag,
          COUNT(*) FILTER (WHERE root_cause LIKE 'Contratacao_%') AS is_contratacao,
          COUNT(*) FILTER (WHERE root_cause IN ('Simulacao_Credito','Endosso_Repasse','Cobranca_Ativa')) AS other_bnpl_funnel
        FROM ticket_insights
        WHERE processing_phase IS NOT NULL
          AND product_area_l1 = 'Onboarding'
          AND product_area = 'BNPL'
        """,
    )
    n, has_venda, is_contrat, other_funnel = row
    _print_kv("Total mismatches (Onboarding != BNPL)", f"{n:,}")
    _print_kv("... with tags like venda_%", f"{has_venda:,} ({has_venda/max(1,n)*100:.1f}%)")
    _print_kv("... with root_cause Contratacao_%", f"{is_contrat:,} ({is_contrat/max(1,n)*100:.1f}%)")
    _print_kv("... with other BNPL funnel root_causes", f"{other_funnel:,} ({other_funnel/max(1,n)*100:.1f}%)")

    print(f"\nTop {min(args.top_n, 10)} root_causes within this mismatch:")
    rows = _fetchall(
        cur,
        """
        SELECT root_cause, COUNT(*) AS n
        FROM ticket_insights
        WHERE processing_phase IS NOT NULL
          AND product_area_l1 = 'Onboarding'
          AND product_area = 'BNPL'
        GROUP BY 1
        ORDER BY n DESC
        LIMIT %s
        """,
        [min(args.top_n, 10)],
    )
    for rc, nn in rows:
        print(f"  {str(rc):28s} {nn:>8,}")

    _print_section("5) ROOT_CAUSE: CANONICAL V3.2 vs OTHER")
    canonical_v3_2 = (
        "Simulacao_Credito",
        "Contratacao_Acompanhamento",
        "Contratacao_Suporte_Paciente",
        "Endosso_Repasse",
        "Cobranca_Ativa",
        "Credenciamento",
        "Migracao",
        "Process_Generico",
        "Subscription_Pagamento",
        "Subscription_Cancelamento",
        "Financial_Inquiry",
        "Forma_Pagamento",
        "Negativacao",
        "Operational_Question",
        "Technical_Issue",
        "Acesso",
        "Carne_Capim",
        "Alteracao_Cadastral",
        "Unclear",
    )
    rows = _fetchall(
        cur,
        """
        SELECT
          processing_phase,
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE root_cause IS NULL) AS nulls,
          COUNT(*) FILTER (WHERE root_cause = ANY(%s)) AS canonical_v3_2,
          COUNT(*) FILTER (WHERE root_cause IS NOT NULL AND root_cause <> ALL(%s)) AS noncanonical
        FROM ticket_insights
        GROUP BY processing_phase
        ORDER BY total DESC
        """,
        [list(canonical_v3_2), list(canonical_v3_2)],
    )
    for phase, tot, nulls, canon, noncanon in rows:
        lbl = _as_phase_label(phase)
        print(
            f"{lbl:25s} total={tot:>9,} | root_cause NULL={nulls:>7,} | canonical={canon:>7,} | noncanonical={noncanon:>7,}"
        )

    print(f"\nTop {args.top_n} root_cause values (non-NULL):")
    rows = _fetchall(
        cur,
        """
        SELECT root_cause, COUNT(*) AS n
        FROM ticket_insights
        WHERE root_cause IS NOT NULL
        GROUP BY root_cause
        ORDER BY n DESC
        LIMIT %s
        """,
        [args.top_n],
    )
    for v, n in rows:
        print(f"  {v:30s} {n:>9,} ({n/max(1, processed)*100:>5.1f}% of total processed)")

    # Focus: known drift values
    drift_root_causes = ("unclear", "not_applicable", "debt_collection", "Contratacao")
    rows = _fetchall(
        cur,
        """
        SELECT root_cause, processing_phase, COUNT(*) AS n
        FROM ticket_insights
        WHERE root_cause = ANY(%s)
        GROUP BY root_cause, processing_phase
        ORDER BY root_cause, n DESC
        """,
        [list(drift_root_causes)],
    )
    if rows:
        print("\nNon-canonical root_cause by phase:")
        for rc, ph, n in rows:
            print(f"  {rc:18s} phase={_as_phase_label(ph):20s} n={n:,}")

    _print_section("6) SERVICE_TYPE + FLAGS (COVERAGE BY PHASE)")
    rows = _fetchall(
        cur,
        """
        SELECT
          processing_phase,
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE clinic_id IS NOT NULL AND clinic_id > 0) AS clinic_id_present,
          COUNT(*) FILTER (WHERE clinic_id IS NULL OR clinic_id = 0) AS clinic_id_missing,
          COUNT(*) FILTER (WHERE service_type IS NULL) AS service_type_null,
          COUNT(*) FILTER (WHERE service_type = 'Bot_Resolvido') AS bot_resolvido,
          COUNT(*) FILTER (WHERE service_type = 'Bot_Escalado') AS bot_escalado,
          COUNT(*) FILTER (WHERE service_type = 'Escalacao_Solicitada') AS escalacao_solicitada,
          COUNT(*) FILTER (WHERE service_type = 'Humano_Direto') AS humano_direto,
          COUNT(*) FILTER (WHERE tags ILIKE '%droz_ativo%') AS droz_ativo_tag,
          COUNT(*) FILTER (WHERE is_proactive IS NULL) AS is_proactive_null,
          COUNT(*) FILTER (WHERE is_proactive IS TRUE) AS is_proactive_true,
          COUNT(*) FILTER (WHERE is_proactive IS FALSE) AS is_proactive_false,
          COUNT(*) FILTER (WHERE has_interaction IS NULL) AS has_interaction_null,
          COUNT(*) FILTER (WHERE has_interaction IS TRUE) AS has_interaction_true,
          COUNT(*) FILTER (WHERE has_interaction IS FALSE) AS has_interaction_false
        FROM ticket_insights
        GROUP BY processing_phase
        ORDER BY total DESC
        """,
    )
    for (
        phase,
        tot,
        cid_present,
        cid_missing,
        st_null,
        bot_r,
        bot_e,
        esc,
        hum,
        droz_ativo_tag,
        pro_null,
        pro_t,
        pro_f,
        hi_null,
        hi_t,
        hi_f,
    ) in rows:
        lbl = _as_phase_label(phase)
        print(
            f"{lbl:25s} total={tot:>9,} | clinic_id present/missing={cid_present:>7,}/{cid_missing:>7,} "
            f"| service_type NULL={st_null:>7,} "
            f"| BR={bot_r:>6,} BE={bot_e:>6,} ES={esc:>6,} HD={hum:>6,} "
            f"| droz_ativo_tag={droz_ativo_tag:>6,} "
            f"| proactive T/F/NULL={pro_t:>6,}/{pro_f:>6,}/{pro_null:>6,} "
            f"| interaction T/F/NULL={hi_t:>6,}/{hi_f:>6,}/{hi_null:>6,}"
        )

    _print_section("6b) QUAL ATENDIMENTO ESTÁ MAIS CORRETO? (CONSISTÊNCIA vs SINAIS DE TAG)")
    # Use a simplified, tag-driven expectation (high-signal) to compare service_type vs atendimento_type.
    # We intentionally avoid regex-on-text here; tags + assignee snapshot are the strongest empirical signals we have.
    row = _fetchone(
        cur,
        """
        WITH processed AS (
          SELECT *
          FROM ticket_insights
          WHERE processing_phase IS NOT NULL
        ),
        expected AS (
          SELECT
            CASE
              WHEN tags ILIKE '%transbordo_botweb%' THEN
                CASE WHEN is_claudinha_assigned IS TRUE THEN 'Bot_Resolvido' ELSE 'Bot_Escalado' END
              WHEN tags ILIKE '%cloudhumans%' THEN
                CASE WHEN is_claudinha_assigned IS TRUE THEN 'Bot_Resolvido' ELSE 'Bot_Escalado' END
              WHEN is_claudinha_assigned IS TRUE THEN 'Bot_Resolvido'
              ELSE NULL
            END AS expected_bot_handling,
            service_type,
            atendimento_type
          FROM processed
        )
        SELECT
          COUNT(*) FILTER (WHERE expected_bot_handling IS NOT NULL) AS n_expected,
          COUNT(*) FILTER (WHERE expected_bot_handling IS NOT NULL AND service_type = expected_bot_handling) AS service_match,
          COUNT(*) FILTER (WHERE expected_bot_handling IS NOT NULL AND atendimento_type = expected_bot_handling) AS atendimento_match,
          COUNT(*) FILTER (WHERE expected_bot_handling IS NOT NULL AND service_type IS NULL) AS service_null,
          COUNT(*) FILTER (WHERE expected_bot_handling IS NOT NULL AND atendimento_type IS NULL) AS atendimento_null
        FROM expected
        """,
    )
    n_exp, svc_match, at_match, svc_null, at_null = row
    _print_kv("Rows with strong bot expectation (tags/assignee)", f"{n_exp:,}")
    _print_kv("service_type matches expectation", f"{svc_match:,} ({svc_match/max(1,n_exp)*100:.1f}%)")
    _print_kv("atendimento_type matches expectation", f"{at_match:,} ({at_match/max(1,n_exp)*100:.1f}%)")
    _print_kv("service_type NULL in expected-set", f"{svc_null:,}")
    _print_kv("atendimento_type NULL in expected-set", f"{at_null:,}")

    print("\nBreakdown for cloudhumans (expected bot flow):")
    rows = _fetchall(
        cur,
        """
        SELECT
          CASE WHEN is_claudinha_assigned IS TRUE THEN 'claud_TRUE' ELSE 'claud_FALSE' END AS claud_snapshot,
          COUNT(*) AS n,
          COUNT(*) FILTER (WHERE service_type = 'Bot_Resolvido') AS svc_br,
          COUNT(*) FILTER (WHERE service_type = 'Bot_Escalado') AS svc_be,
          COUNT(*) FILTER (WHERE service_type = 'Humano_Direto') AS svc_hd,
          COUNT(*) FILTER (WHERE atendimento_type = 'Bot_Resolvido') AS at_br,
          COUNT(*) FILTER (WHERE atendimento_type = 'Bot_Escalado') AS at_be,
          COUNT(*) FILTER (WHERE atendimento_type = 'Humano_Direto') AS at_hd
        FROM ticket_insights
        WHERE processing_phase IS NOT NULL
          AND tags ILIKE '%cloudhumans%'
        GROUP BY 1
        ORDER BY 1
        """,
    )
    for snap, n, svc_br, svc_be, svc_hd, at_br, at_be, at_hd in rows:
        print(
            f"  {snap:10s} n={n:>8,} | service_type BR/BE/HD={svc_br:>6,}/{svc_be:>6,}/{svc_hd:>6,} "
            f"| atendimento_type BR/BE/HD={at_br:>6,}/{at_be:>6,}/{at_hd:>6,}"
        )

    print("\nBreakdown for transbordo_botweb (expected bot flow):")
    rows = _fetchall(
        cur,
        """
        SELECT
          CASE WHEN is_claudinha_assigned IS TRUE THEN 'claud_TRUE' ELSE 'claud_FALSE' END AS claud_snapshot,
          COUNT(*) AS n,
          COUNT(*) FILTER (WHERE service_type = 'Bot_Resolvido') AS svc_br,
          COUNT(*) FILTER (WHERE service_type = 'Bot_Escalado') AS svc_be,
          COUNT(*) FILTER (WHERE service_type = 'Humano_Direto') AS svc_hd,
          COUNT(*) FILTER (WHERE atendimento_type = 'Bot_Resolvido') AS at_br,
          COUNT(*) FILTER (WHERE atendimento_type = 'Bot_Escalado') AS at_be,
          COUNT(*) FILTER (WHERE atendimento_type = 'Humano_Direto') AS at_hd
        FROM ticket_insights
        WHERE processing_phase IS NOT NULL
          AND tags ILIKE '%transbordo_botweb%'
        GROUP BY 1
        ORDER BY 1
        """,
    )
    for snap, n, svc_br, svc_be, svc_hd, at_br, at_be, at_hd in rows:
        print(
            f"  {snap:10s} n={n:>8,} | service_type BR/BE/HD={svc_br:>6,}/{svc_be:>6,}/{svc_hd:>6,} "
            f"| atendimento_type BR/BE/HD={at_br:>6,}/{at_be:>6,}/{at_hd:>6,}"
        )

    _print_section("7) TAG SIGNALS: DROZ vs CLOUDHUMANS vs TRANSBORDO (EMPIRICAL)")
    row = _fetchone(
        cur,
        """
        SELECT
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE tags ILIKE '%cloudhumans%') AS cloudhumans,
          COUNT(*) FILTER (WHERE tags ILIKE '%transbordo_botweb%') AS transbordo_botweb,
          COUNT(*) FILTER (WHERE is_claudinha_assigned IS TRUE) AS claudinha_assigned,
          COUNT(*) FILTER (WHERE tags ILIKE '%droz_switchboard%') AS droz_switchboard,
          COUNT(*) FILTER (WHERE tags ILIKE '%droz_%') AS droz_any,
          COUNT(*) FILTER (WHERE tags ILIKE '%droz_ativo%') AS droz_ativo
        FROM ticket_insights
        """,
    )
    (
        tot,
        cloud,
        transb,
        claud,
        droz_sw,
        droz_any,
        droz_ativo,
    ) = row
    _print_kv("cloudhumans tag", f"{cloud:,} ({cloud/tot*100:.1f}%)")
    _print_kv("transbordo_botweb tag", f"{transb:,} ({transb/tot*100:.1f}%)")
    _print_kv("is_claudinha_assigned", f"{claud:,} ({claud/tot*100:.1f}%)")
    _print_kv("droz_switchboard tag", f"{droz_sw:,} ({droz_sw/tot*100:.1f}%)")
    _print_kv("droz_* any tag", f"{droz_any:,} ({droz_any/tot*100:.1f}%)")
    _print_kv("droz_ativo tag", f"{droz_ativo:,} ({droz_ativo/tot*100:.1f}%)")

    # Overlaps + "snapshot recall" sanity checks
    row = _fetchone(
        cur,
        """
        SELECT
          COUNT(*) FILTER (WHERE tags ILIKE '%cloudhumans%' AND tags ILIKE '%transbordo_botweb%') AS overlap_cloud_transbordo,
          COUNT(*) FILTER (WHERE (is_claudinha_assigned IS TRUE)
                             OR (tags ILIKE '%cloudhumans%')
                             OR (tags ILIKE '%transbordo_botweb%')) AS bot_touched_any,
          COUNT(*) FILTER (WHERE is_claudinha_assigned IS TRUE) AS claudinha_assigned,
          COUNT(*) FILTER (WHERE tags ILIKE '%cloudhumans%' AND is_claudinha_assigned IS TRUE) AS cloudhumans_and_claud_true,
          COUNT(*) FILTER (WHERE tags ILIKE '%cloudhumans%' AND (is_claudinha_assigned IS FALSE OR is_claudinha_assigned IS NULL)) AS cloudhumans_and_claud_false,
          COUNT(*) FILTER (WHERE tags ILIKE '%transbordo_botweb%' AND is_claudinha_assigned IS TRUE) AS transbordo_and_claud_true,
          COUNT(*) FILTER (WHERE tags ILIKE '%transbordo_botweb%' AND (is_claudinha_assigned IS FALSE OR is_claudinha_assigned IS NULL)) AS transbordo_and_claud_false
        FROM ticket_insights
        """,
    )
    (
        overlap_cloud_transbordo,
        bot_touched_any,
        claud_assigned,
        cloud_and_true,
        cloud_and_false,
        transb_and_true,
        transb_and_false,
    ) = row
    _print_kv("cloudhumans ∩ transbordo overlap", f"{overlap_cloud_transbordo:,}")
    _print_kv("bot_touched_any (claud OR cloud OR transb)", f"{bot_touched_any:,} ({bot_touched_any/tot*100:.1f}%)")
    _print_kv("snapshot capture rate (is_claudinha / bot_touched_any)", f"{claud_assigned/max(1, bot_touched_any)*100:.1f}%")
    _print_kv("cloudhumans: claud TRUE", f"{cloud_and_true:,}")
    _print_kv("cloudhumans: claud FALSE/NULL", f"{cloud_and_false:,}")
    _print_kv("transbordo: claud TRUE", f"{transb_and_true:,}")
    _print_kv("transbordo: claud FALSE/NULL", f"{transb_and_false:,}")

    # Time trend for droz_ativo (known drift signal) to validate "dying tag" hypothesis
    _print_section("7b) TAG TREND BY MONTH (droz_ativo / cloudhumans / transbordo)")
    rows = _fetchall(
        cur,
        """
        SELECT
          DATE_TRUNC('month', ticket_created_at) AS month,
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE tags ILIKE '%droz_ativo%') AS droz_ativo,
          COUNT(*) FILTER (WHERE tags ILIKE '%cloudhumans%') AS cloudhumans,
          COUNT(*) FILTER (WHERE tags ILIKE '%transbordo_botweb%') AS transbordo
        FROM ticket_insights
        GROUP BY 1
        ORDER BY 1
        """,
    )
    for month, n, da, ch, tb in rows:
        da_pct = da / max(1, n) * 100
        ch_pct = ch / max(1, n) * 100
        tb_pct = tb / max(1, n) * 100
        print(f"{month:%Y-%m} total={n:>7,} | droz_ativo={da:>7,} ({da_pct:>5.1f}%) | cloudhumans={ch:>7,} ({ch_pct:>5.1f}%) | transbordo={tb:>6,} ({tb_pct:>4.1f}%)")

    _print_section("8) VIEW CHECK: ticket_insights_enriched_v1 (IF EXISTS)")
    view = _fetchone(
        cur,
        "SELECT to_regclass('public.ticket_insights_enriched_v1')",
    )[0]
    if not view:
        print("(view not found)")
    else:
        definition = _fetchone(cur, "SELECT pg_get_viewdef('ticket_insights_enriched_v1'::regclass, true)")[0]
        contains_droz = "droz_" in (definition or "")
        contains_is_bot_flow = "is_bot_flow" in (definition or "")
        _print_kv("View exists", "YES")
        _print_kv("Definition contains 'is_bot_flow'", contains_is_bot_flow)
        _print_kv("Definition contains 'droz_'", contains_droz)
        # Print a short excerpt around 'is_bot_flow' if present
        if contains_is_bot_flow:
            idx = definition.find("is_bot_flow")
            start = max(0, idx - 200)
            end = min(len(definition), idx + 300)
            print("\nExcerpt:")
            print(definition[start:end])

    _print_section("9) APP IMPACT (client-voice): CURRENT COLUMNS vs CANONICAL")
    # The Streamlit app currently treats "new taxonomy" as presence of product_area_l1 and uses:
    #   - product_area_l1 for product
    #   - atendimento_type for atendimento
    # and uses llm_processed_at IS NOT NULL as the "reprocessed" filter.
    # We quantify mismatches vs the empirically-correct columns:
    #   - product_area (v3 L1 used by pipeline)
    #   - service_type (deterministic atendimento classification)

    def _impact_for(where_extra: str, label: str, days: int | None) -> None:
        date_clause = ""
        if days is not None:
            date_clause = f"AND ticket_created_at >= CURRENT_DATE - INTERVAL '{days} days'"

        row = _fetchone(
            cur,
            f"""
            SELECT
              COUNT(*) AS total,
              -- Product distributions (app vs canonical)
              COUNT(*) FILTER (WHERE product_area_l1 = 'BNPL') AS l1_bnpl,
              COUNT(*) FILTER (WHERE product_area_l1 = 'SaaS') AS l1_saas,
              COUNT(*) FILTER (WHERE product_area_l1 = 'Onboarding') AS l1_onboarding,
              COUNT(*) FILTER (WHERE product_area_l1 = 'POS') AS l1_pos,
              COUNT(*) FILTER (WHERE product_area_l1 = 'Indeterminado') AS l1_ind,
              COUNT(*) FILTER (WHERE product_area_l1 IS NULL) AS l1_null,

              COUNT(*) FILTER (WHERE product_area = 'BNPL') AS pa_bnpl,
              COUNT(*) FILTER (WHERE product_area = 'SaaS') AS pa_saas,
              COUNT(*) FILTER (WHERE product_area = 'Onboarding') AS pa_onboarding,
              COUNT(*) FILTER (WHERE product_area = 'POS') AS pa_pos,
              COUNT(*) FILTER (WHERE product_area = 'Indeterminado') AS pa_ind,
              COUNT(*) FILTER (WHERE product_area IS NULL) AS pa_null,

              -- Atendimento distributions (app vs canonical)
              COUNT(*) FILTER (WHERE atendimento_type = 'Bot_Resolvido') AS at_br,
              COUNT(*) FILTER (WHERE atendimento_type = 'Bot_Escalado') AS at_be,
              COUNT(*) FILTER (WHERE atendimento_type = 'Escalacao_Solicitada') AS at_es,
              COUNT(*) FILTER (WHERE atendimento_type = 'Humano_Direto') AS at_hd,
              COUNT(*) FILTER (WHERE atendimento_type IS NULL) AS at_null,

              COUNT(*) FILTER (WHERE service_type = 'Bot_Resolvido') AS svc_br,
              COUNT(*) FILTER (WHERE service_type = 'Bot_Escalado') AS svc_be,
              COUNT(*) FILTER (WHERE service_type = 'Escalacao_Solicitada') AS svc_es,
              COUNT(*) FILTER (WHERE service_type = 'Humano_Direto') AS svc_hd,
              COUNT(*) FILTER (WHERE service_type IS NULL) AS svc_null,

              -- Mismatches (only where both sides are non-NULL)
              COUNT(*) FILTER (WHERE product_area_l1 IS NOT NULL AND product_area IS NOT NULL AND product_area_l1 <> product_area) AS mismatch_product,
              COUNT(*) FILTER (WHERE atendimento_type IS NOT NULL AND service_type IS NOT NULL AND atendimento_type <> service_type) AS mismatch_atendimento
            FROM ticket_insights
            WHERE 1=1
              {where_extra}
              {date_clause}
            """,
        )

        (
            tot,
            l1_bnpl,
            l1_saas,
            l1_onb,
            l1_pos,
            l1_ind,
            l1_null,
            pa_bnpl,
            pa_saas,
            pa_onb,
            pa_pos,
            pa_ind,
            pa_null,
            at_br,
            at_be,
            at_es,
            at_hd,
            at_null,
            svc_br,
            svc_be,
            svc_es,
            svc_hd,
            svc_null,
            mm_prod,
            mm_at,
        ) = row

        days_label = "ALL" if days is None else f"{days}d"
        print(f"\n[{label}] window={days_label} total={tot:,}")
        if tot == 0:
            return

        def pct(n: int) -> str:
            return f"{(n / tot * 100):.1f}%"

        print("  Product (app=product_area_l1)  BNPL/SaaS/Onboarding/POS/Ind/NULL:",
              f"{l1_bnpl:,} ({pct(l1_bnpl)}), {l1_saas:,} ({pct(l1_saas)}), {l1_onb:,} ({pct(l1_onb)}), {l1_pos:,} ({pct(l1_pos)}), {l1_ind:,} ({pct(l1_ind)}), {l1_null:,} ({pct(l1_null)})")
        print("  Product (canon=product_area)   BNPL/SaaS/Onboarding/POS/Ind/NULL:",
              f"{pa_bnpl:,} ({pct(pa_bnpl)}), {pa_saas:,} ({pct(pa_saas)}), {pa_onb:,} ({pct(pa_onb)}), {pa_pos:,} ({pct(pa_pos)}), {pa_ind:,} ({pct(pa_ind)}), {pa_null:,} ({pct(pa_null)})")

        bot_app = at_br + at_be
        bot_canon = svc_br + svc_be
        print("  Atendimento (app=atendimento_type)  BR/BE/ES/HD/NULL:",
              f"{at_br:,} ({pct(at_br)}), {at_be:,} ({pct(at_be)}), {at_es:,} ({pct(at_es)}), {at_hd:,} ({pct(at_hd)}), {at_null:,} ({pct(at_null)})")
        print("  Atendimento (canon=service_type)    BR/BE/ES/HD/NULL:",
              f"{svc_br:,} ({pct(svc_br)}), {svc_be:,} ({pct(svc_be)}), {svc_es:,} ({pct(svc_es)}), {svc_hd:,} ({pct(svc_hd)}), {svc_null:,} ({pct(svc_null)})")
        print(f"  Bot_touched rate app vs canon: {bot_app:,} ({pct(bot_app)}) vs {bot_canon:,} ({pct(bot_canon)})")

        # Mismatch rates
        print(f"  Mismatches (non-NULL): product={mm_prod:,} ({(mm_prod/tot*100):.1f}% of rows), atendimento={mm_at:,} ({(mm_at/tot*100):.1f}% of rows)")

    # Two relevant universes:
    #  - app_rp: what the app calls "reprocessed" today
    #  - strict_processed: what we consider fully processed v3.x (has processing_phase)
    where_app_rp = "AND llm_processed_at IS NOT NULL"
    where_strict = "AND processing_phase IS NOT NULL"

    for universe_label, where_clause in [
        ("app_rp (llm_processed_at IS NOT NULL)", where_app_rp),
        ("strict_processed (processing_phase IS NOT NULL)", where_strict),
    ]:
        _impact_for(where_clause, universe_label, days=30)
        _impact_for(where_clause, universe_label, days=90)
        _impact_for(where_clause, universe_label, days=None)

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

