# Taxonomia de 3 Eixos Ortogonais — CLIENT_VOICE

> **Status**: ✅ Sacramentada (audit-aligned)  
> **Version**: 3.2 (Contratacao split + venda_* -> BNPL + metadata complementar ativa)  
> **Decisões**: 19.11-19.17, 19.22-19.29 (`DECISIONS_IN_PROGRESS.md`)  
> **Validade**: Substitui `CATEGORY_TAXONOMY.md` (legacy LLM intent-based)

---

## 🎯 Princípio Fundamental

**Cada ticket é classificado em 3 dimensões ortogonais**:

```
Ticket = Produto × Natureza × Atendimento
```

- **Produto** (WHAT): Qual produto/área Capim está envolvido?
- **Natureza** (WHY): Qual a natureza do problema/consulta? (19 valores v3.2)
- **Atendimento** (HOW): Como o atendimento foi realizado? (bot vs humano)

**Ortogonalidade**: As dimensões são independentes. Um ticket pode ser:
- `BNPL × Cobranca_Ativa × Bot_Escalado`
- `SaaS × Technical_Issue × Humano_Direto`
- `BNPL × Contratacao_Acompanhamento × Escalacao_Solicitada`

**Nota**: "Atendimento" se refere ao **tipo de handling** (bot/humano/escalação), não ao **canal físico** (`via_channel`: WhatsApp, email, widget). O canal físico é metadata complementar, não eixo taxonômico.

---

## 📊 EIXO 1: PRODUTO (product_area)

### **Valores L1** (5 categorias principais)

| Valor | Descrição | Volume % | Subcategorias (L2) |
|:---|:---|:---:|:---|
| **BNPL** | Crédito parcelado, cobrança, endosso | snapshot histórico | Cobranca, Servicing, Originacao, Contratacao |
| **SaaS** | Plataforma clínica, agenda, orçamento | snapshot histórico | Clinico, Conta, Lifecycle |
| **Onboarding** | Credenciamento e ativação operacional | snapshot histórico | Credenciamento, Ativacao |
| **POS** | Maquininha Capininha (hardware) | snapshot histórico | Entrega, Operacao, Configuracao |
| **Indeterminado** | Não foi possível determinar | snapshot histórico | *(target: <12%)* |

### **Subcategorias L2**

#### **BNPL** (L2):
- **Cobranca**: Tickets de cobrança, renegociação, boletos
- **Servicing**: Contratos, parcelas, alterações pós-aprovação
- **Originacao**: Simulações, aprovações, crivo (pre-booking)

#### **SaaS** (L2):
- **Clinico**: Agenda, pacientes, procedimentos, orçamentos
- **Conta**: Assinatura, planos, billing Capim, login, acesso
- **Lifecycle**: Migração, cancelamento, renovação, inadimplência SaaS

### **Subcategorias L2** (update 2026-02-13)

#### **Onboarding** (L2):
- **Credenciamento**: Processo de credenciamento BNPL/POS, documentos, aprovação
- **Ativacao**: Primeiro acesso, configuração inicial, setup

#### **POS** (L2):
- **Entrega**: Rastreio, envio, correios, logística
- **Operacao**: Uso da maquininha, transações, taxas
- **Configuracao**: Setup, instalação, ativação da maquininha

### **Lógica de Classificação (Produto): Fluxo Completo**

> **Princípio (v2.1 - 2026-02-13)**: Tags e themes determinam EXCLUSIVAMENTE. Root_cause NÃO é fallback.
> **Implementação**: `scripts/reprocess_tickets_full_taxonomy.py :: classify_produto()`
> **Mudança**: Removido uso de root_cause como fallback (dependência circular eliminada)

```
╔══════════════════════════════════════════════════════════════╗
║     COMO UM TICKET É CLASSIFICADO NO EIXO PRODUTO          ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  ENTRADA: tags[], key_themes[] (do LLM), root_cause,        ║
║           full_conversation                                  ║
║                                                              ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ PASSO 1: POS por tag explícita                          │ ║
║  │   tags contém "saas__maquininha", "maquininha",         │ ║
║  │   "capininha"? Ou conversa cita "capininha"?            │ ║
║  │   → SIM → L1 = POS                                     │ ║
║  │   → NÃO → continua                                     │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                         ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ PASSO 2: Scoring (tags +2, themes +1)                   │ ║
║  │   Para BNPL, Onboarding, SaaS:                          │ ║
║  │   - Cada tag que matcha      → +2 pontos                │ ║
║  │   - Cada theme que matcha    → +1 ponto                 │ ║
║  │   Vencedor com score >= 2    → L1 = vencedor            │ ║
║  │   Se empate/nada >= 2        → continua                 │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                         ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ PASSO 3: Nada matchou → L1 = Indeterminado             │ ║
║  │   (ACEITÁVEL! Melhorar via tag enrichment)              │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                         ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ PASSO 4: POST-HOC VALIDATION (não fallback!)            │ ║
║  │   Se root_cause = "debt_collection" MAS product != BNPL │ ║
║  │   → FLAG como conflito para investigação                │ ║
║  │   → NÃO auto-corrigir (pode ser tag ruim, LLM erro)    │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                                                              ║
║  ═══════════════════════════════════════════════════════════  ║
║                                                              ║
║  COMO O L2 É DETERMINADO (v2.1 - 2026-02-13):               ║
║                                                              ║
║  1. Tenta match por patterns nas tags/themes                 ║
║     Ex: BNPL + tag "cob_*" → L2 = Cobranca                 ║
║     Ex: SaaS + theme "agenda" → L2 = Clinico                ║
║                                                              ║
║  2. Se pattern não matcha → L2 = NULL (ACEITÁVEL!)          ║
║     (root_cause cross-cutting não determinam L2)             ║
║     Target: 78% cobertura L2 via tag/theme enrichment        ║
║                                                              ║
║  REMOVED: root_cause fallback para L2 (dependência circular) ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

### **Tag/Theme Patterns por L1**

```yaml
BNPL:
  tags: [cob_*, grupo_cobranca, bnpl_*, endosso, template_contrato_*]
  themes: [cobranca, renegociacao, parcela, boleto, contrato, financiamento, bnpl]

SaaS:
  tags: [saas*, bug_*, login, loss, nao_assinante, cancelamento]
  themes: [agenda, orcamento, paciente, transacao, configuracao, relatorio, assinatura]
  exclusion: NOT saas__maquininha (isso é POS)

Onboarding:
  tags: [venda*, onboarding, credenciamento, venda_si_*]
  themes: [credenciamento, onboarding, documento, ativacao]

POS:
  tags: [saas__maquininha, maquininha, capininha]
  themes: [maquininha, entrega, capininha]
  ambiguity: "maquininha" textual → Prompt Compiler L3 + clinic profile

Indeterminado:
  fallback: quando nenhum dos acima tem score >= 2
```

### **L2 Patterns (para `_get_l2_subcategory`)**

```yaml
BNPL:
  Cobranca: [cob_*, renegociacao, boleto, faixa_*, codigo_cobranca, cobranca]
  Servicing: [bnpl_servicing, contrato, parcela, link_pagamento, servicing]
  Originacao: [simulacao, aprovacao, crivo, analise_credito, financiamento, credito]
  Contratacao: [venda_si_*, venda, contratacao, proposta, assinatura_digital, assinatura_contrato]

