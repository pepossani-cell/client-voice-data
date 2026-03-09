"""
Prompt Compiler - 5-Layer Context-Aware Prompt Architecture (Phase 3.2)
======================================================================
Decisions: 20.5g, 20.7a, 19.22-19.29 (DECISIONS_IN_PROGRESS.md)

Layers:
  L1: Task definition + output schema (7 LLM variables, JSON mode)
  L2: Taxonomy context (19 root_cause v3.2, 45 key_themes, 3-axis model)
  L3: Disambiguation rules (key_themes aliases, contextual resolution)
  L4: Clinic profile (Snowflake: BNPL/POS/subscription status)
  L5: Conversation (subject + full conversation, max 1000 tokens)

Phase 3.2 Changes (Decisions 19.22-19.29):
  - root_cause: 15 -> 19 valores v3.2 (Natureza redesign + split de Contratacao)
  - Tier 1 deterministic pre-triage: 17+ n2_* tags → skip LLM for root_cause
  - is_proactive: derived flag (curated template whitelist, ~30%)
  - has_interaction: derived flag (NOT sem_interacao, ~87%)
  - saas_login reclassified HIGH → MEDIUM (trust 53.3%)
  - droz_ativo discarded as signal (dying: 30%→3%)
  - 7 LLM variables: root_cause, sentiment, key_themes, conversation_summary,
    customer_effort_score, frustration_detected, churn_risk_flag, llm_confidence
  - Canonical key_themes vocabulary: 45 terms (CANONICAL_VOCAB_FINAL.yaml)

Usage:
    from prompt_compiler import PromptCompiler

    compiler = PromptCompiler()
    compiler.load_clinic_profiles()  # pre-load from Snowflake

    system_prompt, user_prompt = compiler.compile(ticket)
    # Or with Tier 1 pre-triage:
    tier1_result = compiler.apply_tier1_natureza(ticket)
    if tier1_result:
        # Skip LLM root_cause, use deterministic value
        ...

Updated: 2026-02-13 (Phase 3.2 - Natureza v3.2 + n2_* Tier 1 + metadata flags)
"""

import os
import sys
import yaml
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Snowflake connection (local project utils)
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Load canonical vocabularies
_DATA_DIR = Path(__file__).parent.parent / 'data' / 'key_themes_investigation'
_CANONICAL_VOCAB_PATH = _DATA_DIR / 'CANONICAL_VOCAB_FINAL.yaml'
_OUTPUT_SCHEMA_PATH = _DATA_DIR / 'OUTPUT_SCHEMA_FINAL.yaml'

def _load_canonical_vocab():
    """Load canonical key_themes vocabulary"""
    if not _CANONICAL_VOCAB_PATH.exists():
        print(f"[WARN] Canonical vocab not found: {_CANONICAL_VOCAB_PATH}")
        return []
    with open(_CANONICAL_VOCAB_PATH, 'r', encoding='utf-8') as f:
        vocab_data = yaml.safe_load(f)
    return vocab_data.get('canonical_terms', [])

