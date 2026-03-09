"""
PHASE 3.2: Full Taxonomy Reprocessing Pipeline

Applies the complete 3-axis taxonomy to tickets:
1. NATUREZA (root_cause) - Tier 1 deterministic (n2_* tags) + LLM extraction (19 values v3.2)
2. PRODUTO (product_area) - Deterministic rules (5 L1 + L2 subcategories)
3. ATENDIMENTO (service_type) - Deterministic rules (4 values)

Plus complementary LLM variables:
- sentiment (1-5)
- key_themes (max 3)
- conversation_summary (max 200 chars)
- customer_effort_score (1-7)
- frustration_detected (boolean)
- churn_risk_flag (LOW/MEDIUM/HIGH)
- llm_confidence (0.0-1.0)

Plus derived metadata flags (v3.1):
- is_proactive (curated template whitelist, ~30%)
- has_interaction (NOT sem_interacao, ~87%)

Usage:
    python reprocess_tickets_full_taxonomy.py --limit 100 --dry-run
    python reprocess_tickets_full_taxonomy.py --batch-size 50

Updated: 2026-02-13 (Phase 3.2 - Natureza v3.2 + n2_* Tier 1 + metadata flags)
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import psycopg2
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.prompt_compiler import PromptCompiler, apply_tier1_natureza, derive_metadata_flags
from scripts.routing_logic import TicketRouter, ClinicContext, TicketContext

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# PRODUTO CLASSIFICATION (Deterministic)
# ============================================================================

PRODUTO_TAG_RULES = {
    'BNPL': {
        'tags': ['cob_', 'grupo_cobranca', 'bnpl_', 'endosso', 'template_contrato_',
                 'venda', 'venda_si_'],  # venda_* = BNPL sales support (NOT SaaS sales)
        'themes': ['cobranca', 'renegociacao', 'parcela', 'boleto', 'contrato', 
                   'financiamento', 'bnpl', 'proposta', 'assinatura_digital'],
    },
    'SaaS': {
        'tags': ['saas', 'bug_', 'login', 'loss', 'nao_assinante', 'cancelamento'],
        'themes': ['agenda', 'orcamento', 'paciente', 'transacao', 'configuracao', 'relatorio', 'assinatura'],
        'exclusion': ['saas__maquininha'],
    },
    'Onboarding': {
        'tags': ['onboarding', 'credenciamento'],  # venda_* REMOVED (moved to BNPL)
        'themes': ['credenciamento', 'onboarding', 'ativacao'],  # documento REMOVED (too generic)
    },
    'POS': {
        'tags': ['saas__maquininha', 'maquininha', 'capininha'],
        'themes': ['maquininha', 'entrega', 'capininha'],
    },
}

PRODUTO_L2_RULES = {
    'BNPL': {
        'Cobranca': ['cob_', 'renegociacao', 'boleto', 'faixa_', 'codigo_cobranca', 'cobranca'],
        'Servicing': ['bnpl_servicing', 'contrato', 'parcela', 'link_pagamento', 'servicing'],
        'Originacao': ['simulacao', 'aprovacao', 'crivo', 'analise_credito', 'financiamento', 'credito'],
        'Contratacao': ['venda_si_', 'venda', 'contratacao', 'proposta', 'assinatura_digital', 'assinatura_contrato'],
    },
    'SaaS': {
        'Clinico': ['agenda', 'paciente', 'procedimento', 'orcamento', 'contato_paciente'],
        'Conta': ['assinatura', 'plano', 'billing', 'login', 'acesso', 'assinatura_contrato', 'renovacao_plano'],
        'Lifecycle': ['migracao', 'cancelamento', 'renovacao', 'inadimplencia', 'cancelamento_saas', 'migracao_dados'],
    },
    'Onboarding': {
        'Credenciamento': ['credenciamento', 'credenciar', 'documentacao'],  # venda_si_ REMOVED (moved to BNPL)
        'Ativacao': ['onboarding', 'ativacao', 'primeiro_acesso', 'configuracao_inicial'],
    },
    'POS': {
        'Entrega': ['entrega', 'rastreio', 'envio', 'correios'],
        'Operacao': ['maquininha', 'capininha', 'transacao', 'taxa'],
        'Configuracao': ['configuracao', 'setup', 'instalacao', 'ativacao'],
    },
}

# REMOVED (2026-02-13): root_cause should NOT determine Produto
# Produto is ALWAYS deterministic (tags/themes only)
# If tags/themes insufficient → "Indeterminado" (acceptable!)
#
# OLD CIRCULAR DEPENDENCIES (removed):
# ROOT_CAUSE_PRODUCT_MAP = {...}  # LLM (root_cause) → Produto (fallback)
# ROOT_CAUSE_L2_FALLBACK = {...}  # LLM (root_cause) → L2 (fallback)
#
# NEW APPROACH:
# - Produto classification: tags/themes scoring ONLY
# - No fallback to root_cause
# - Post-hoc validation: flag semantic conflicts for investigation
# - Target: < 12% Indeterminado via tag enrichment (not via root_cause crutch)

# Fine-grained L2 inference from key_themes when standard patterns fail.
# ONLY includes unambiguous mappings within the L1 context.
# Ambiguous themes (pos_venda, credenciamento_bnpl, boleto) are left as L2=NULL
# because they may belong to a different L1 (e.g., Onboarding).
THEME_L2_INFERENCE = {
    'BNPL': {
        'Cobranca': ['inadimplencia_paciente', 'endosso_ligacao'],
    },
    'SaaS': {
        'Conta': ['debito_nao_autorizado', 'estorno', 'debito_automatico'],
    },
}

# Post-hoc validation: expected product for specific root_causes (v3.2)
# Used ONLY for conflict detection (not classification)
# Values can be str (single product) or list (multiple valid products)
# Updated 2026-02-13: Contratacao split + venda_* → BNPL
EXPECTED_PRODUCT_FOR_ROOT_CAUSE = {
    # BNPL funnel (5 stages with Contratacao split)
    'Simulacao_Credito': 'BNPL',
    'Contratacao_Acompanhamento': 'BNPL',   # NEW: venda_si_suporte, venda_apenas_acompanhamento
    'Contratacao_Suporte_Paciente': 'BNPL', # NEW: venda_si_telefone, venda_si_docs, venda_si_assinatura
    'Endosso_Repasse': 'BNPL',
    'Cobranca_Ativa': 'BNPL',
    # Dual-affinity (validated via Golden Set N=1000)
    'Credenciamento': ['BNPL', 'POS'],      # 43% BNPL, 33% POS (NOT Onboarding)
    # SaaS subscription
    'Subscription_Pagamento': 'SaaS',
    'Subscription_Cancelamento': 'SaaS',
    'Migracao': 'SaaS',
    'Acesso': 'SaaS',
    # Cross-cutting: these are NOT validated (expected in multiple products)
    # 'Process_Generico', 'Financial_Inquiry', 'Forma_Pagamento',
    # 'Negativacao', 'Operational_Question', 'Technical_Issue',
    # 'Carne_Capim', 'Alteracao_Cadastral', 'Unclear'
    # Legacy (Golden Set):
    # 'Contratacao': ['Onboarding', 'BNPL']  # REMOVED in v3.2, split into 2 new Naturezas
}

# ============================================================================
# NATUREZA → L1 OVERRIDE (2026-02-14)
# Corrects semantic conflicts where tag-based L1 disagrees with Natureza.
# Applied AFTER tag-based classification. Only for single-product naturezas.
# Evidence: 928 conflicts (0.78%) in audit of 118K tickets.
# Example: SaaS × Cobranca_Ativa (162 tickets) — tags say SaaS, natureza is BNPL-only.
# ============================================================================
NATUREZA_FORCES_L1 = {
    # BNPL-exclusive naturezas (by definition)
    'Simulacao_Credito': 'BNPL',
    'Contratacao_Acompanhamento': 'BNPL',
    'Contratacao_Suporte_Paciente': 'BNPL',
    'Endosso_Repasse': 'BNPL',
    'Cobranca_Ativa': 'BNPL',
    # SaaS-exclusive naturezas (by definition)
    'Subscription_Pagamento': 'SaaS',
    'Subscription_Cancelamento': 'SaaS',
    'Migracao': 'SaaS',
    # NOT included (cross-cutting or dual-affinity):
    # Credenciamento (BNPL+POS), Acesso (mostly SaaS but not exclusive),
    # Operational_Question, Technical_Issue, Forma_Pagamento,
    # Alteracao_Cadastral, Carne_Capim, Process_Generico, Financial_Inquiry,
    # Negativacao, Unclear
}

# ============================================================================
# ROOT_CAUSE → L2 FALLBACK (2026-02-14)
# Used when tag/theme-based L2 returns None, to fill gaps.
# NOT circular: L1 is determined by tags, root_cause determines Natureza (LLM).
# Here we only use root_cause as a FALLBACK hint for L2 subcategory.
# Evidence: 19.4% L2=NULL, mostly from new naturezas without L2 rules.
# ============================================================================
ROOT_CAUSE_L2_FALLBACK = {
    'BNPL': {
        'Cobranca_Ativa': 'Cobranca',
        'Endosso_Repasse': 'Servicing',
        'Contratacao_Acompanhamento': 'Contratacao',
        'Contratacao_Suporte_Paciente': 'Contratacao',
        'Simulacao_Credito': 'Originacao',
        'Credenciamento': 'Originacao',
        'Alteracao_Cadastral': 'Servicing',
        'Operational_Question': 'Servicing',
    },
    'SaaS': {
        'Subscription_Pagamento': 'Conta',
        'Subscription_Cancelamento': 'Lifecycle',
        'Migracao': 'Lifecycle',
        'Acesso': 'Conta',
        'Alteracao_Cadastral': 'Conta',
        'Carne_Capim': 'Conta',
        'Forma_Pagamento': 'Conta',
        'Operational_Question': 'Clinico',
    },
    'POS': {
        'Credenciamento': 'Operacao',
        'Alteracao_Cadastral': 'Operacao',
        'Forma_Pagamento': 'Operacao',
        'Operational_Question': 'Operacao',
    },
    'Onboarding': {
        'Credenciamento': 'Credenciamento',
    },
}


def classify_produto(tags: list, key_themes: list, root_cause: str, conversation: str = "") -> Tuple[str, Optional[str]]:
    """Classify ticket into Produto (L1) and optionally L2.
    
    Strategy (v3.0 - 2026-02-14):
    1. Tag/theme pattern matching (score-based) → L1 + L2 via patterns
    2. If nothing matches → ('Indeterminado', None)
    3. POST-HOC: Natureza override (NATUREZA_FORCES_L1) corrects L1 conflicts
    4. L2 fallback (ROOT_CAUSE_L2_FALLBACK) fills gaps when tag-based L2 is None
    
    NOTE: root_cause is NOT used for L1 classification (tags/themes only).
    The override in step 3 only applies for single-product naturezas where
    the tag-based L1 is provably wrong (e.g., SaaS × Cobranca_Ativa).
    """
    tags_lower = [t.lower() for t in (tags or [])]
    themes_lower = [t.lower() for t in (key_themes or [])]
    
    # Priority 1: POS (explicit tag match)
    for pattern in PRODUTO_TAG_RULES['POS']['tags']:
        if any(pattern in t for t in tags_lower) or any(pattern in t for t in themes_lower):
            l2 = _get_l2_subcategory('POS', tags_lower, themes_lower, root_cause)
            return _apply_natureza_override('POS', l2, root_cause, tags_lower, themes_lower)
    
    if conversation and 'capininha' in conversation.lower():
        l2 = _get_l2_subcategory('POS', tags_lower, themes_lower, root_cause)
        return _apply_natureza_override('POS', l2 or 'Operacao', root_cause, tags_lower, themes_lower)
    
    # Score-based classification
    scores = {'BNPL': 0, 'Onboarding': 0, 'SaaS': 0}
    
    for product, rules in [('BNPL', PRODUTO_TAG_RULES['BNPL']), 
                           ('Onboarding', PRODUTO_TAG_RULES['Onboarding']),
                           ('SaaS', PRODUTO_TAG_RULES['SaaS'])]:
        is_maquininha = any('maquininha' in t for t in tags_lower)
        if product == 'SaaS' and is_maquininha:
            continue
            
        for pattern in rules['tags']:
            if any(pattern in t for t in tags_lower):
                scores[product] += 2
        for theme in rules['themes']:
            if theme in themes_lower:
                scores[product] += 1
    
    max_score = max(scores.values())
    if max_score >= 2:
        winner = max(scores, key=scores.get)
        l2 = _get_l2_subcategory(winner, tags_lower, themes_lower, root_cause)
        return _apply_natureza_override(winner, l2, root_cause, tags_lower, themes_lower)
    
    # No match → Indeterminado (but still apply override if natureza forces L1)
    if root_cause in NATUREZA_FORCES_L1:
        forced_l1 = NATUREZA_FORCES_L1[root_cause]
        l2 = _get_l2_subcategory(forced_l1, tags_lower, themes_lower, root_cause)
        return (forced_l1, l2)
    
    return ('Indeterminado', None)


def _apply_natureza_override(product_l1: str, product_l2: Optional[str], 
                              root_cause: str, tags: list, themes: list) -> Tuple[str, Optional[str]]:
    """Apply NATUREZA_FORCES_L1 override if L1 conflicts with single-product Natureza.
    
    Only overrides when:
    1. Natureza is in NATUREZA_FORCES_L1 (single-product)
    2. Current L1 disagrees with forced L1
    3. Current L1 is NOT 'Indeterminado' (handled separately in classify_produto)
    """
    if root_cause in NATUREZA_FORCES_L1:
        forced_l1 = NATUREZA_FORCES_L1[root_cause]
        if product_l1 != forced_l1:
            # L1 override — recalculate L2 for the new product
            new_l2 = _get_l2_subcategory(forced_l1, tags, themes, root_cause)
            return (forced_l1, new_l2)
    return (product_l1, product_l2)


def validate_semantic_consistency(product_l1: str, root_cause: str) -> Tuple[bool, Optional[str]]:
    """Post-hoc validation: check if product and root_cause are semantically consistent.
    
    Returns:
        (is_consistent, warning_message)
    
    Note: This is for DETECTION only, not classification.
    Conflicts should be logged/investigated but NOT auto-corrected.
    Supports both single-product and multi-product (list) expected values.
    """
    if root_cause not in EXPECTED_PRODUCT_FOR_ROOT_CAUSE:
        return (True, None)  # Cross-cutting root_cause (expected diversity)
    
    expected = EXPECTED_PRODUCT_FOR_ROOT_CAUSE[root_cause]
    
    # Support both single string and list of valid products
    if isinstance(expected, list):
        valid = product_l1 in expected or product_l1 == 'Indeterminado'
        expected_str = '/'.join(expected)
    else:
        valid = product_l1 == expected or product_l1 == 'Indeterminado'
        expected_str = expected
    
    if valid:
        return (True, None)
    
    warning = (f"Semantic conflict: root_cause={root_cause} (expects {expected_str}) "
               f"but product={product_l1}. Investigate: tags wrong? LLM error? Leak?")
    return (False, warning)


def _get_l2_subcategory(product: str, tags: list, themes: list, root_cause: str = None) -> Optional[str]:
    """Get L2 subcategory for a product via pattern matching + root_cause fallback.
    
    Priority:
    1. Standard patterns (PRODUTO_L2_RULES) - broad tag/theme matching
    2. Fine-grained inference (THEME_L2_INFERENCE) - specific theme signals
    3. Root-cause fallback (ROOT_CAUSE_L2_FALLBACK) - when tags/themes insufficient
    """
    if product not in PRODUTO_L2_RULES:
        # Even without tag rules, try root_cause fallback
        if root_cause and product in ROOT_CAUSE_L2_FALLBACK:
            return ROOT_CAUSE_L2_FALLBACK[product].get(root_cause)
        return None
    
    # Priority 1: Standard patterns
    for l2_name, patterns in PRODUTO_L2_RULES[product].items():
        for pattern in patterns:
            if any(pattern in t for t in tags) or any(pattern in t for t in themes):
                return l2_name
    
    # Priority 2: Fine-grained theme inference
    if product in THEME_L2_INFERENCE:
        for l2_name, theme_signals in THEME_L2_INFERENCE[product].items():
            for signal in theme_signals:
                if signal in themes:
                    return l2_name
    
    # Priority 3: Root-cause fallback (fills gaps for new naturezas)
    if root_cause and product in ROOT_CAUSE_L2_FALLBACK:
        return ROOT_CAUSE_L2_FALLBACK[product].get(root_cause)
    
    return None


# ============================================================================
# ATENDIMENTO CLASSIFICATION (Deterministic)
# ============================================================================

ESCALATION_PATTERNS_HIGH = [
    r'vou te transferir para (um|uma|o|a) (atendente|especialista|analista)',
    r'não consigo (ajudar|resolver|te atender) com (isso|esse caso)',
    r'vou encaminhar (para|pro) time de (suporte|atendimento)',
    r'transferindo para atendente',
    r'encaminhando para especialista',
]

ESCALATION_PATTERNS_MEDIUM = [
    r'(transferir|encaminhar|direcionar).*(atendente|especialista|humano)',
    r'(não posso|não consigo).*(ajudar|resolver)',
    r'um momento.*(atendente|especialista)',
]

CLIENT_REQUESTED_HUMAN = [
    r'quero falar com (atendente|humano|pessoa)',
    r'preciso de (humano|atendente|pessoa)',
    r'não quero (bot|robô|ia)',
    r'falar com (alguém|uma pessoa)',
    r'atendente humano',
]

# Bot self-identification signatures (HIGH confidence only).
# Bare 'claudia' excluded: matches human agents named Claudia.
# The bot presents as "ClaudIA" but in lowercase matching 'claudia' is too broad.
# Use specific phrases where bot self-identifies.
BOT_SELF_ID = [
    'sou a claudia',           # "Oi! Sou a Claudia, a assistente virtual"
    'sou a claudinha',
    'sou a assistente virtual',
    'sou uma assistente virtual',
    'sou a ia da capim',
    'sou a inteligência artificial',
]


def classify_atendimento(tags: list, conversation: str, is_claudinha_assigned: bool = False, via_channel: str = None) -> str:
    """Classify ticket into Atendimento type.

    Three evidence layers for bot involvement (discovered 2026-02-13):
      - is_claudinha_assigned: bot is CURRENT assignee (snapshot, not history)
      - 'cloudhumans' tag: ticket went through CloudHumans/WhatsApp bot (31.8% of all tickets)
      - 'transbordo_botweb' tag: ticket escalated from native messaging bot (2.1%, since Dec 2025)

    Key insight: is_claudinha_assigned is a snapshot. When bot escalates,
    assignee changes to human → 68% of cloudhumans tickets have claudinha=FALSE.
    The 'cloudhumans' tag captures the "dark matter" of bot involvement.

    Pipeline:
      1. Determine bot_involved via tags (cloudhumans, transbordo) + assignee + text
      2. transbordo_botweb → Bot_Escalado (formal escalation tag, native messaging)
      3. cloudhumans + claudinha=FALSE → Bot_Escalado (bot touched via WhatsApp, human took over)
      4. Text: escalation patterns → Bot_Escalado
      5. Text: client asks for human → Escalacao_Solicitada
      6. bot_involved + no escalation signals → Bot_Resolvido
      7. DEFAULT → Humano_Direto (no evidence of bot involvement)

    Key principle: conv_len is NOT used as bot_involved proxy.
    """
    import re

    tags_lower = [t.lower() for t in (tags or [])]
    conv_lower = (conversation or '').lower()

    # === Step 1: Determine bot involvement (evidence-based, 3 layers) ===
    has_cloudhumans_tag = 'cloudhumans' in tags_lower
    has_transbordo_tag = 'transbordo_botweb' in tags_lower

    bot_involved = (
        is_claudinha_assigned or          # Layer 1: assignee snapshot
        has_cloudhumans_tag or            # Layer 2: CloudHumans/WhatsApp platform (31.8%)
        has_transbordo_tag or             # Layer 3: native messaging escalation (2.1%)
        any(sig in conv_lower for sig in BOT_SELF_ID)  # Layer 4: text self-ID (backup)
    )

    # === Step 2: transbordo_botweb = formal escalation from native messaging bot ===
    if has_transbordo_tag:
        if is_claudinha_assigned:
            # Bot still assigned despite transbordo tag → resolved in N1
            return 'Bot_Resolvido'
        return 'Bot_Escalado'

    # === Step 3: cloudhumans + claudinha=FALSE = bot touched via WhatsApp, human took over ===
    if has_cloudhumans_tag and not is_claudinha_assigned:
        # Bot interacted via WhatsApp but human assumed the ticket.
        # Check for explicit client escalation request first.
        for pattern in CLIENT_REQUESTED_HUMAN:
            if re.search(pattern, conv_lower):
                return 'Escalacao_Solicitada'
        # Otherwise this is a bot-to-human handoff.
        return 'Bot_Escalado'

    # === Step 4: Text-based escalation (bot or system announces transfer) ===
    has_bot_escalation = False
    for pattern in ESCALATION_PATTERNS_HIGH:
        if re.search(pattern, conv_lower):
            has_bot_escalation = True
            break

    if not has_bot_escalation:
        for pattern in ESCALATION_PATTERNS_MEDIUM:
            if re.search(pattern, conv_lower):
                has_bot_escalation = True
                break

    if has_bot_escalation:
        return 'Bot_Escalado'

    # === Step 5: Client requested human (no bot tag but text signal) ===
    for pattern in CLIENT_REQUESTED_HUMAN:
        if re.search(pattern, conv_lower):
            return 'Escalacao_Solicitada'

    # === Step 6: Bot touched but no escalation → resolved by bot ===
    if bot_involved:
        return 'Bot_Resolvido'

    # === Step 7: Default → human handled (no evidence of bot) ===
    return 'Humano_Direto'


# ============================================================================
# LLM PROCESSING
# ============================================================================

TIER_MODELS = {
    'T1': {'model': 'claude-opus-4-6', 'input_cost': 5.0, 'output_cost': 25.0},               # Opus 4.6 for very relevant
    'T2': {'model': 'claude-sonnet-4-5', 'input_cost': 3.0, 'output_cost': 15.0},             # Sonnet 4.5 for standard
    'T3': {'model': 'claude-haiku-4-5', 'input_cost': 1.0, 'output_cost': 5.0},               # Haiku 4.5 for trivial
}


def call_llm(prompt_system: str, prompt_user: str, model: str, dry_run: bool = False) -> Dict[str, Any]:
    """Call Claude API and parse JSON response."""
    if dry_run:
        return {
            'root_cause': 'indeterminado',
            'sentiment': 3,
            'key_themes': ['test'],
            'conversation_summary': '[DRY RUN]',
            'customer_effort_score': 3,
            'frustration_detected': False,
            'churn_risk_flag': 'LOW',
            'llm_confidence': 0.5,
        }
    
    import anthropic
    client = anthropic.Anthropic()
    
    response = client.messages.create(
        model=model,
        max_tokens=500,
        messages=[
            {"role": "user", "content": prompt_user}
        ],
        system=prompt_system,
    )
    
    # Parse JSON from response
    text = response.content[0].text
    
    # Extract JSON from response
    import re
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        result = json.loads(json_match.group())
        result['_input_tokens'] = response.usage.input_tokens
        result['_output_tokens'] = response.usage.output_tokens
        return result
    
    raise ValueError(f"Could not parse JSON from response: {text[:200]}")


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def get_postgres_connection():
    """Get PostgreSQL connection."""
    connect_args = {
        'host': os.getenv('VOX_POPULAR_HOST'),
        'dbname': os.getenv('VOX_POPULAR_DB'),
        'user': os.getenv('VOX_POPULAR_USER'),
        'password': os.getenv('VOX_POPULAR_PASSWORD'),
    }
    port = os.getenv('VOX_POPULAR_PORT')
    if port:
        connect_args['port'] = port
    return psycopg2.connect(**connect_args)


def fetch_tickets_to_process(conn, limit: int = None, offset: int = 0, prioritize_clinic_ids: bool = True, created_after: str = None, unprocessed_only: bool = False) -> list:
    """Fetch tickets that need reprocessing.
    
    Args:
        prioritize_clinic_ids: If True, prioritize tickets with valid clinic_id for better routing
        created_after: Filter tickets created after this date (YYYY-MM-DD)
        unprocessed_only: If True, only fetch tickets where processing_phase IS NULL
    """
    cursor = conn.cursor()
    
    # Build WHERE conditions
    where_conditions = [
        "full_conversation IS NOT NULL",
        "LENGTH(full_conversation) > 100"
    ]
    
    if prioritize_clinic_ids:
        where_conditions.extend([
            "clinic_id IS NOT NULL",
            "clinic_id > 0"
        ])
    
    if created_after:
        where_conditions.append(f"ticket_created_at >= '{created_after}'")
    
    if unprocessed_only:
        where_conditions.append("processing_phase IS NULL")
    
    where_clause = " AND ".join(where_conditions)
    
    query = f'''
        SELECT 
            zendesk_ticket_id,
            clinic_id,
            tags,
            full_conversation,
            is_claudinha_assigned,
            via_channel,
            subject,
            status,
            ticket_created_at
        FROM ticket_insights
        WHERE {where_clause}
        ORDER BY ticket_created_at DESC
    '''
    
    if limit:
        query += f' LIMIT {limit}'
    if offset:
        query += f' OFFSET {offset}'
    
    cursor.execute(query)
    
    columns = ['zendesk_ticket_id', 'clinic_id', 'tags', 'full_conversation', 
               'is_claudinha_assigned', 'via_channel', 'subject', 'status', 'ticket_created_at']
    
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def save_processed_ticket(conn, ticket_id: int, result: Dict[str, Any]):
    """Save processed ticket back to PostgreSQL (full 3-axis taxonomy).
    
    Uses savepoint per ticket to avoid cascading transaction failures.
    """
    cursor = conn.cursor()
    
    # key_themes is stored as ARRAY in PostgreSQL - pass list directly
    key_themes = result.get('key_themes')
    if isinstance(key_themes, str):
        key_themes = [k.strip() for k in key_themes.split(',')]
    
    try:
        cursor.execute("SAVEPOINT save_ticket")
        cursor.execute('''
            UPDATE ticket_insights
            SET 
                root_cause = %s,
                sentiment = %s,
                key_themes = %s,
                conversation_summary = %s,
                customer_effort_score = %s,
                frustration_detected = %s,
                churn_risk_flag = %s,
                llm_confidence = %s,
                product_area = %s,
                product_area_l2 = %s,
                service_type = %s,
                is_proactive = %s,
                has_interaction = %s,
                processing_phase = %s,
                llm_model = %s,
                llm_processed_at = %s
            WHERE zendesk_ticket_id = %s
        ''', (
            result.get('root_cause'),
            result.get('sentiment'),
            key_themes,
            result.get('conversation_summary'),
            result.get('customer_effort_score'),
            result.get('frustration_detected'),
            result.get('churn_risk_flag'),
            result.get('llm_confidence'),
            result.get('product_area_l1'),
            result.get('product_area_l2'),
            result.get('service_type'),
            result.get('is_proactive'),
            result.get('has_interaction'),
            result.get('_processing_phase'),
            result.get('_model'),
            datetime.now(),
            ticket_id
        ))
        cursor.execute("RELEASE SAVEPOINT save_ticket")
        conn.commit()
        return True
    except Exception as e:
        cursor.execute("ROLLBACK TO SAVEPOINT save_ticket")
        conn.commit()
        logger.error(f"Failed to save ticket {ticket_id}: {e}")
        return False


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def process_ticket(ticket: dict, compiler: PromptCompiler, router: TicketRouter, 
                   clinic_context: dict, processing_phase: str = 'phase_3.1_full',
                   dry_run: bool = False) -> Dict[str, Any]:
    """
    Process a single ticket through the full taxonomy pipeline.
    
    Args:
        processing_phase: Identifier for audit trail (e.g., 'phase_3.1_golden')
    
    Returns dict with all 3 axes + complementary variables.
    """
    ticket_id = ticket['zendesk_ticket_id']
    clinic_id = ticket.get('clinic_id')
    tags = ticket.get('tags', '')
    conversation = ticket.get('full_conversation', '')
    
    # Parse tags
    if isinstance(tags, str):
        tags_list = [t.strip() for t in tags.split(',') if t.strip()]
    else:
        tags_list = tags or []
    
    # 1. DETERMINE TIER (routing)
    # Create default clinic context if not available
    clinic_ctx = clinic_context.get(clinic_id) if clinic_id else None
    if clinic_ctx is None:
        clinic_ctx = ClinicContext(
            clinic_id=clinic_id or 0,
            has_bnpl_contract=False,
            has_capim_pos=False,
            current_subscription_status='unknown',
        )
    
    ticket_ctx = TicketContext(
        zendesk_ticket_id=ticket_id,
        tags=tags_list,
        escalation_level='N1',
        assignee_group='',
        conversation_turns=conversation.count('\n') // 2 + 1,
        total_tokens=len(conversation.split()),
        priority=ticket.get('status', 'normal'),
        subject=ticket.get('subject', ''),
        product_mentions=[]
    )
    
    tier = router.route(clinic_ctx, ticket_ctx)
    model_config = TIER_MODELS[tier]
    
    # 2. TIER 1 DETERMINISTIC NATUREZA (n2_* tags, decision 19.27)
    tier1_result = apply_tier1_natureza(tags_list)
    tier1_override = tier1_result.get('tier1_override', False) if tier1_result else False
    
    # 3. DERIVE METADATA FLAGS (decisions 19.28, 19.29)
    metadata_flags = derive_metadata_flags(tags_list)
    
    # 4. COMPILE PROMPT (Tier 1 hint is injected into metadata layer)
    ticket_data = {
        'zendesk_ticket_id': ticket_id,
        'clinic_id': clinic_id,
        'tags': tags,
        'subject': ticket.get('subject', ''),
        'conversation': conversation,
    }
    
    system_prompt, user_prompt = compiler.compile(ticket_data)
    
    # 5. CALL LLM (NATUREZA extraction — all 7 variables)
    llm_result = call_llm(
        system_prompt,
        user_prompt,
        model_config['model'],
        dry_run=dry_run
    )
    
    # 5b. RESOLVE NATUREZA: Tier 1 override vs LLM
    if tier1_override:
        # High-confidence deterministic match → override LLM root_cause
        root_cause = tier1_result['root_cause']
        llm_confidence = max(tier1_result['confidence'], llm_result.get('llm_confidence', 0))
        logger.debug(f"[Ticket {ticket_id}] Tier 1 override: {root_cause} "
                     f"(tag: {tier1_result['matched_tag']}, conf: {tier1_result['confidence']:.0%})")
    else:
        root_cause = llm_result.get('root_cause', 'Unclear')
        llm_confidence = llm_result.get('llm_confidence', 0.5)
    
    # 6. CLASSIFY PRODUTO (deterministic)
    key_themes = llm_result.get('key_themes', [])
    product_l1, product_l2 = classify_produto(tags_list, key_themes, root_cause, conversation)
    
    # 6b. POST-HOC VALIDATION (detect conflicts, don't auto-fix)
    is_consistent, conflict_warning = validate_semantic_consistency(product_l1, root_cause)
    if not is_consistent and not dry_run:
        logger.warning(f"[Ticket {ticket_id}] {conflict_warning}")
    
    # 7. CLASSIFY ATENDIMENTO (deterministic)
    service_type = classify_atendimento(
        tags=tags_list,
        conversation=conversation,
        is_claudinha_assigned=ticket.get('is_claudinha_assigned', False),
        via_channel=ticket.get('via_channel')
    )
    
    # 8. COMBINE ALL RESULTS
    result = {
        # NATUREZA (Tier 1 override or LLM)
        'root_cause': root_cause,
        'sentiment': llm_result.get('sentiment'),
        'key_themes': llm_result.get('key_themes'),
        'conversation_summary': llm_result.get('conversation_summary'),
        'customer_effort_score': llm_result.get('customer_effort_score'),
        'frustration_detected': llm_result.get('frustration_detected'),
        'churn_risk_flag': llm_result.get('churn_risk_flag'),
        'llm_confidence': llm_confidence,
        
        # PRODUTO (Deterministic)
        'product_area_l1': product_l1,
        'product_area_l2': product_l2,
        
        # ATENDIMENTO (Deterministic)
        'service_type': service_type,
        
        # DERIVED METADATA (v3.1)
        'is_proactive': metadata_flags['is_proactive'],
        'has_interaction': metadata_flags['has_interaction'],
        
        # Pipeline metadata
        '_tier': tier,
        '_model': model_config['model'],
        '_tier1_override': tier1_override,
        '_tier1_tag': tier1_result.get('matched_tag') if tier1_result else None,
        '_proactive_type': metadata_flags.get('proactive_type'),
        '_processing_phase': processing_phase,
        '_input_tokens': llm_result.get('_input_tokens', 0),
        '_output_tokens': llm_result.get('_output_tokens', 0),
        'zendesk_ticket_id': ticket_id,
        'clinic_id': clinic_id,
    }
    
    return result


def main():
    parser = argparse.ArgumentParser(description='Reprocess tickets with full 3-axis taxonomy')
    parser.add_argument('--limit', type=int, help='Limit number of tickets to process')
    parser.add_argument('--offset', type=int, default=0, help='Offset for pagination')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for processing')
    parser.add_argument('--dry-run', action='store_true', help='Dry run without LLM calls')
    parser.add_argument('--output', type=str, help='Output JSONL file path')
    parser.add_argument('--save-to-db', action='store_true', help='Save results to PostgreSQL')
    parser.add_argument('--phase', type=str, default='phase_3.1_full', 
                        choices=['phase_3.1_golden', 'phase_3.1_subset', 'phase_3.1_full'],
                        help='Reprocessing phase identifier (for audit trail)')
    args = parser.parse_args()
    
    logger.info("="*80)
    logger.info("PHASE 3: FULL TAXONOMY REPROCESSING")
    logger.info("="*80)
    logger.info(f"  Processing Phase: {args.phase}")
    logger.info(f"  Dry run: {args.dry_run}")
    logger.info(f"  Limit: {args.limit or 'ALL'}")
    logger.info(f"  Save to DB: {args.save_to_db}")
    
    # Initialize components
    compiler = PromptCompiler()
    router = TicketRouter()
    
    # Connect to PostgreSQL
    conn = get_postgres_connection()
    
    # Fetch tickets
    logger.info(f"Fetching tickets from PostgreSQL...")
    tickets = fetch_tickets_to_process(conn, limit=args.limit, offset=args.offset)
    logger.info(f"[OK] Fetched {len(tickets)} tickets")
    
    # Fetch clinic context from Snowflake for routing
    clinic_context = {}
    try:
        from src.utils.snowflake_connection import run_query
        
        # Get unique clinic_ids from tickets
        clinic_ids = list(set(t.get('clinic_id') for t in tickets if t.get('clinic_id') and t.get('clinic_id') > 0))
        
        if clinic_ids:
            ids_str = ','.join(str(c) for c in clinic_ids)
            logger.info(f"Fetching {len(clinic_ids)} clinic profiles from Snowflake...")
            
            df = run_query(f'''
                SELECT CLINIC_ID, IS_SUBSCRIBER, WAS_SUBSCRIBER, HAS_SIGNED_CONTRACT, HAS_CAPIM_POS
                FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.CLINIC_MOST_RELEVANT_INFO
                WHERE CLINIC_ID IN ({ids_str})
            ''')
            
            if df is not None:
                for _, row in df.iterrows():
                    cid = int(row['CLINIC_ID'])
                    clinic_context[cid] = ClinicContext(
                        clinic_id=cid,
                        has_bnpl_contract=bool(row['HAS_SIGNED_CONTRACT']),
                        has_capim_pos=bool(row['HAS_CAPIM_POS']),
                        current_subscription_status='ativo' if row['IS_SUBSCRIBER'] else ('cancelado' if row['WAS_SUBSCRIBER'] else 'nunca_assinou'),
                    )
                logger.info(f"[OK] Loaded {len(clinic_context)} clinic profiles for routing")
    except Exception as e:
        logger.warning(f"Could not load clinic profiles: {e}")
    
    # Process tickets
    results = []
    stats = {
        'produto': {},
        'atendimento': {},
        'natureza': {},
        'tiers': {'T1': 0, 'T2': 0, 'T3': 0},
        'tokens': {'input': 0, 'output': 0},
        'saved': 0,
        'save_errors': 0,
        'tier1_overrides': 0,
        'proactive': 0,
        'no_interaction': 0,
    }
    
    logger.info(f"\nProcessing {len(tickets)} tickets...")
    
    for i, ticket in enumerate(tickets):
        try:
            result = process_ticket(ticket, compiler, router, clinic_context, 
                                   processing_phase=args.phase, dry_run=args.dry_run)
            results.append(result)
            
            # Update stats
            stats['produto'][result['product_area_l1']] = stats['produto'].get(result['product_area_l1'], 0) + 1
            stats['atendimento'][result['service_type']] = stats['atendimento'].get(result['service_type'], 0) + 1
            stats['natureza'][result['root_cause']] = stats['natureza'].get(result['root_cause'], 0) + 1
            stats['tiers'][result['_tier']] += 1
            stats['tokens']['input'] += result.get('_input_tokens', 0)
            stats['tokens']['output'] += result.get('_output_tokens', 0)
            if result.get('_tier1_override'):
                stats['tier1_overrides'] += 1
            if result.get('is_proactive'):
                stats['proactive'] += 1
            if not result.get('has_interaction'):
                stats['no_interaction'] += 1
            
            # Save to DB if requested
            if args.save_to_db and not args.dry_run:
                saved = save_processed_ticket(conn, ticket['zendesk_ticket_id'], result)
                if saved:
                    stats['saved'] += 1
                else:
                    stats['save_errors'] += 1
            
            # Progress
            if (i + 1) % 50 == 0:
                logger.info(f"  Processed {i+1}/{len(tickets)} tickets...")
                
        except Exception as e:
            logger.error(f"Error processing ticket {ticket['zendesk_ticket_id']}: {e}")
            continue
    
    # Save to file
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(__file__).parent.parent / 'data' / 'reprocessed' / f'reprocessed_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jsonl'
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False, default=str) + '\n')
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("PROCESSING COMPLETE")
    logger.info("="*80)
    
    logger.info("\n[PRODUTO DISTRIBUTION]")
    for product, count in sorted(stats['produto'].items(), key=lambda x: -x[1]):
        pct = 100 * count / len(results)
        logger.info(f"  {product:15s} {count:5d} ({pct:5.1f}%)")
    
    logger.info("\n[ATENDIMENTO DISTRIBUTION]")
    for service, count in sorted(stats['atendimento'].items(), key=lambda x: -x[1]):
        pct = 100 * count / len(results)
        logger.info(f"  {service:22s} {count:5d} ({pct:5.1f}%)")
    
    logger.info("\n[NATUREZA TOP 10]")
    for nature, count in sorted(stats['natureza'].items(), key=lambda x: -x[1])[:10]:
        pct = 100 * count / len(results)
        logger.info(f"  {nature:22s} {count:5d} ({pct:5.1f}%)")
    
    logger.info("\n[TIER DISTRIBUTION]")
    for tier, count in sorted(stats['tiers'].items()):
        pct = 100 * count / len(results) if results else 0
        logger.info(f"  {tier}: {count} ({pct:.1f}%)")
    
    logger.info(f"\n[TIER 1 NATUREZA OVERRIDES]")
    t1_pct = 100 * stats['tier1_overrides'] / len(results) if results else 0
    logger.info(f"  Overrides: {stats['tier1_overrides']} ({t1_pct:.1f}%)")
    
    logger.info(f"\n[METADATA FLAGS]")
    pro_pct = 100 * stats['proactive'] / len(results) if results else 0
    noint_pct = 100 * stats['no_interaction'] / len(results) if results else 0
    logger.info(f"  is_proactive=TRUE: {stats['proactive']} ({pro_pct:.1f}%)")
    logger.info(f"  has_interaction=FALSE: {stats['no_interaction']} ({noint_pct:.1f}%)")
    
    logger.info(f"\n[TOKENS]")
    logger.info(f"  Input: {stats['tokens']['input']:,}")
    logger.info(f"  Output: {stats['tokens']['output']:,}")
    
    if args.save_to_db:
        logger.info(f"\n[DATABASE]")
        logger.info(f"  Saved to PostgreSQL: {stats['saved']}")
        logger.info(f"  Save errors: {stats['save_errors']}")
    
    logger.info(f"\n[OUTPUT]")
    logger.info(f"  File: {output_path}")
    logger.info(f"  Records: {len(results)}")
    
    conn.close()


if __name__ == '__main__':
    main()