SaaS:
  Clinico: [agenda, paciente, procedimento, orcamento, contato_paciente]
  Conta: [assinatura, plano, billing, login, acesso, assinatura_contrato, renovacao_plano]
  Lifecycle: [migracao, cancelamento, renovacao, inadimplencia, cancelamento_saas, migracao_dados]

Onboarding:
  Credenciamento: [credenciamento, credenciar, documentacao]
  Ativacao: [onboarding, ativacao, primeiro_acesso, configuracao_inicial]

POS:
  Entrega: [entrega, rastreio, envio, correios]
  Operacao: [maquininha, capininha, transacao, taxa]
  Configuracao: [configuracao, setup, instalacao, ativacao]
```

### **L2 Coverage Target** (v2.1 - 2026-02-13)

**REMOVED**: L2 fallback por root_cause (dependência circular eliminada)

**Nova estratégia**:
- L2 determinado APENAS por tags/themes patterns
- Se pattern não matcha → L2 = NULL (aceitável!)
- Target: manter 78% cobertura L2 via tag/theme enrichment
- Investigar tickets com L2=NULL para identificar padrões perdidos

### **Cobertura L2 (N=400, validação 2026-02-13)**

| L1 | Com L2 | Sem L2 | Cobertura |
|:---|---:|---:|---:|
| BNPL | 83 | 24 | 77.6% |
| SaaS | 108 | 20 | 84.4% |
| Onboarding | 83 | 0 | **100%** |
| POS | 37 | 0 | **100%** |
| Indeterminado | 0 | 45 | 0% (by design) |
| **Total** | **311** | **89** | **77.8%** |

**Nota**: Tickets sem L2 têm root_cause "cross-cutting" (information_request, feature_request, complaint, indeterminado) que não mapeiam naturalmente a nenhum L2 específico.

### **Regras especiais**:
- **Assinatura SaaS** → `SaaS.Conta` (não é produto separado)
- **Plataforma** → `SaaS.Conta` (conta Capim)
- **"Maquininha" ambígua** → Contexto clínico (clinic profile) + Prompt Compiler L3

### **Canal físico (metadata, NÃO é eixo taxonômico)**

```yaml
via_channel:
  valores_reais: [whatsapp (78.8%), native_messaging (14.9%), web (3.9%), email (2.3%), api (0.1%)]
  nota: NÃO existe phone/voice na base (100% digital)
  fonte: Zendesk raw (via_channel field)
  uso: Análises complementares (ex: "Bot_Escalado via WhatsApp")