def _load_output_schema():
    """Load output schema specification"""
    if not _OUTPUT_SCHEMA_PATH.exists():
        print(f"[WARN] Output schema not found: {_OUTPUT_SCHEMA_PATH}")
        return {}
    with open(_OUTPUT_SCHEMA_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

_CANONICAL_KEY_THEMES = _load_canonical_vocab()
_OUTPUT_SCHEMA = _load_output_schema()


# =============================================================================
# L1: Task Definition + Output Schema (Phase 3)
# =============================================================================

_SYSTEM_PROMPT_PHASE3 = """Você é um especialista em análise de tickets de suporte no domínio de clínicas odontológicas brasileiras.

Seu objetivo: extrair insights estruturados de tickets Zendesk para análise de churn, qualidade de atendimento e saúde operacional.

DOMÍNIO CAPIM (contexto):
- **Produtos**: BNPL (financiamento odontológico), SaaS (sistema de gestão clínica), POS (maquininha Capininha)
- **Personas**: B2B (clínicas odontológicas), B2C (pacientes)
- **Taxonomia**: Produto × Natureza × Atendimento (3 eixos ortogonais)

TAREFA: Extrair 7 variáveis estruturadas (JSON) para cada ticket.

OUTPUT SCHEMA (JSON):
{
  "root_cause": "<enum: 19 valores canônicos v3.2, ver abaixo>",
  "sentiment": <int: 1-5, experiência do cliente>,
  "key_themes": ["<termo1>", "<termo2>", "<termo3>"],
  "conversation_summary": "<string: max 200 chars, síntese objetiva>",
  "customer_effort_score": <int: 1-7, esforço para resolver>,
  "frustration_detected": <boolean: sinais explícitos de frustração>,
  "churn_risk_flag": "<enum: LOW/MEDIUM/HIGH>",
  "llm_confidence": <float: 0.0-1.0, sua autoavaliação de confiança>
}

INSTRUÇÕES DETALHADAS:

1. **root_cause** (19 valores canônicos v3.2):

   FUNIL BNPL (5 etapas do ciclo de crédito):
   - Simulacao_Credito: C1 — recusa de crédito, aprovação, consulta de score, elegibilidade
   - Contratacao_Acompanhamento: C2 follow-up — clínica acompanhando venda, suporte genérico ao paciente
   - Contratacao_Suporte_Paciente: C2 fricção — dificuldades em telefone, docs, assinatura digital, SMS
   - Endosso_Repasse: C2→C2S — confirmação, ligação banco, liberação endosso, repasse $$ para clínica
   - Cobranca_Ativa: Post-C2S — boleto, parcelas, inadimplência, renegociação (paciente devedor)

   PROCESSOS OPERACIONAIS (3 valores):
   - Credenciamento: onboarding/ativação de clínica (BNPL ou POS)
   - Migracao: migração de sistema/dados (SaaS lifecycle)
   - Process_Generico: outros processos operacionais (treinamento, configuração)

   ASSINATURA SAAS (2 valores):
   - Subscription_Pagamento: inadimplência/bloqueio da assinatura SaaS
   - Subscription_Cancelamento: pedido de cancelamento SaaS (churn)

   FINANCEIRO / TRANSACIONAL (3 valores):
   - Financial_Inquiry: consultas informativas de PACIENTES sobre contratos ativos ("quantas parcelas?", "quando vence?") — sentiment geralmente neutro/positivo
   - Forma_Pagamento: consultas transacionais ("como pago?", "qual o boleto?", "link de pagamento")
   - Negativacao: negativação, protesto, Serasa — caso extremo, baixo volume

   SUPORTE / TÉCNICO (3 valores):
   - Operational_Question: dúvidas de uso, "como faço X?", treinamento
   - Technical_Issue: bugs, falhas técnicas, instabilidade do sistema
   - Acesso: login, senha, bloqueio, permissão

   CROSS-CUTTING (3 valores):
   - Carne_Capim: saque, recebimento, transação Carnê Capim (funcionalidade SaaS)
   - Alteracao_Cadastral: dados bancários, telefone, CNPJ, email (todos os produtos)
   - Unclear: não foi possível determinar com confiança (confidence < 0.75)

   IMPORTANTE: Se uma tag de pré-triagem já forneceu o root_cause (ver METADADOS), use-o.
   Se root_cause já foi determinado por regra determinística, foque nos outros 6 campos.

2. **sentiment** (1-5):
   - 1 = Muito negativo (raiva, ameaça churn)
   - 2 = Negativo (insatisfação, frustração)
   - 3 = Neutro (transacional, sem emoção)
   - 4 = Positivo (satisfação, agradecimento)
   - 5 = Muito positivo (elogio, entusiasmo)

3. **key_themes** (máx 3 termos, VOCABULÁRIO CANÔNICO obrigatório):
   - Use APENAS os 45 termos canônicos (ver seção abaixo)
   - Multi-word themes: SEMPRE usar underscores (ex: "codigo_cobranca", "link_pagamento")
   - Priorize themes que distinguem este ticket de outros
   - Evite themes genéricos ("problema", "duvida")

4. **conversation_summary** (max 200 chars):
   - Síntese objetiva do problema/request
   - Foco em RESULTADO, não processo
   - Ex: "Paciente quer renegociar parcela BNPL atrasada. Agente ofereceu desconto 10%."

5. **customer_effort_score** (1-7):
   - 1 = Resolvido em 1 interação, sem fricção
   - 4 = Múltiplas interações, esforço moderado
   - 7 = Extremo esforço, múltiplos canais, escalação N2+

6. **frustration_detected** (true/false):
   - true: Sinais EXPLÍCITOS (capslock, "absurdo", "ridículo", "cancelar", ameaça jurídica)
   - false: Ausência de sinais ou frustração implícita

7. **churn_risk_flag** (LOW/MEDIUM/HIGH):
   - HIGH: Ameaça explícita de cancelamento, múltiplas reclamações, N2+
   - MEDIUM: Insatisfação moderada, problemas recorrentes, sentiment ≤2
   - LOW: Ticket transacional ou positivo, sem sinais de risco

8. **llm_confidence** (0.0-1.0):
   - Sua autoavaliação de confiança na classificação
   - 0.9-1.0: Alta (contexto claro, decisão trivial)
   - 0.6-0.8: Média (ambiguidade resolvível com regras)
   - 0.0-0.5: Baixa (contexto insuficiente, múltiplas interpretações)
   - Se ticket sem conversa real (has_interaction=FALSE): reduza confiança em 0.2

RETORNE APENAS O JSON VÁLIDO, SEM EXPLICAÇÕES ADICIONAIS.
"""

# =============================================================================
# L2: Taxonomy Context (Canonical Vocabularies)
# =============================================================================

def _build_canonical_vocab_section() -> str:
    """Build L2: canonical key_themes vocabulary section"""
    if not _CANONICAL_KEY_THEMES:
        return "(Vocabulário canônico não carregado)"
    
    vocab_str = ", ".join(_CANONICAL_KEY_THEMES[:20])  # First 20 for brevity
    remaining = len(_CANONICAL_KEY_THEMES) - 20
    if remaining > 0:
        vocab_str += f", ... (+{remaining} termos)"
    
    return f"""
VOCABULÁRIO CANÔNICO (key_themes) — 45 termos obrigatórios:
{', '.join(_CANONICAL_KEY_THEMES)}

REGRAS:
- Multi-word themes: SEMPRE underscores (ex: "codigo_cobranca", "link_pagamento", "nota_fiscal")
- Lowercase obrigatório
- Máximo 3 themes por ticket
- Priorize themes que aparecem EXPLICITAMENTE na conversa
"""

# =============================================================================
# L3: Disambiguation Rules (injected into system prompt)
# =============================================================================
# Based on empirical investigation (20.5f + 20.7a)

_DISAMBIGUATION_BNPL_ACTIVE = """
REGRAS DE DESAMBIGUAÇÃO (esta clínica TEM BNPL ativo):
- "boleto" / "parcela" / "PIX": Interpretar como Cobranca_Ativa (financiamento BNPL Post-C2S), não SaaS
- "pagamento": Priorizar Cobranca_Ativa (parcela BNPL). Se contexto é orçamento/plano de tratamento -> Contratacao_Acompanhamento ou Contratacao_Suporte_Paciente. Se mensalidade SaaS -> Subscription_Pagamento
- "assinatura": Se CONTRATO de financiamento (selfie, documentos) -> Contratacao_Acompanhamento (follow-up genérico) ou Contratacao_Suporte_Paciente (fricção docs/telefone). Se PLANO mensal SaaS -> Subscription_Pagamento ou Subscription_Cancelamento
- "cancelamento": Se cancelar FINANCIAMENTO -> Cobranca_Ativa. Se cancelar PLANO SaaS -> Subscription_Cancelamento
- "endosso" / "repasse" / "liberação": Endosso_Repasse (C2→C2S)
- "score" / "recusa" / "aprovação" / "simulação": Simulacao_Credito (C1)
- "agenda": Se no contexto de cobrança (vencimento) -> Cobranca_Ativa. Se funcionalidade do sistema -> Operational_Question
- "maquininha" / "capininha" / "POS": Sempre Operational_Question ou Technical_Issue (domínio POS)
- "carnê" / "saque" / "recebimento carnê": Carne_Capim
- "dados bancários" / "CNPJ" / "telefone": Alteracao_Cadastral
"""

_DISAMBIGUATION_NO_BNPL = """
REGRAS DE DESAMBIGUAÇÃO (esta clínica NÃO tem BNPL):
- "boleto" / "pagamento": Interpretar como Subscription_Pagamento (assinatura SaaS) ou Forma_Pagamento (consulta transacional)
- "assinatura": Quase certamente Subscription_Pagamento ou Subscription_Cancelamento (plano SaaS). Muito improvável ser BNPL
- "cancelamento": Priorizar Subscription_Cancelamento (cancelamento do plano SaaS)
- "agenda" / "paciente" / "procedimento": Operational_Question (funcionalidade do sistema)
- "maquininha" / "capininha" / "POS": Operational_Question ou Technical_Issue
- "credito" / "simulacao" / "financiamento": Se a clínica não tem BNPL, pode ser CONSULTA sobre como aderir -> Credenciamento
- "carnê" / "saque": Carne_Capim
- "dados bancários" / "CNPJ": Alteracao_Cadastral
- "login" / "senha" / "bloqueio": Acesso
"""

_DISAMBIGUATION_UNKNOWN_CLINIC = """
REGRAS DE DESAMBIGUAÇÃO (clínica não identificada):
- "boleto": Se tags contém cob_* ou grupo_cobranca -> Cobranca_Ativa. Se tags contém saas_* ou n2_saas -> Subscription_Pagamento. Sem pista -> usar contexto da conversa
- "pagamento": Analisar contexto: parcela/dívida -> Cobranca_Ativa. Orçamento/checkout -> Forma_Pagamento. Mensalidade -> Subscription_Pagamento
- "assinatura": Se tags venda_* (BNPL) -> Contratacao_Acompanhamento ou Contratacao_Suporte_Paciente (dependendo se é follow-up ou fricção). Se tags SaaS -> Subscription_Pagamento/Subscription_Cancelamento
- "cancelamento": Verificar tags: loss/cxloss -> Subscription_Cancelamento. cob_*/grupo_cobranca -> Cobranca_Ativa
- "endosso" / "repasse": Endosso_Repasse (BNPL C2→C2S)
- "score" / "recusa" / "crédito": Simulacao_Credito (BNPL C1)
- "agenda": Verificar se contexto é funcionalidade (SaaS -> Operational_Question) ou data de cobrança (BNPL -> Cobranca_Ativa)
- "login" / "senha": Acesso
- "carnê" / "saque": Carne_Capim
- "dados bancários" / "CNPJ" / "telefone": Alteracao_Cadastral
"""


# =============================================================================
# Tier 1 Deterministic Natureza Pre-Triage (Decision 19.27)
# =============================================================================
# High-confidence tag → root_cause mappings. When these fire, the LLM
# should NOT override root_cause (but still extracts the other 6 variables).
# Based on audit: N=78K, 6 months, 7/7 months stable, <0.1% contradictions.

TIER1_NATUREZA_RULES = {
    # ── FUNIL BNPL ──────────────────────────────────────────────
    'Cobranca_Ativa': {
        'tags': ['grupo_cobranca', 'agente_cobranca', 'bnpl_boleto', 'bnpl_cobranca',
                 'falar_com_atendente_cobranca',
                 'n2_bnpl_boleto', 'n2_bnpl_cobranca', 'n2_cob_renegociacao'],
        'tag_prefixes': ['cob_'],
        'confidence': 0.90,
    },
    'Contratacao_Acompanhamento': {
        'tags': ['venda_si_suporte', 'venda_apenas_acompanhamento', 'venda_sem_suporte',
                 'n2_venda_si_suporte', 'n2_venda_apenas_acompanhamento', 'n2_venda_sem_suporte'],
        'confidence': 0.85,
    },
    'Contratacao_Suporte_Paciente': {
        'tags': ['venda_si_telefone', 'venda_si_docs', 'venda_si_assinatura', 'venda_si_sms',
                 'n2_venda_si_telefone', 'n2_venda_si_docs', 'n2_venda_si_assinatura'],
        'confidence': 0.85,
    },
    'Endosso_Repasse': {
        'tags': ['n2_endosso', 'n1_endosso', 'n2_bnpl_endosso', 'bnpl_endosso'],
        'confidence': 0.85,
    },
    'Simulacao_Credito': {
        'tags': ['bnpl_creditoquestionando_recusa'],
        'confidence': 0.75,
    },
    # ── PROCESSOS ───────────────────────────────────────────────
    'Credenciamento': {
        'tags': ['credenciamento', 'bnpl_duvidas_em_credenciamento',
                 'n2_bnpl_duvidas_em_credenciamento',
                 'bnpl__documentos_para_credenciamento'],
        'confidence': 0.85,
    },
    'Migracao': {
        'tags': ['migracao', 'saas_migracao_base', 'n2_saas_migracao_base'],
        'confidence': 0.85,
    },
    # ── ASSINATURA SAAS ────────────────────────────────────────
    'Subscription_Pagamento': {
        'tags': ['n2_saas_pagamento', 'saas_pagamento'],
        'confidence': 0.85,
    },
    'Subscription_Cancelamento': {
        'tags': ['loss', 'saas_churn', 'n2_saas_churn', 'n2_cancelamento'],
        'confidence': 0.80,
    },
    # ── SUPORTE / TÉCNICO ──────────────────────────────────────
    'Technical_Issue': {
        'tags': ['bug_saas', 'n2_bug_agenda', 'n2_bug_pacientes',
                 'venda_dificuldade_na_assinatura', 'n2_venda_dificuldade_na_assinatura'],
        'tag_prefixes': ['bug_'],
        'confidence': 0.81,
    },
    'Acesso': {
        'tags': ['saas_login', 'n2_saas_login'],
        'confidence': 0.53,  # MEDIUM — 47% are technical_issue/info_request
        # NOTE: This low confidence means LLM Tier 2 should still refine.
        # We set a higher threshold (0.70) for actually overriding LLM.
    },
    'Operational_Question': {
        'tags': ['saas_treinamento', 'n2_saas_treinamento',
                 'n2_bnpl_duvidas_e_suporte', 'bnpl_duvidas_e_suporte',
                 'n2_saas_suporte'],
        'confidence': 0.75,
    },
    # ── FINANCEIRO / TRANSACIONAL ──────────────────────────────
    'Carne_Capim': {
        'tags': ['saas_financeiro_carne', 'n2_saas_financeiro_carne'],
        'confidence': 0.85,
    },
    'Alteracao_Cadastral': {
        'tags': ['saas_alteracao_dados', 'n2_saas_alteracao_dados'],
        'confidence': 0.85,
    },
    'Forma_Pagamento': {
        'tags': ['saas_financeiro_menoscarne', 'n2_saas_financeiro_menoscarne'],
        'confidence': 0.75,
    },
    # ── FINANCEIRO / COBRANCA ──────────────────────────────────
    'Negativacao': {
        'tags': ['template_negativacao', 'template_negativacao_v2', 'template_negativacao_concluida',
                 'n2_negativacao'],
        'tag_prefixes': ['template_negativacao'],
        'confidence': 0.90,
    },
}

# Minimum confidence to actually override LLM root_cause
TIER1_OVERRIDE_THRESHOLD = 0.70


def apply_tier1_natureza(tags: list) -> dict:
    """Apply Tier 1 deterministic pre-triage for Natureza (root_cause).
    
    Args:
        tags: List of Zendesk tags (lowercase)
    
    Returns:
        dict with keys:
            - root_cause: str or None (None = no Tier 1 match, use LLM)
            - confidence: float
            - matched_tag: str (the tag that fired)
            - tier1_override: bool (True if confidence >= TIER1_OVERRIDE_THRESHOLD)
        Returns empty dict if no match.
    """
    tags_lower = [t.lower().strip() for t in (tags or [])]
    
    for natureza, rule in TIER1_NATUREZA_RULES.items():
        # Check exact tag matches
        for tag_pattern in rule.get('tags', []):
            if tag_pattern in tags_lower:
                conf = rule['confidence']
                return {
                    'root_cause': natureza,
                    'confidence': conf,
                    'matched_tag': tag_pattern,
                    'tier1_override': conf >= TIER1_OVERRIDE_THRESHOLD,
                }
        
        # Check prefix matches (e.g., 'cob_' matches 'cob_renegociacao_facil')
        for prefix in rule.get('tag_prefixes', []):
            for tag in tags_lower:
                if tag.startswith(prefix):
                    conf = rule['confidence']
                    return {
                        'root_cause': natureza,
                        'confidence': conf,
                        'matched_tag': tag,
                        'tier1_override': conf >= TIER1_OVERRIDE_THRESHOLD,
                    }
    
    return {}


# =============================================================================
# Derived Metadata Flags (Decisions 19.28, 19.29)
# =============================================================================

# Curated whitelist of outbound/system templates (audit: 78K tickets, 6 months)
_PROACTIVE_TEMPLATES_OUTBOUND = [
    'template_contrato_validado',
    'template_promessa_lembrete_botao',
    'template_documents_approved_v4',
    'template_contrato_assinado_v1',
    'template_cxprimeiramensagem',
    'template_promessa_quebrada_v4',
    'template_promessa_quebrada_v2',           # versioned predecessor (135 vol)
    'template_negativacao_concluida',
    'template_campanha_desconto',
    'template_campanha_desconto_padrao',       # variant (54 vol)
    'template_contract_canceled_v3',
    'template_treinamento_maquininha_v1',
    'template_lembrete_promessa_no_dia',
    'template_cxloss',
    'template_documents_rejected_v4',
    'template_aniversariantes_do_mes',
    # ── Campanhas outbound (audit 2026-02-13) ──
    'template_campanha_entrada_reduzida_pix',  # 140 vol — campanha entrada reduzida
    'template_campanha_entrada_reduzida_v2',   #  20 vol — campanha v2
    'template_quitacao_colchao',               # 109 vol — quitação/acordo
    'template_aditamento',                     #  18 vol — aditamento contrato
    'template_patient_downpayment_renegotiation',  # 30 vol — renegociação paciente
    'template_patient_invoices_renegotiation',     # 16 vol — parcelas paciente
    'template_restituicao_ir',                     #  6 vol — restituição IR
]

_PROACTIVE_TEMPLATES_OUTBOUND_PREFIXES = [
    'template_regularize_hoje',  # broadened: catches _ofertas_ and base (204+5460 vol)
]

_PROACTIVE_TEMPLATES_SYSTEM = [
    'template_negativacao',
    'template_negativacao_rigoroso',
    'template_negativacao_v2',             # versioned successor (272 vol)
    'template_pague_seu_boleto',
    'template_atraso_curto',
    'template_atraso_curto_v1',            # versioned successor (282 vol)
    'template_lembrete_vencimento',
    'template_lembrete_vencimento_v3',     # versioned successor (306 vol)
    'template_lembrete_vencimento_v4',     # versioned successor (53 vol)
    'template_assinatura_pendente',
    'template_cob_assinatura_pendente',
    # ── DDA automático (naming: template_N_dda, not template_dda_N) ──
    'template_8_dda',                      #  76 vol — DDA 8 dias
    'template_15_dda',                     # 110 vol — DDA 15 dias
    'template_22_dda',                     #  73 vol — DDA 22 dias
]

_PROACTIVE_TEMPLATES_SYSTEM_PREFIXES = [
    'template_cob_',
    'template_dda_',  # template_dda_* patterns (kept for future templates)
]

# NOTE (2026-02-13 audit): Explicitly EXCLUDED — response/receptivo templates:
# - template_cxsolicitandocontato     (66% receptivo, 3679→313 vol recente)
# - template_saas_inadimplentes_v1    (96% receptivo, 916→32 vol recente)
# - template_saas_inadimplentes_fup_v1(90% receptivo)
# - template_boasvindas_cx*           (77-94% receptivo)
# - template_maquininha_em_transito*  (100% receptivo)
# - template_cx_onboarding_*          (71-79% receptivo)


def derive_metadata_flags(tags: list) -> dict:
    """Derive is_proactive and has_interaction from tags.
    
    Args:
        tags: List of Zendesk tags
    
    Returns:
        dict with:
            - is_proactive: bool
            - proactive_type: 'outbound_human' | 'system_automated' | None
            - has_interaction: bool
            - matched_template: str or None
    """
    tags_lower = [t.lower().strip() for t in (tags or [])]
    
    # --- is_proactive ---
    is_proactive = False
    proactive_type = None
    matched_template = None
    
    for tag in tags_lower:
        # Outbound human templates (exact match)
        if tag in _PROACTIVE_TEMPLATES_OUTBOUND:
            is_proactive = True
            proactive_type = 'outbound_human'
            matched_template = tag
            break
        
        # Outbound human templates (prefix match)
        for prefix in _PROACTIVE_TEMPLATES_OUTBOUND_PREFIXES:
            if tag.startswith(prefix):
                is_proactive = True
                proactive_type = 'outbound_human'
                matched_template = tag
                break
        if is_proactive:
            break
        
        # System automated templates (exact match)
        if tag in _PROACTIVE_TEMPLATES_SYSTEM:
            is_proactive = True
            proactive_type = 'system_automated'
            matched_template = tag
            break
        
        # System automated templates (prefix match)
        for prefix in _PROACTIVE_TEMPLATES_SYSTEM_PREFIXES:
            if tag.startswith(prefix):
                is_proactive = True
                proactive_type = 'system_automated'
                matched_template = tag
                break
        if is_proactive:
            break
    
    # --- has_interaction ---
    has_interaction = 'sem_interacao' not in tags_lower
    
    return {
        'is_proactive': is_proactive,
        'proactive_type': proactive_type,
        'has_interaction': has_interaction,
        'matched_template': matched_template,
    }


# =============================================================================
# Clinic Profile Loader
# =============================================================================

class ClinicProfileLoader:
    """Pre-loads clinic profiles from Snowflake for L2 injection."""

    def __init__(self):
        self.profiles = {}  # clinic_id -> profile dict
        self._loaded = False

    def load(self):
        """Load all clinic profiles from CLINIC_FEATURES_SNAPSHOT_V1."""
        try:
            from src.utils.snowflake_connection import run_query
        except ImportError:
            print("[WARN] Snowflake connection not available, L2 disabled")
            self._loaded = True
            return

        print("[Compiler] Loading clinic profiles from Snowflake...")
        # Use CLINIC_MOST_RELEVANT_INFO directly (CLINIC_DIM_V1 was fixed 2026-02-13 but MRI is sufficient for prompts)
        query = """
        SELECT
            CLINIC_ID as clinic_id,
            CLINIC_NAME as clinic_name,
            BUSINESS_SEGMENTATION as clinic_business_segmentation,
            IS_SUBSCRIBER as clinic_is_subscriber,
            WAS_SUBSCRIBER as clinic_was_subscriber,
            CASE 
                WHEN IS_SUBSCRIBER THEN 'active'
                WHEN WAS_SUBSCRIBER THEN 'churned'
                ELSE 'never'
            END as clinic_saas_bucket,
            IS_BNPL_ELIGIBLE as clinic_is_bnpl_eligible,
            HAS_SIGNED_CONTRACT as clinic_has_signed_contract,
            CLINIC_UF as clinic_uf,
            CLINIC_CITY as clinic_city,
            INTEREST_CATEGORY as clinic_interest_category,
            CLINIC_CREDIT_SCORE as clinic_credit_score,
            COALESCE(HAS_CAPIM_POS, FALSE) as clinic_has_capim_pos
        FROM CAPIM_DATA_DEV.POSSANI_SANDBOX.CLINIC_MOST_RELEVANT_INFO
        WHERE CLINIC_ID IS NOT NULL
        """
        try:
            df = run_query(query)
            if df is not None and len(df) > 0:
                # Normalize column names (Snowflake returns UPPERCASE)
                df.columns = [c.lower() for c in df.columns]
                for _, row in df.iterrows():
                    cid = int(row['clinic_id'])
                    self.profiles[cid] = {
                        'clinic_id': cid,
                        'name': row.get('clinic_name', ''),
                        'segment': row.get('clinic_business_segmentation', 'unknown'),
                        'is_subscriber': bool(row.get('clinic_is_subscriber', False)),
                        'saas_bucket': row.get('clinic_saas_bucket', 'unknown'),
                        'is_bnpl_eligible': bool(row.get('clinic_is_bnpl_eligible', False)),
                        'has_bnpl_contract': bool(row.get('clinic_has_signed_contract', False)),
                        'has_pos': bool(row.get('clinic_has_capim_pos', False)),
                        'uf': row.get('clinic_uf', ''),
                        'city': row.get('clinic_city', ''),
                        'interest_category': row.get('clinic_interest_category', ''),
                        'credit_score': row.get('clinic_credit_score'),
                    }
                print(f"[Compiler] Loaded {len(self.profiles)} clinic profiles")
            else:
                print("[WARN] No clinic profiles returned from Snowflake")
        except Exception as e:
            print(f"[WARN] Failed to load clinic profiles: {e}")

        self._loaded = True

    def get(self, clinic_id):
        """Get profile for a clinic_id. Returns None if not found."""
        if not self._loaded:
            self.load()
        if clinic_id is None:
            return None
        try:
            return self.profiles.get(int(clinic_id))
        except (ValueError, TypeError):
            return None


# =============================================================================
# Prompt Compiler
# =============================================================================

class PromptCompiler:
    """Compiles context-aware prompts using 5-layer architecture."""

    def __init__(self):
        self.clinic_loader = ClinicProfileLoader()

    def load_clinic_profiles(self):
        """Pre-load clinic profiles from Snowflake (call once before processing)."""
        self.clinic_loader.load()

    # --- L1: Task Definition (Phase 3 unified prompt) ---

    def _get_base_prompt(self) -> str:
        """Get base system prompt (Phase 3: unified for all product areas)"""
        return _SYSTEM_PROMPT_PHASE3

    # --- L1: Structured Metadata ---

    def _build_metadata_layer(self, ticket: dict) -> str:
        """Build L1: structured ticket metadata beyond subject/conversation.
        
        Includes Tier 1 pre-triage hint and derived metadata flags.
        """
        parts = []
        parts.append("=== METADADOS DO TICKET ===")

        if ticket.get('via_channel'):
            parts.append(f"Canal: {ticket['via_channel']}")

        is_bot = ticket.get('is_claudinha_assigned')
        if is_bot is not None:
            parts.append(f"Atendido por bot (Claudinha): {'Sim' if is_bot else 'Nao'}")

        if ticket.get('assignee_name') and not is_bot:
            parts.append(f"Atendente: {ticket['assignee_name']}")

        if ticket.get('ticket_domain_heuristic') and ticket['ticket_domain_heuristic'] != 'ROUTER_NEEDED':
            heuristic_labels = {
                'B2B_POS': 'POS/Maquininha (B2B)',
                'B2B_SUPPORT': 'Suporte SaaS (B2B)',
                'B2C_FINANCE': 'Financeiro/Cobranca (B2C)',
                'AGENT_CLAUDINHA': 'Bot Claudinha (auto)',
            }
            label = heuristic_labels.get(ticket['ticket_domain_heuristic'],
                                         ticket['ticket_domain_heuristic'])
            parts.append(f"Dominio heuristico: {label}")

        if ticket.get('clinic_id_source'):
            source_labels = {
                'org': 'identificada via organizacao Zendesk',
                'restricted': 'identificada via email (baixa confianca)',
                'none': 'nao identificada',
            }
            parts.append(f"Clinica: {source_labels.get(ticket['clinic_id_source'], ticket['clinic_id_source'])}")

        # --- Tier 1 pre-triage hint ---
        tags = ticket.get('tags', '')
        if isinstance(tags, str):
            tags_list = [t.strip() for t in tags.split(',') if t.strip()]
        else:
            tags_list = tags or []
        
        tier1 = apply_tier1_natureza(tags_list)
        if tier1 and tier1.get('tier1_override'):
            parts.append(f"PRÉ-TRIAGEM DETERMINÍSTICA: root_cause = {tier1['root_cause']} "
                         f"(confiança {tier1['confidence']:.0%}, tag: {tier1['matched_tag']}). "
                         f"USE este valor para root_cause.")
        elif tier1:
            parts.append(f"SUGESTÃO PRÉ-TRIAGEM: root_cause provável = {tier1['root_cause']} "
                         f"(confiança {tier1['confidence']:.0%}, tag: {tier1['matched_tag']}). "
                         f"Confirme ou corrija com base na conversa.")
        
        # --- Derived metadata flags ---
        metadata = derive_metadata_flags(tags_list)
        if metadata.get('is_proactive'):
            parts.append(f"PROATIVO: Este ticket é contato proativo da Capim ({metadata['proactive_type']}). "
                         f"Template: {metadata['matched_template']}")
        if not metadata.get('has_interaction'):
            parts.append("SEM INTERAÇÃO: Ticket sem conversa real (tag sem_interacao). "
                         "Classificação terá baixa confiança — reduza llm_confidence.")

        if len(parts) == 1:  # only header, no metadata
            return ""
        return "\n".join(parts)

    # --- L2: Clinic Profile ---

    def _build_clinic_profile_layer(self, clinic_profile: dict) -> str:
        """Build L2: clinic profile context."""
        if not clinic_profile:
            return ""

        parts = []
        cid = clinic_profile.get('clinic_id', '?')
        name = clinic_profile.get('name', '')
        parts.append(f"=== PERFIL DA CLINICA (ID: {cid}{', ' + name if name else ''}) ===")

        segment = clinic_profile.get('segment', 'unknown')
        parts.append(f"Segmento: {segment}")

        # SaaS status
        bucket = clinic_profile.get('saas_bucket', 'unknown')
        bucket_labels = {
            'current_subscriber': 'Assinante ativo',
            'ex_subscriber': 'Ex-assinante (churn)',
            'never_subscribed': 'Nunca assinou',
        }
        parts.append(f"Status SaaS: {bucket_labels.get(bucket, bucket)}")

        # BNPL status
        is_bnpl = clinic_profile.get('is_bnpl_eligible', False)
        has_contract = clinic_profile.get('has_bnpl_contract', False)
        if is_bnpl and has_contract:
            bnpl_str = "Sim (elegivel + contrato ativo)"
        elif is_bnpl:
            bnpl_str = "Sim (elegivel, sem contrato)"
        else:
            bnpl_str = "Nao"
        parts.append(f"BNPL: {bnpl_str}")

        # POS
        has_pos = clinic_profile.get('has_pos', False)
        parts.append(f"POS (CAPININHA): {'Sim' if has_pos else 'Nao'}")

        # Location (if available)
        uf = clinic_profile.get('uf', '')
        city = clinic_profile.get('city', '')
        if uf:
            loc = f"{city}/{uf}" if city else uf
            parts.append(f"Localizacao: {loc}")

        return "\n".join(parts)

    # --- L3: Disambiguation Rules ---

    def _build_disambiguation_layer(self, ticket: dict, clinic_profile: dict) -> str:
        """Build L3: contextual disambiguation rules based on clinic profile."""
        if clinic_profile:
            is_bnpl = clinic_profile.get('is_bnpl_eligible', False)
            has_contract = clinic_profile.get('has_bnpl_contract', False)
            if is_bnpl or has_contract:
                return _DISAMBIGUATION_BNPL_ACTIVE
            else:
                return _DISAMBIGUATION_NO_BNPL
        else:
            return _DISAMBIGUATION_UNKNOWN_CLINIC

    # --- L5: Conversation ---

    def _build_conversation_layer(self, ticket: dict, max_tokens: int = 1000) -> str:
        """
        Build L5: conversation content (subject + full conversation)
        
        Args:
            ticket: Ticket dict with subject, conversation, tags, etc.
            max_tokens: Maximum tokens for conversation (approx 4 chars/token)
        
        Returns:
            Formatted conversation string
        """
        parts = []
        parts.append(f"Subject: {ticket.get('subject', '')}")
        parts.append(f"Tags: {ticket.get('tags', '')}")
        
        conv = ticket.get('conversation', '') or ''
        
        # Truncate conversation to max_tokens (approx 4 chars/token)
        max_chars = max_tokens * 4
        if len(conv) > max_chars:
            conv = conv[:max_chars] + "\n\n[... conversa truncada ...]"
            logger.debug(f"Conversation truncated to {max_tokens} tokens (~{max_chars} chars)")
        
        parts.append(f"\nConversa completa:\n{conv}")
        
        return "\n".join(parts)

    # --- Compile ---

    def compile(self, ticket: dict) -> tuple:
        """
        Compile a context-aware (system_prompt, user_prompt) pair for a ticket (Phase 3).

        Args:
            ticket: dict with keys from ticket_insights
                Required: subject, tags, conversation
                Optional: via_channel, is_claudinha_assigned, assignee_name,
                          ticket_domain_heuristic, clinic_id, clinic_id_source

        Returns:
            (system_prompt: str, user_prompt: str)
        
        Prompt Architecture (Phase 3):
            System Prompt: L1 (Task) + L2 (Taxonomy) + L3 (Disambiguation)
            User Prompt:   L4 (Clinic Profile) + L5 (Conversation)
        """
        # Resolve clinic profile
        clinic_id = ticket.get('clinic_id')
        clinic_profile = self.clinic_loader.get(clinic_id)

        # --- System Prompt: L1 + L2 + L3 ---
        l1_task = self._get_base_prompt()
        l2_taxonomy = _build_canonical_vocab_section()
        l3_disambiguation = self._build_disambiguation_layer(ticket, clinic_profile)
        
        system_prompt = f"{l1_task}\n\n{l2_taxonomy}\n\n{l3_disambiguation}"

        # --- User Prompt: [L1_metadata] + L4 + L5 ---
        l1_metadata = self._build_metadata_layer(ticket)
        l4_clinic = self._build_clinic_profile_layer(clinic_profile)
        l5_conversation = self._build_conversation_layer(ticket, max_tokens=1000)

        user_parts = ["Analise este ticket:\n"]
        if l1_metadata:
            user_parts.append(l1_metadata)
        if l4_clinic:
            user_parts.append(l4_clinic)
        user_parts.append(f"\n=== CONVERSA ===\n{l5_conversation}")
        user_parts.append("\nRetorne apenas o JSON válido com os 7 campos.")

        user_prompt = "\n\n".join(user_parts)

        return system_prompt, user_prompt

    # --- Stats ---

    def get_compilation_stats(self, ticket: dict) -> dict:
        """Get token estimates for a compiled prompt (for cost tracking)."""
        system_prompt, user_prompt = self.compile(ticket)
        sys_tokens = len(system_prompt) // 4
        usr_tokens = len(user_prompt) // 4
        clinic_profile = self.clinic_loader.get(ticket.get('clinic_id'))
        return {
            'system_tokens_est': sys_tokens,
            'user_tokens_est': usr_tokens,
            'total_tokens_est': sys_tokens + usr_tokens,
            'has_clinic_profile': clinic_profile is not None,
            'has_bnpl': clinic_profile.get('is_bnpl_eligible', False) if clinic_profile else None,
        }


# =============================================================================
# Self-test
# =============================================================================

if __name__ == '__main__':
    print("=" * 70)
    print("Prompt Compiler - Self Test")
    print("=" * 70)

    compiler = PromptCompiler()

    # --- Test Tier 1 pre-triage ---
    print("\n--- Tier 1 Pre-Triage Tests ---")
    
    test_cases_tier1 = [
        (['grupo_cobranca', 'cob_renegociacao_facil'], 'Cobranca_Ativa'),
        (['n2_endosso', 'bnpl_endosso'], 'Endosso_Repasse'),
        (['venda_si_suporte'], 'Contratacao_Acompanhamento'),
        (['venda_apenas_acompanhamento'], 'Contratacao_Acompanhamento'),
        (['venda_si_telefone'], 'Contratacao_Suporte_Paciente'),
        (['venda_si_docs'], 'Contratacao_Suporte_Paciente'),
        (['venda_dificuldade_na_assinatura'], 'Technical_Issue'),
        (['loss', 'cancelamento'], 'Subscription_Cancelamento'),
        (['bug_saas', 'saas'], 'Technical_Issue'),
        (['n2_saas_financeiro_carne'], 'Carne_Capim'),
        (['saas_login'], 'Acesso'),  # MEDIUM confidence, tier1_override=False
        (['duvida', 'informacao'], None),  # No match
    ]
    
    for tags, expected in test_cases_tier1:
        result = apply_tier1_natureza(tags)
        got = result.get('root_cause')
        override = result.get('tier1_override', False)
        conf = result.get('confidence', 0)
        status = 'OK' if got == expected else 'FAIL'
        print(f"  [{status}] tags={tags[:2]} -> {got} (conf={conf:.0%}, override={override}) [expected: {expected}]")
    
    # --- Test metadata derivation ---
    print("\n--- Metadata Derivation Tests ---")
    
    test_cases_meta = [
        (['template_contrato_validado', 'grupo_cobranca'], True, 'outbound_human', True),
        (['template_cob_lembrete_3', 'grupo_cobranca'], True, 'system_automated', True),
        (['template_cxsolicitandocontato', 'saas'], False, None, True),   # response template → NOT proactive
        (['sem_interacao', 'saas'], False, None, False),                  # no interaction
        (['duvida', 'saas'], False, None, True),                          # normal ticket
    ]
    
    for tags, exp_proactive, exp_type, exp_interaction in test_cases_meta:
        result = derive_metadata_flags(tags)
        ok = (result['is_proactive'] == exp_proactive and 
              result['proactive_type'] == exp_type and 
              result['has_interaction'] == exp_interaction)
        status = 'OK' if ok else 'FAIL'
        print(f"  [{status}] tags={tags[:2]} -> proactive={result['is_proactive']}, "
              f"type={result['proactive_type']}, interaction={result['has_interaction']}")
    
    # --- Test full compilation ---
    print("\n" + "=" * 70)
    print("Test without clinic profiles (L4 disabled)")
    print("=" * 70)
    
    # Test without clinic profiles (L4 disabled)
    test_ticket = {
        'subject': 'Problema com boleto',
        'tags': 'cob_renegociacao_facil, grupo_cobranca',
        'conversation': 'Paciente: Ola, meu boleto nao aparece...',
        'via_channel': 'web_messaging',
        'is_claudinha_assigned': False,
        'assignee_name': 'Daniela',
        'ticket_domain_heuristic': 'B2C_FINANCE',
        'clinic_id': None,
        'clinic_id_source': 'none',
    }

    sys_prompt, usr_prompt = compiler.compile(test_ticket)

    print(f"\n--- System Prompt ({len(sys_prompt)} chars, ~{len(sys_prompt)//4} tokens) ---")
    print(sys_prompt[:500] + "...\n")

    print(f"--- User Prompt ({len(usr_prompt)} chars, ~{len(usr_prompt)//4} tokens) ---")
    print(usr_prompt)

    # Test with mock clinic profile
    print("\n" + "=" * 70)
    print("Test with mock clinic profile (L2 enabled)")
    print("=" * 70)

    compiler.clinic_loader.profiles[12345] = {
        'clinic_id': 12345,
        'name': 'Odonto Premium SP',
        'segment': 'Independente',
        'is_subscriber': True,
        'saas_bucket': 'current_subscriber',
        'is_bnpl_eligible': True,
        'has_bnpl_contract': True,
        'has_pos': False,
        'uf': 'SP',
        'city': 'Sao Paulo',
        'interest_category': 'Ortodontia',
        'credit_score': 3,
    }
    compiler.clinic_loader._loaded = True

    test_ticket['clinic_id'] = 12345
    test_ticket['clinic_id_source'] = 'org'

    sys_prompt, usr_prompt = compiler.compile(test_ticket)

    print(f"\n--- System Prompt ({len(sys_prompt)} chars, ~{len(sys_prompt)//4} tokens) ---")
    # Show just the L3 part (disambiguation) — encode-safe for Windows
    idx = sys_prompt.find('REGRAS DE DESAMBIG')
    if idx > 0:
        print(f"[L0: {idx} chars of base prompt]\n")
        # Safe print for Windows (cp1252 doesn't support all Unicode)
        try:
            print(sys_prompt[idx:])
        except UnicodeEncodeError:
            print(sys_prompt[idx:].encode('ascii', errors='replace').decode('ascii'))

    print(f"\n--- User Prompt ({len(usr_prompt)} chars, ~{len(usr_prompt)//4} tokens) ---")
    print(usr_prompt)

    # Token statistics (Phase 3)
    print("\n" + "=" * 70)
    print("Token Statistics (Phase 3)")
    print("=" * 70)

    test_ticket['clinic_id'] = 12345
    stats = compiler.get_compilation_stats(test_ticket)
    print(f"  System tokens:  ~{stats['system_tokens_est']:4d}")
    print(f"  User tokens:    ~{stats['user_tokens_est']:4d}")
    print(f"  TOTAL INPUT:    ~{stats['total_tokens_est']:4d} (target: ~1400)")
    print(f"  Expected OUTPUT: ~700 tokens (7 LLM variables)")
    print(f"  COST/ticket:     ~${(stats['total_tokens_est'] * 0.005 + 700 * 0.025) / 1000:.4f} (Opus 4.6)")

    print("\n[OK] Prompt Compiler ready (Phase 3.1 — Natureza v3 + n2_* Tier 1 + metadata flags)")