```

---

## 🧬 EIXO 2: NATUREZA (root_cause / nature)

> **Version**: 3.2 (Contratacao split + venda_* → BNPL, 2026-02-13)
> **Decisões**: venda_* investigation + Contratacao split (plan: contratacao_split_+_venda_bnpl_fix_1c598311)
> **Mudança vs v3.1**: Split de `Contratacao` em 2 Naturezas: `Contratacao_Acompanhamento` (follow-up genérico) + `Contratacao_Suporte_Paciente` (fricção: telefone, docs, assinatura, SMS). Absorção de `venda_dificuldade_na_assinatura` em `Technical_Issue`. Correção: venda_* tags agora mapeiam para BNPL (não Onboarding).
> **Evidência**: Deep dive investigation em venda_* tags (N=1000 Golden Set + full population query).

### **Valores** (19 categorias)

| Valor | Descrição | Afinidade Produto | Sinal Determinístico |
|:---|:---|:---|:---|
| **Simulacao_Credito** | C1: recusa, aprovação, consulta de score, elegibilidade | BNPL | tag `bnpl_creditoquestionando_recusa` |
| **Contratacao_Acompanhamento** | C2: follow-up genérico de venda (clínica acompanhando paciente) | BNPL | tags `venda_si_suporte`, `venda_apenas_acompanhamento`, `venda_sem_suporte` |
| **Contratacao_Suporte_Paciente** | C2: fricção em telefone, docs, assinatura digital, SMS | BNPL | tags `venda_si_telefone`, `venda_si_docs`, `venda_si_assinatura`, `venda_si_sms` |
| **Endosso_Repasse** | C2→C2S: confirmação, ligação banco, liberação endosso, repasse $$ para clínica | BNPL | tags `n2_endosso`, `n1_endosso`, `n2_bnpl_endosso` |
| **Cobranca_Ativa** | Post-C2S: boleto, parcelas, inadimplência, renegociação (paciente devedor) | BNPL | tags `grupo_cobranca`, `bnpl_boleto`, `cob_renegociação_fácil`, `agente_cobranca` |
| **Credenciamento** | Processo de credenciamento de clínica para BNPL e/ou POS | **BNPL** (43%), **POS** (33%) | tags `credenciamento`, `bnpl_duvidas_em_credenciamento`, `n2_bnpl_duvidas_em_credenciamento` |
| **Migracao** | Migração de sistema/dados (SaaS lifecycle) | SaaS | tags `migracao`, `saas_migracao_base` |
| **Process_Generico** | Outros processos operacionais (não credenciamento, não contratação) | cross-cutting | — (LLM Tier 2) |
| **Subscription_Pagamento** | Inadimplência/bloqueio assinatura SaaS | SaaS | tags `saas_pagamento`, `n2_saas_pagamento` |
| **Subscription_Cancelamento** | Pedido de cancelamento SaaS (churn) | SaaS | tag `loss` |
| **Forma_Pagamento** | Consultas transacionais sobre pagamento ("como pago?", "qual o boleto?") | cross-cutting | — (LLM Tier 2) |
| **Financial_Inquiry** | Consultas informativas de pacientes sobre contratos ativos ("quantas parcelas?") | BNPL | sentiment >= 3.5 + actor = Paciente |
| **Negativacao** | Negativação, protesto, Serasa | BNPL | — (LLM Tier 2, baixo volume) |
| **Operational_Question** | Dúvidas de uso, configuração, "como faço X?" | SaaS, POS | — (LLM Tier 2) |
| **Technical_Issue** | Bugs, falhas técnicas, instabilidade (inclui `venda_dificuldade_na_assinatura`) | SaaS, POS, BNPL | tags `bug_*`, `venda_dificuldade_na_assinatura` |
| **Acesso** | Login, senha, bloqueio, permissão | SaaS, POS | tag `saas_login` |
| **Carne_Capim** | Saque, recebimento, transação Carnê Capim | SaaS | — (LLM Tier 2, tema "carnê"/"saque") |
| **Alteracao_Cadastral** | Dados bancários, telefone, CNPJ, email | cross-cutting | themes `dados_bancarios`, `conta_bancaria`, `cnpj` |
| **Unclear** | Não foi possível determinar com confiança | — | confidence < 0.75 |

### **Agrupamentos Lógicos**

#### **1. Funil BNPL** (5 etapas)
- `Simulacao_Credito`: Etapa C1 — análise de crédito, aprovação/recusa, score
- `Contratacao_Acompanhamento`: Etapa C2 (follow-up) — clínica acompanhando venda, suporte genérico
- `Contratacao_Suporte_Paciente`: Etapa C2 (fricção) — dificuldades em telefone, docs, assinatura, SMS
- `Endosso_Repasse`: Etapa C2→C2S — confirmação, ligação banco, repasse para clínica
- `Cobranca_Ativa`: Post-C2S — vida do contrato, boleto, renegociação, inadimplência

**Nota histórica**: O antigo `debt_collection` (v2.0) era catch-all. Em v3.1, split em 4 etapas. Em v3.2, `Contratacao` split em 2 sub-naturezas para separar follow-up genérico vs fricção específica (telefone, docs, assinatura). **Tags `venda_*` agora mapeiam para BNPL**, não Onboarding (correção semântica: todas referem-se à venda BNPL).

#### **2. Processos Operacionais** (3 valores)
- `Credenciamento`: Workflow crítico de conversão — clínica se credencia para **BNPL** (43%) ou **POS** (33%). NÃO é Onboarding genérico.
- `Migracao`: Evento de risco (SaaS lifecycle)
- `Process_Generico`: Outros processos (documentação, configuração, treinamento)

#### **3. Assinatura SaaS** (2 valores)
- `Subscription_Pagamento`: Inadimplência SaaS (bloqueio)
- `Subscription_Cancelamento`: Churn (decisão do cliente)

#### **4. Financeiro / Transacional** (3 valores)
- `Financial_Inquiry`: Consultas informativas de pacientes (sentiment alto, não é issue)
- `Forma_Pagamento`: Consultas transacionais ("como pago?", "qual boleto?", "link de pagamento")
- `Negativacao`: Caso extremo (Serasa, protesto), baixo volume mas crítico

#### **5. Suporte / Técnico** (3 valores)
- `Operational_Question`: Dúvidas de uso (sentiment alto, não é issue)
- `Technical_Issue`: Bugs, falhas (sentiment baixo)
- `Acesso`: Login, senha, bloqueio, permissão

#### **6. Cross-cutting** (3 valores)
- `Carne_Capim`: Natureza específica SaaS — saque, recebimento, transação Carnê
- `Alteracao_Cadastral`: Dados bancários, telefone, CNPJ (absorveu antigo `financial_operations` parte cadastral + `data_quality`)
- `Unclear`: LLM não conseguiu determinar com confiança

### **Lógica de Detecção (Natureza)**

**Pipeline**: Deterministic signals (Tier 1) → LLM semantic extraction (Tier 2)

```yaml
Deterministic (Tier 1 — alta confiança, tags/metadata):

  # ── FUNIL BNPL ──────────────────────────────────────────────
  Cobranca_Ativa:
    - tags: [grupo_cobranca, agente_cobranca, bnpl_boleto, bnpl_cobranca,
             cob_renegociação_fácil, cob_*, n2_bnpl_boleto, n2_bnpl_cobranca,
             n2_cob_renegociacao, falar_com_atendente_cobranca]
    - confidence: HIGH (0.90+)
    - nota: grupo_cobranca é 97.9% preditivo de cobrança real (Post-C2S).
            template_cob_* é subset perfeito de grupo_cobranca (0 isolados).
    - auditoria: 7/7 meses estável (19-34%), 0.01% contradições.
  
  Contratacao:
    - tags: [venda_si_suporte, venda_apenas_acompanhamento,
             n2_venda_si_telefone, n2_venda_si_docs, n2_venda_si_assinatura,
             n2_venda_si_suporte, venda_si_telefone, venda_si_docs,
             venda_si_assinatura, venda_dificuldade_na_assinatura,
             n2_venda_dificuldade_na_assinatura]
    - themes: [proposta_bnpl, plano_tratamento, assinatura_digital, documentacao]
    - confidence: HIGH (0.85+)
    - nota: 88 tickets no golden set, 94% Onboarding. Trust 93.8%.
    - auditoria: venda_si_suporte estável 4-6% (7/7 meses).

  Endosso_Repasse:
    - tags: [n2_endosso, n1_endosso, n2_bnpl_endosso, bnpl_endosso]
    - themes: [endosso, repasse, liberacao_pagamento]
    - confidence: HIGH (0.85+)
    - auditoria: n2_endosso estável 7/7 meses (1890 tickets).
  
  Simulacao_Credito:
    - tags: [bnpl_creditoquestionando_recusa]
    - themes: [analise_credito, aprovacao_credito, recusa_credito, score]
    - confidence: MEDIUM (0.75+)

  # ── PROCESSOS ───────────────────────────────────────────────
  Credenciamento:
    - tags: [credenciamento, bnpl_duvidas_em_credenciamento,
             n2_bnpl_duvidas_em_credenciamento,
             bnpl__documentos_para_credenciamento]
    - themes: [credenciamento, onboarding, documento]
    - confidence: HIGH (0.85+)
    - auditoria: n2 tag estável 7/7 meses (1012 tickets).
  
  Migracao:
    - tags: [migracao, saas_migracao_base, n2_saas_migracao_base]
    - themes: [migracao] + produto = SaaS
    - confidence: HIGH (0.85+)
    - auditoria: n2_saas_migracao_base estável 7/7 meses (729 tickets).

  # ── ASSINATURA SAAS ────────────────────────────────────────
  Subscription_Pagamento:
    - tags: [saas_pagamento, n2_saas_pagamento, lancamento_concluido]
    - confidence: HIGH (0.85+)
    - auditoria: n2_saas_pagamento estável 7/7 meses (2322 tickets).
    - nota_lancamento: lancamento_concluido tem drift temporal (18%→5%),
                       mas 78% dos tickets com essa tag são subscription_issue.
                       Usar como sinal aditivo (não exclusivo).
  
  Subscription_Cancelamento:
    - tags: [loss, saas_churn, n2_saas_churn, n2_cancelamento, cancelamento]
    - confidence: HIGH (0.80+)
    - auditoria: loss trust 92.0%. n2_saas_churn estável 7/7 meses (623 tickets).

  # ── SUPORTE / TÉCNICO ──────────────────────────────────────
  Acesso:
    - tags: [saas_login, n2_saas_login]
    - themes: [login, senha, acesso]
    - confidence: ⚠️ MEDIUM (0.70+) — NÃO HIGH
    - auditoria: Trust 53.3% (47% são technical_issue/info_request).
                 Tag indica "área de login" não "problema de acesso".
                 LLM Tier 2 deve refinar.

  Technical_Issue:
    - tags: [bug_saas, bug_*, n2_bug_agenda, n2_bug_pacientes]
    - themes: [bug, instabilidade, erro_sistema]
    - confidence: HIGH (0.81+)
    - auditoria: bug_* trust 81.2%. n2_bug_agenda estável 7/7 meses.

  Operational_Question:
    - tags: [saas_treinamento, n2_saas_treinamento,
             n2_bnpl_duvidas_e_suporte, bnpl_duvidas_e_suporte,
             n2_saas_suporte]
    - themes: [treinamento, configuracao, como_fazer]
    - confidence: MEDIUM (0.75+)
    - nota: n2_bnpl_duvidas_e_suporte mapeia para dúvidas BNPL operacionais.

  # ── FINANCEIRO / TRANSACIONAL ──────────────────────────────
  Carne_Capim:
    - tags: [saas_financeiro_carne, n2_saas_financeiro_carne]
    - themes: [carnê, saque, recebimento_carne]
    - confidence: HIGH (0.85+)
    - auditoria: n2_saas_financeiro_carne estável 7/7 meses (196 tickets).

  Alteracao_Cadastral:
    - tags: [saas_alteracao_dados, n2_saas_alteracao_dados]
    - themes: [dados_bancarios, conta_bancaria, cnpj, alteracao_dados]
    - confidence: HIGH (0.85+)
    - auditoria: n2_saas_alteracao_dados estável 7/7 meses (462 tickets).

  Forma_Pagamento:
    - tags: [saas_financeiro_menoscarne, n2_saas_financeiro_menoscarne]
    - themes: [pagamento, boleto, link_pagamento]
    - confidence: MEDIUM (0.75+)
    - nota: "financeiro_menoscarne" = financeiro SaaS excluindo carnê.
  
  Financial_Inquiry:
    - sentiment >= 3.5
    - themes: [contrato, parcela, pagamento]
    - actor: Paciente (não clínica)
    - confidence: HIGH (0.90+)

LLM Semantic (Tier 2 — para tickets sem sinal determinístico):
  - Prompt Compiler 5-layer (L0-L4)
  - Model: tier-dependent (Opus/Sonnet/Haiku)
  - Confidence threshold: 0.75
  - Fallback: "Unclear" if < 0.75
  - Valores que dependem primariamente de LLM:
    - Process_Generico, Negativacao
    - Operational_Question (parcial — dúvidas sem tag n2)
    - Technical_Issue (parcial — bugs sem tag bug_*)
```

### **Auditoria de Confiabilidade das Tags (N=78.018, 6 meses)**

> **Data**: 2026-02-13 | **Decisão**: 19.26-19.28

**Cobertura**: 99.9% dos tickets têm tags (média 7.3 tags/ticket).

| Tag / Grupo | Trust Score | Estabilidade | Contradições | Veredito |
|:---|:---:|:---:|:---:|:---:|
| `grupo_cobranca` | 97.9% | 7/7 meses | 0.01% | **Tier 1 HIGH** |
| `template_cob_*` | 100% | 7/7 meses | 0% (subset de grupo_cobranca) | Redundante |
| `loss` | 92.0% | 7/7 meses | 0.06% | **Tier 1 HIGH** |
| `venda_si_suporte` | 93.8% | 7/7 meses | 0.01% | **Tier 1 HIGH** |
| `bug_*` | 81.2% | 7/7 meses | — | **Tier 1 HIGH** |
| Todos `n2_*` | — | **7/7 meses (top 25)** | 0.03% | **Tier 1 HIGH** |
| `cloudhumans` | — | 7/7 meses | 0% | **Tier 1 HIGH** (bot) |
| `saas_login` | **53.3%** | 7/7 meses | — | **⚠️ Tier 1 MEDIUM** |
| `droz_ativo` | — | **30.6%→3.0% (MORRENDO)** | — | **❌ NÃO USAR** |
| `lancamento_concluido` | 78% | **18.1%→4.6% (INSTÁVEL)** | — | **⚠️ Aditivo apenas** |

**Tags descartadas como sinal Tier 1**:
- ❌ `droz_ativo`: Caiu de 30.6% → 3.0% em 6 meses. Workflow Zendesk mudou.
- ❌ `droz_switchboard`: 93.5% dos tickets (infraestrutura, não seletivo).
- ❌ `template_*` genérico: 16.6% são templates de resposta (não proativos).

### **Regras de desambiguação**
- **Credenciamento vs Contratacao_Acompanhamento / Contratacao_Suporte_Paciente**: Credenciamento = ativação da clínica na plataforma. Contratação BNPL = jornada C2 de um paciente específico.
- **Contratacao_Acompanhamento vs Simulacao_Credito**: acompanhamento genérico de proposta/documentação (C2) vs análise/recusa (C1).
- **Contratacao_Suporte_Paciente vs Technical_Issue**: fricção de telefone, docs, SMS ou assinatura do paciente continua em Natureza BNPL; bugs sistêmicos ficam em `Technical_Issue`.
- **Endosso_Repasse vs Cobranca_Ativa**: Endosso_Repasse = clínica quer receber $$. Cobranca_Ativa = paciente deve $$. Dinâmicas opostas.
- **Endosso_Repasse vs Financial_Inquiry**: Endosso_Repasse = clínica com problema de repasse. Financial_Inquiry = paciente consultando status (informativo, sentiment alto).
- **Forma_Pagamento vs Financial_Inquiry**: Forma_Pagamento = "como pago?" (transacional). Financial_Inquiry = "quantas parcelas faltam?" (informativo).
- **Operational_Question vs Technical_Issue**: Sentiment (3.0 threshold) + themes (configuração vs bug).
- **Acesso vs Technical_Issue**: Acesso = login/senha/permissão. Technical_Issue = bug/instabilidade do sistema.
- **Migracao vs Process_Generico**: key_themes + produto = SaaS + evento de risco.

### **Mapa de-para (valores antigos → v3)**

```
debt_collection ──┬── [grupo_cobranca/bnpl_boleto/cob_*] ──→ Cobranca_Ativa
                  ├── [n2_endosso/n1_endosso] ──────────────→ Endosso_Repasse
                  ├── [venda_si_*/template_cx* sem fricção] ─→ Contratacao_Acompanhamento
                  ├── [telefone/docs/sms/assinatura] ────────→ Contratacao_Suporte_Paciente
                  ├── [bnpl_creditoquestionando_recusa] ────→ Simulacao_Credito
                  └── [sem sinal] ──────────────────────────→ LLM decide

financial_operations ──┬── [repasse/endosso] ──→ Endosso_Repasse
                       ├── [dados_bancarios] ──→ Alteracao_Cadastral
                       └── [carnê/saque] ──────→ Carne_Capim

process_issue ──┬── [Onboarding: doc inicial] ─────→ Credenciamento
                ├── [BNPL: endosso/contrato] ──────→ Endosso_Repasse ou Contratacao_Acompanhamento
                └── [SaaS: workflow] ──────────────→ Process_Generico

subscription_issue ──┬── [pagamento/bloqueio] ──→ Subscription_Pagamento
                     └── [cancelamento/loss] ───→ Subscription_Cancelamento

pos_issue ──→ MORTO (era Produto, não Natureza). POS usa naturezas genéricas.
information_request ──→ Financial_Inquiry / Operational_Question / Forma_Pagamento
access_issue ──→ Acesso
migration_issue ──→ Migracao
operational_issue ──→ Operational_Question
technical_issue ──→ Technical_Issue
Credit_Issue (Fase 3) ──→ Simulacao_Credito (renomeado)
Financial_Issue (Fase 3) ──→ Endosso_Repasse (absorvido, 0.03%)
Other (Fase 3) ──→ Unclear (consolidado)
user_error ──→ Operational_Question
feature_request ──→ Unclear (baixo volume)
data_quality ──→ Alteracao_Cadastral
complaint ──→ absorvido (sentiment já captura)
integration_issue ──→ Technical_Issue
```

---

## 📞 EIXO 3: ATENDIMENTO (service_type / handling)

### **Valores** (4 categorias)

| Valor | Descrição | Volume % (estimado) | Interpretação |
|:---|:---|:---:|:---|
| **Bot_Escalado** | Bot tocou o ticket, humano assumiu | ~25-30% | Bot identificou limite ou roteou |
| **Bot_Resolvido** | Bot resolveu sem intervenção humana | ~15-17% | Autoatendimento eficaz |
| **Escalacao_Solicitada** | Cliente pediu humano explicitamente | ~3-5% | Cliente quer human touch |
| **Humano_Direto** | Sem evidência de envolvimento do bot | ~55-60% | Canal sem bot (web, email) ou roteamento direto |

### **Descoberta Crítica: 3 Camadas de Evidência de Bot (2026-02-13)**

O `is_claudinha_assigned` é um **snapshot final**, não histórico. Quando ClaudIA escala:

```
Ticket aberto → ClaudIA atende → ClaudIA escala → Humano assume
                                                    ↑
                                        is_claudinha_assigned = FALSE (assignee mudou!)
```

**56.5%** dos tickets com tag `transbordo_botweb` têm `is_claudinha_assigned = FALSE`.

Investigação empírica revelou **duas tags-chave** que capturam bot involvement:

| Tag | Canal | Significado | Volume | Confiança |
|:---|:---|:---|---:|:---|
| `cloudhumans` | WhatsApp (99.8%) | Ticket passou pela plataforma CloudHumans/ClaudIA | 54,684 (31.8%) | Alta |
| `transbordo_botweb` | Native messaging (99.7%) | Escalação formal do bot web | 3,620 (2.1%) | Alta |

Essas tags são **mutuamente exclusivas** (0 tickets com ambas) e representam **dois pipelines de bot diferentes**.

**Evolução temporal**:
- `cloudhumans`: presente desde fev/2025 (~25% → 43%, crescendo)
- `transbordo_botweb`: nasce em dez/2025 (7% → 23%, crescendo)

**Distribuição global de sinais de bot**:

```
Sem evidência de bot                104,034 (60.5%)
CloudHumans (WhatsApp bot)           54,684 (31.8%)
  ├─ claudinha=TRUE (resolvido)      17,575 (10.2%)
  └─ claudinha=FALSE (escalado)      37,109 (21.6%)
Claudinha assigned (sem tag)          9,578 (5.6%)
Transbordo (native messaging bot)     3,620 (2.1%)
  ├─ claudinha=TRUE (resolvido N1)    1,576 (0.9%)
  └─ claudinha=FALSE (escalado)       2,044 (1.2%)
```

### **Lógica de Classificação (Atendimento)**

> **Princípio**: Bot involvement requer **evidência** (tags, assignee, texto). `conv_len` NÃO é proxy de bot.
> **Implementação**: `scripts/reprocess_tickets_full_taxonomy.py :: classify_atendimento()`

```
╔══════════════════════════════════════════════════════════════╗
║    COMO UM TICKET É CLASSIFICADO NO EIXO ATENDIMENTO         ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  ENTRADA: tags[], full_conversation, is_claudinha_assigned,  ║
║           via_channel                                        ║
║                                                              ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ PASSO 1: Evidência de Bot (4 camadas)                    │ ║
║  │   bot_involved = TRUE se qualquer uma:                    │ ║
║  │   • is_claudinha_assigned = TRUE (snapshot)               │ ║
║  │   • tag 'cloudhumans' (WhatsApp bot, 31.8%)              │ ║
║  │   • tag 'transbordo_botweb' (native bot, 2.1%)           │ ║
║  │   • bot se auto-identifica no texto (backup)              │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                         ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ PASSO 2: Tag 'transbordo_botweb'?                       │ ║
║  │   → claudinha=TRUE  → Bot_Resolvido (resolveu em N1)     │ ║
║  │   → claudinha=FALSE → Bot_Escalado (escalação formal)    │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                         ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ PASSO 3: Tag 'cloudhumans' + claudinha=FALSE?           │ ║
║  │   (bot tocou via WhatsApp, humano assumiu)               │ ║
║  │   → Texto: cliente pediu humano? → Escalacao_Solicitada  │ ║
║  │   → Senão → Bot_Escalado (handoff bot→humano)            │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                         ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ PASSO 4: Padrões de escalação no texto?                 │ ║
║  │   ("vou te transferir", "não consigo ajudar")            │ ║
║  │   → SIM → Bot_Escalado                                   │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                         ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ PASSO 5: Cliente pede atendimento humano?               │ ║
║  │   ("quero falar com atendente", "preciso de humano")    │ ║
║  │   → SIM → Escalacao_Solicitada                           │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                         ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ PASSO 6: bot_involved = TRUE (sem escalação)?           │ ║
║  │   (cloudhumans+claudinha=TRUE ou claudinha_only)          │ ║
║  │   → SIM → Bot_Resolvido                                  │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                         ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ PASSO 7: DEFAULT → Humano_Direto                        │ ║
║  │   (sem evidência de bot: web, email, sem tags bot)       │ ║
║  └─────────────────────────────────────────────────────────┘ ║
╚══════════════════════════════════════════════════════════════╝
```

### **Sinais descartados** (falsos positivos):
- ❌ `conv_len >= 200 → bot_involved`: Heurística agressiva, maioria de conversas humanas > 200 chars
- ❌ `via_channel in ['phone', 'voice']`: Não existem na base (100% digital)
- ❌ `sig_human_takes_over`: Detecta saudação humana, não escalação
- ❌ `Bot_Lixo` (conv_len < 200): Apenas 4 tickets em 171K
- ❌ "ClaudIA" genérico no texto (sem contexto): Menção não implica escalação
- ❌ Tags `droz_*` como proxy de bot: 93.5% dos tickets têm droz (infraestrutura), não significa interação real

### **Sinais de texto (backup para tickets sem tags)**

```yaml
BOT_SELF_ID (alta confiança):
  - "sou a claudia" / "sou a claudinha" / "sou a assistente virtual"
  - "sou a ia da capim" / "sou a inteligência artificial"
  - NÃO inclui "claudia" genérico (match com agentes humanas chamadas Claudia)

ESCALATION_PATTERNS_HIGH:
  - "vou te transferir para (um|uma|o|a) (atendente|especialista|analista)"
  - "não consigo (ajudar|resolver|te atender) com (isso|esse caso)"
  - "vou encaminhar (para|pro) time de (suporte|atendimento)"

ESCALATION_PATTERNS_MEDIUM:
  - "transferir|encaminhar|direcionar" + "atendente|especialista|humano"
  - "não posso|não consigo" + contexto de limitação

CLIENT_REQUESTED_HUMAN:
  - "quero falar com (um |uma )?(atendente|humano|pessoa)"
  - "preciso de (um |uma )?(atendente|humano|pessoa real)"
  - "não quero (falar com |)bot"
```

---

## 🏷️ METADATA COMPLEMENTAR (flags derivadas das tags)

> **Version**: 1.0 (2026-02-13) | **Decisões**: 19.26-19.28
> **Princípio**: Estas flags NÃO são eixos taxonômicos — são metadata derivada para filtrar/segmentar análises.

### **`is_proactive`** — Direção do contato (Capim iniciou vs cliente iniciou)

**Motivação**: ~20-35% dos tickets são contatos proativos da Capim — não são "voz do cliente" orgânica. Misturá-los distorce análises de sentiment, NPS e root-cause. A taxa varia no tempo (35% em 2025-H1, ~20% em 2025-Q4/2026-Q1 — tendência de queda no outreach proativo).

**Regra**: `is_proactive = TRUE` quando o ticket contém templates **sabidamente outbound** (lista curada via auditoria de 78K tickets).

```yaml
is_proactive: TRUE when ANY tag matches:

  # ── OUTBOUND HUMANO (droz_ativo dominante, >80%) ──────────
  # Agente CX inicia contato proativamente via WhatsApp template
  outbound_human:
    - template_contrato_validado          # 5184 vol, 100% ativo — "contrato validado"
    - template_promessa_lembrete_botao    # 1130 vol, 100% ativo — lembrete de promessa
    - template_documents_approved_v4      #  779 vol, 100% ativo — "docs aprovados"
    - template_contrato_assinado_v1       #  438 vol, 100% ativo — "contrato assinado"
    - template_regularize_hoje*           #  ~5700 vol, ~100% ativo — ofertas regularização (broadened)
    - template_cxprimeiramensagem         #  232 vol, 89% ativo — primeiro contato CX
    - template_promessa_quebrada_v4       #  243 vol, 91% ativo — "promessa quebrada"
    - template_promessa_quebrada_v2       #  135 vol — versão anterior
    - template_negativacao_concluida      #  173 vol, 100% ativo — negativação feita
    - template_campanha_desconto          #  137 vol, 100% ativo — campanha desconto
    - template_campanha_desconto_padrao   #   54 vol — variante
    - template_contract_canceled_v3       #  107 vol, 100% ativo — "contrato cancelado"
    - template_treinamento_maquininha_v1  #   74 vol, 100% ativo — treinamento POS
    - template_lembrete_promessa_no_dia   #   58 vol, 100% ativo — lembrete dia
    - template_cxloss                     #   18 vol, 83% ativo — retenção
    - template_documents_rejected_v4      #   17 vol, 100% ativo — "docs rejeitados"
    - template_aniversariantes_do_mes     #   27 vol, 100% ativo — aniversariantes
    # ── Campanhas outbound (adicionadas 2026-02-13 audit) ──
    - template_campanha_entrada_reduzida_pix  # 140 vol — campanha entrada reduzida
    - template_campanha_entrada_reduzida_v2   #  20 vol — v2
    - template_quitacao_colchao               # 109 vol — quitação/acordo
    - template_aditamento                     #  18 vol — aditamento contrato
    - template_patient_downpayment_renegotiation  # 30 vol — renegociação paciente
    - template_patient_invoices_renegotiation     # 16 vol — parcelas paciente
    - template_restituicao_ir                     #  6 vol — restituição IR

  # ── SISTEMA AUTOMATIZADO (billing system, 100% grupo_cobranca) ─
  # Mensagens automáticas de cobrança — sem droz, disparadas por sistema
  system_automated:
    - template_cob_*                      # todas as cob_: ~8800 vol
    - template_8_dda                      # DDA 8 dias (76 vol)
    - template_15_dda                     # DDA 15 dias (110 vol)
    - template_22_dda                     # DDA 22 dias (73 vol)
    - template_negativacao                #  267 vol — aviso negativação
    - template_negativacao_rigoroso       #   25 vol — negativação rigorosa
    - template_negativacao_v2             #  272 vol — versão v2
    - template_pague_seu_boleto           #  322 vol — "pague seu boleto"
    - template_atraso_curto               #  371 vol — "atraso curto"
    - template_atraso_curto_v1            #  282 vol — versão v1
    - template_lembrete_vencimento        #  311 vol — lembrete vencimento
    - template_lembrete_vencimento_v3     #  306 vol — versão v3
    - template_lembrete_vencimento_v4     #   53 vol — versão v4
    - template_assinatura_pendente        #  216 vol — assinatura pendente
    - template_cob_assinatura_pendente    #  140 vol — cob assinatura pendente

is_proactive: FALSE (NÃO incluir — templates de RESPOSTA):
  # Estes templates são usados por agentes em conversas REATIVAS
  # (>60% droz_receptivo) — auditoria comprovou falso-positivo
  response_templates:
    - template_cxsolicitandocontato       # 3679 vol, 66% RECEPTIVO
    - template_saas_inadimplentes_v1      #  916 vol, 96% RECEPTIVO
    - template_saas_inadimplentes_fup_v1  #  488 vol, 90% RECEPTIVO
    - template_boasvindas_cx_poscs        #  483 vol, 94% RECEPTIVO
    - template_boasvindas_cx              #  268 vol, 77% RECEPTIVO
    - template_maquininha_em_transito*    #   ~36 vol, 100% RECEPTIVO
    - template_cx_onboarding_dia0_v2      #   24 vol, 71% RECEPTIVO
    - template_cx_onboarding_dia1_v01     #   14 vol, 79% RECEPTIVO
```

**NÃO usar como sinal**: `droz_ativo` (30.6%→3.0%, tag morrendo) nem `template_*` genérico (16.6% falso-positivo).

**Cobertura estimada**: ~52.500 tickets proativos na base total (30.5% histórico). Tendência de queda: 35%→20% entre 2025-H1 e 2026-Q1. Whitelist expandida em 2026-02-13 (versioned successors + DDA fix + campanhas).

### **`has_interaction`** — Houve conversa real?

**Motivação**: ~13.4% dos tickets têm tag `sem_interacao` — o ticket foi aberto mas não houve conversa real. Classificação LLM tem baixa confiança sem conversa. 69% têm sentiment neutro (3).

**Regra**:
```yaml
has_interaction: FALSE when:
  - tag 'sem_interacao' presente
  
has_interaction: TRUE (default)
  - ausência da tag 'sem_interacao'
```

**Estabilidade**: Tag presente em 7-14% dos tickets (variável mas presente em todos os 7 meses). Aceitável como sinal.

**Uso**:
- Filtrar de análises de sentiment (sentiment pouco significativo sem conversa)
- Medir taxa de resposta de outreach proativo (`is_proactive = TRUE AND has_interaction = FALSE` → outreach sem resposta)
- NÃO excluir de contagens de volume (são tickets reais)

---

## 🔄 Pipeline de Classificação Completo

```
┌─────────────────────────────────────────────────────────────────┐
│                     INCOMING TICKET                             │
│                  (Zendesk raw + conversation)                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              STAGE 1: Deterministic Pre-Triage                  │
│  ─────────────────────────────────────────────────────────────  │
│  • Produto: tags → 80% coverage                                 │
│  • Atendimento: tags + texto (escalation signals) → 70% coverage│
│  • Natureza: high-confidence rules → 30% coverage               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│          STAGE 2: LLM Semantic Extraction (Unified)             │
│  ─────────────────────────────────────────────────────────────  │
│  • Model: Claude Haiku 4.5                                      │
│  • Prompt: 5-layer compiler (L0-L4)                             │
│    - L0: Base task                                              │
│    - L1: Ontology (BNPL/SaaS/Onboarding/POS)                    │
│    - L2: Metadata (via_channel, tags, is_claudinha_assigned)    │
│    - L3: Disambiguation rules (contextual)                      │
│    - L4: Examples (few-shot, stratified by product)             │
│  • Output:                                                      │
│    - product_area (L1 + L2)                                     │
│    - root_cause (Natureza, 19 valores v3.2)                       │
│    - sentiment (1-5)                                            │
│    - key_themes (array)                                         │
│    - conversation_summary (150 chars)                           │
│    - llm_confidence (0.0-1.0)                                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              STAGE 3: Post-Processing & Validation              │
│  ─────────────────────────────────────────────────────────────  │
│  • Override low-confidence (<0.75) → "Indeterminado"/"Unclear"  │
│  • Apply leak fixes (tag-based recovery)                        │
│  • Validate axioms (HARD constraints)                           │
│  • Enrich with metadata (clinic_id, patient_cpf, event_date)    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                 OUTPUT: ticket_insights                         │
│  ─────────────────────────────────────────────────────────────  │
│  • Produto (L1 + L2)                                            │
│  • Natureza (19 valores v3.2)                                   │
│  • Atendimento (4 valores)                                      │
│  • is_proactive (flag: outbound vs inbound)                     │
│  • has_interaction (flag: conversa real vs sem_interacao)        │
│  • Sentiment, themes, summary, confidence                       │
│  • via_channel (metadata: WhatsApp, email, widget, etc.)        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📐 Regras de Interpretação

### **1. Ortogonalidade**

Os 3 eixos são **independentes**. Não assuma correlação:

❌ **Errado**: "Se é Bot_Resolvido, então deve ser Operational_Question"  
✅ **Correto**: Bot pode resolver issues críticos (ex: Cobranca_Ativa via bot)

❌ **Errado**: "Se é Onboarding, então deve ser Credenciamento"  
✅ **Correto**: Onboarding pode ter Simulacao_Credito, Technical_Issue, etc.

### **2. Granularidade**

**Produto**: 
- Use L1 para análises macro (BNPL vs SaaS)
- Use L2 para drill-down (SaaS.Clinico vs SaaS.Conta)

**Natureza**:
- 19 valores v3.2 (justificados empiricamente, golden set + auditoria BNPL)
- Prefira agrupar logicamente (Process_Generico) vs criar novo valor

**Atendimento**:
- 4 valores são suficientes
- "Bot_Resolvido" ≠ "ticket fácil" (pode ser complexo mas bot conseguiu)
- `via_channel` (WhatsApp, email) é metadata complementar, não eixo taxonômico

### **3. Queries Cross-Dimensionais**

**Exemplo 1**: "Tickets de credenciamento que o bot escalou"
```sql
SELECT * 
FROM ticket_insights
WHERE root_cause = 'Credenciamento'
  AND service_type = 'Bot_Escalado'
```

**Exemplo 2**: "Problemas técnicos em SaaS clínico atendidos por humano"
```sql
SELECT * 
FROM ticket_insights
WHERE product_area = 'SaaS'
  AND product_area_l2 = 'Clinico'
  AND root_cause = 'Technical_Issue'
  AND service_type IN ('Humano_Direto', 'Escalacao_Solicitada')
```

**Exemplo 3**: "Financial inquiries resolvidos por bot (alta eficiência)"
```sql
SELECT * 
FROM ticket_insights
WHERE root_cause = 'Financial_Inquiry'
  AND service_type = 'Bot_Resolvido'
  AND sentiment >= 4.0
```

### **4. Coverage Targets**

| Eixo | Categoria "Indeterminado" | Target |
|:---|:---|:---:|
| Produto | `Indeterminado` | < 12% |
| Natureza | `Unclear` | < 15% |
| Atendimento | *(não tem indeterminado - fallback = Humano_Direto)* | N/A |

**Estratégia de melhoria**:
- **Produto**: Leak fixes (tags não mapeadas) → target <10%
- **Natureza**: Refinar Prompt Compiler L3/L4 com 19 valores v3.2 → target <12%

---

## 📊 Exemplos Práticos

### **Exemplo 1: Ticket de Cobrança via Bot**

```yaml
Ticket ID: 123456
Conversa: "Olá! Meu boleto venceu, posso renegociar? [ClaudIA] Sim, aqui está..."
Tags: [cob_contato, faixa_31_60]

Classificação:
  product_area: BNPL
  product_area_l2: Cobranca
  root_cause: Cobranca_Ativa
  service_type: Bot_Resolvido
  via_channel: web
  sentiment: 3.5
  key_themes: [renegociacao, boleto, pagamento]
  llm_confidence: 0.89
```

**Interpretação**: Cliente BNPL em soft delinquency, bot conseguiu renegociar. Autoatendimento eficaz.

---

### **Exemplo 2: Credenciamento com Problema Técnico**

```yaml
Ticket ID: 789012
Conversa: "Clínica em credenciamento, sistema travou no upload de documentos"
Tags: [venda_si_sp, credenciamento, bug_upload]

Classificação:
  product_area: Onboarding
  product_area_l2: Credenciamento
  root_cause: Technical_Issue
  service_type: Humano_Direto
  via_channel: email
  sentiment: 2.0
  key_themes: [credenciamento, documento, bug, upload]
  llm_confidence: 0.92
```

**Interpretação**: Onboarding atrasado por bug técnico. Combina Produto (Onboarding) + Natureza (Technical_Issue). **NÃO** é "Credenciamento" na natureza (apesar de estar em onboarding), pois a natureza é o **bug**, não o processo.

---

### **Exemplo 3: Paciente Consultando Parcelas (Transacional)**

```yaml
Ticket ID: 345678
Conversa: "Paciente quer saber quantas parcelas faltam do tratamento"
Tags: [bnpl_servicing]

Classificação:
  product_area: BNPL
  product_area_l2: Servicing
  root_cause: Financial_Inquiry
  service_type: Humano_Direto
  via_channel: chat
  sentiment: 5.0
  key_themes: [contrato, parcela, paciente]
  llm_confidence: 0.94
```

**Interpretação**: Consulta informativa (não é issue). Sentiment alto. **NÃO** é "Cobranca_Ativa" (paciente não está em débito).

---

### **Exemplo 4: Migração de Dados com Escalação de Bot**

```yaml
Ticket ID: 901234
Conversa: "Clínica migrando, bot tentou ajudar mas escalou: 'vou te transferir para especialista'"
Tags: [migracao, saas]
is_claudinha_assigned: TRUE (no snapshot, depois mudou)

Classificação:
  product_area: SaaS
  product_area_l2: Lifecycle
  root_cause: Migracao
  service_type: Bot_Escalado
  via_channel: web
  sentiment: 2.8
  key_themes: [migracao, configuracao, agenda]
  llm_confidence: 0.87
```

**Interpretação**: Evento de risco (migração), bot reconheceu limite e escalou. **NÃO** é "Humano_Direto" (bot participou antes de escalar). Canal físico (web) é metadata complementar.

---

## 🔍 Validação & Quality Assurance

### **Métricas de Saúde**

```sql
-- Coverage por eixo
SELECT 
  'Produto' as eixo,
  COUNT(*) FILTER(WHERE product_area = 'Indeterminado') as indeterminado,
  COUNT(*) as total,
  ROUND(100.0 * COUNT(*) FILTER(WHERE product_area = 'Indeterminado') / COUNT(*), 1) as pct
FROM ticket_insights

UNION ALL

SELECT 
  'Natureza' as eixo,
  COUNT(*) FILTER(WHERE root_cause = 'Unclear') as indeterminado,
  COUNT(*) as total,
  ROUND(100.0 * COUNT(*) FILTER(WHERE root_cause = 'Unclear') / COUNT(*), 1) as pct
FROM ticket_insights;
```

### **Confiança LLM**

```sql
-- Distribuição de confiança por natureza
SELECT 
  root_cause,
  COUNT(*) as cnt,
  ROUND(AVG(llm_confidence)::numeric, 3) as avg_conf,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY llm_confidence)::numeric, 3) as p50_conf
FROM ticket_insights
WHERE root_cause != 'Unclear'
GROUP BY 1
ORDER BY 3 DESC;
```

### **Matriz de Transição** (before → after)

```sql
-- Validar drift pós-reprocessamento
SELECT 
  old_product_area as before,
  new_product_area as after,
  COUNT(*) as cnt,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) as pct
FROM ticket_transitions
GROUP BY 1, 2
ORDER BY 3 DESC
LIMIT 20;
```

---

## 🚀 Próximos Passos

### **Fase 1: Implementação Técnica** (Sprint 1-2)

1. ✅ **Taxonomia sacramentada** (2026-02-12)
2. ⏳ **Atualizar Prompt Compiler** (L2/L3/L4)
   - Adicionar novos valores de natureza
   - Refinar regras de desambiguação
3. ⏳ **Criar regras determinísticas** (Stage 1)
   - `Credenciamento`, `Migracao`, `Financial_Inquiry`, `Endosso_Repasse`
4. ⏳ **Reprocessar Phase 3** (24.6K tickets, 3 meses)
   - Validar nova taxonomia em subset
5. ⏳ **Validação empírica**
   - Coverage, confidence, sentiment distribution
   - Matriz de transição (before → after)

### **Fase 2: Backfill Histórico** (Sprint 3-4)

6. ⏳ **Backfill 430K tickets** (histórico completo)
   - Após validação bem-sucedida da Phase 3
7. ⏳ **Criar views finais**
   - `TICKET_INSIGHTS_V4` (nova taxonomia)
   - Deprecar `TICKET_ANALYSIS_V3` (legacy)

### **Fase 3: Integração & Documentação** (Sprint 5)

8. ⏳ **Atualizar dashboards** (Streamlit app)
   - Novos filtros (Produto L1/L2, Natureza 19 valores v3.2, Atendimento 4 valores, is_proactive, has_interaction)
   - Filtro adicional: via_channel (WhatsApp, email, widget)
9. ⏳ **Documentação stakeholders**
   - User-friendly naming guide
   - Query examples cookbook
10. ⏳ **n8n agents** (especialização por produto)
    - SAAS agent, POS agent, FINTECH agent
    - Guardrails e prompts específicos

---

## 📚 Referências

- **Decisões**: `_memory/DECISIONS_IN_PROGRESS.md` (19.11-19.17, 19.22-19.29)
- **Scripts de validação empírica**:
  - `scripts/analysis/diagnose_bot_escalation_deep.py`
  - `scripts/analysis/diagnose_product_axis.py`
  - `scripts/analysis/diagnose_nature_subcategories.py`
  - `scripts/analysis/diagnose_financial_operations.py`
- **Taxonomias anteriores** (legacy):
  - `CATEGORY_TAXONOMY.md` (intent-based, LLM Stage 2, 36% coverage) — DEPRECATED
  - `PRODUCT_TAXONOMY.md` (deterministic, tags-based) — MANTIDO, agora L1/L2
- **Prompt Compiler**: `scripts/prompt_compiler.py`
- **Axiomas**: `_domain/START_HERE.md` (data quality rules)

---

## 📝 Changelog

- **2026-02-13 (v3.2)**: **CONTRATACAO SPLIT + venda_* → BNPL**: Deep dive em tags `venda_*` revelou que 100% são relacionados à venda BNPL (clínica ajudando paciente fechar financiamento), NÃO venda de SaaS. `Contratacao` split em 2 Naturezas: `Contratacao_Acompanhamento` (follow-up genérico: `venda_si_suporte`, `venda_apenas_acompanhamento`, `venda_sem_suporte`) + `Contratacao_Suporte_Paciente` (fricção: `venda_si_telefone`, `venda_si_docs`, `venda_si_assinatura`, `venda_si_sms`). `venda_dificuldade_na_assinatura` absorvido por `Technical_Issue`. Correção produto: tags `venda_*` movidas de Onboarding para BNPL em `PRODUTO_TAG_RULES` e `PRODUTO_L2_RULES`. `EXPECTED_PRODUCT_FOR_ROOT_CAUSE`: ambas novas Naturezas → `'BNPL'` (não dual-affinity). Net: 18 → 19 Naturezas. Funil BNPL agora tem 5 etapas (C1 → C2 follow-up → C2 fricção → C2→C2S → Post-C2S).
- **2026-02-13 (v3.1.1)**: **GOLDEN SET AUDIT FIXES**: Credenciamento reclassificado de Onboarding→BNPL/POS (43%/33% no Golden Set N=1000). Contratacao reclassificada de BNPL→Onboarding/BNPL (88.6% Onboarding) — **SUPERADO em v3.2 com Contratacao split**. Whitelist `is_proactive` expandida: +7 campanhas outbound, +5 versioned successors system, +3 DDA explícitos, prefix broadened (`template_regularize_hoje`). Bug fix: DDA templates (`template_N_dda`) não matchavam prefix `template_dda_`. `validate_semantic_consistency` agora suporta multi-product (list). Tendência proactive rate documentada: 35%→20% (2025-H1→2026-Q1).
- **2026-02-13 (v3.1)**: **TAG RELIABILITY + METADATA**: Auditoria de confiabilidade em 78K tickets (6 meses). Expansão Tier 1 com tags `n2_*` (25 tags estáveis 7/7 meses). `saas_login` rebaixado de HIGH → MEDIUM (trust 53.3%). Adição de `is_proactive` (lista curada 18+ templates outbound, ~30% da base) e `has_interaction` (NOT `sem_interacao`, ~13%). `droz_ativo` descartado como sinal (30.6%→3.0%, morrendo). `template_*` genérico descartado (16.6% falso-positivo como proativo). Decisões 19.26-19.29.
- **2026-02-13 (v3.0)**: **NATUREZA REDESIGN**: Reconciliação empírica (golden set N=1000 + tags Zendesk). `debt_collection` split em 4 etapas funil BNPL (Simulacao_Credito, Contratacao, Endosso_Repasse, Cobranca_Ativa). `financial_operations` morto (absorvido). `Credit_Issue` renomeado `Simulacao_Credito`. Novos: Carne_Capim, Alteracao_Cadastral, Acesso. Total: 15→18 valores. Decisões 19.22-19.24.
- **2026-02-13 (v2.4)**: **CRITICAL FIX**: Removida dependência circular entre Produto e Natureza. `ROOT_CAUSE_PRODUCT_MAP` e `ROOT_CAUSE_L2_FALLBACK` eliminados. Produto agora é 100% determinístico (tags/themes only). `root_cause` (LLM output) não é mais usado como fallback para classificar Produto. Adicionada validação post-hoc para detectar conflitos semânticos (não auto-corrigir). Target: aceitar < 12% Indeterminado como válido, melhorar via tag enrichment.
- **2026-02-13 (v2.3)**: Eixo Atendimento redesenhado. Descoberta empírica: tags `cloudhumans` (31.8%, WhatsApp bot) e `transbordo_botweb` (2.1%, native bot) são sinais de alta confiança para bot involvement. `is_claudinha_assigned` é snapshot (não histórico) — sozinho perde 76.9% dos tickets bot-touched. Nova lógica com 4 camadas de evidência. `Humano_Direto` restaurado (60.5% sem evidência de bot). `conv_len` removido como proxy de bot.
- **2026-02-13 (v2.2)**: Produto L2 expandido para Onboarding e POS. `ROOT_CAUSE_L2_FALLBACK` introduzido. Cobertura L2 de 43.5% para 78.2%.
- **2026-02-12 (v2.1)**: Renomeação "Canal" → "Atendimento" para evitar ambiguidade com `via_channel` (meio físico). Clarificação: Atendimento = tipo de handling (bot/humano), via_channel = meio físico (WhatsApp/email/widget).
- **2026-02-12 (v2.0)**: Redesign completo. 3 eixos ortogonais (Produto × Natureza × Atendimento). 15 valores de natureza. Substituição de Stage 2 workflow.
- **2026-02-10 (v1.0)**: Legacy taxonomy (intent-based CATEGORY_TAXONOMY + Stage 2 workflow).
