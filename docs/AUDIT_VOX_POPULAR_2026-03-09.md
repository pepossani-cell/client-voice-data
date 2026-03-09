# Auditoria Vox Popular

> **Data**: 2026-03-09  
> **Escopo**: `vox_popular.ticket_insights` no histórico completo e no recorte operacional de 90 dias  
> **Objetivo**: validar coerência entre base, taxonomia, documentação e consumo do app `client-voice`

---

## Resumo Executivo

A auditoria confirma que o **contrato canônico atual** do `vox_popular.ticket_insights` está funcional para os tickets processados: `product_area` e `service_type` estão alinhados com `product_area_l1` e `atendimento_type`, o eixo `root_cause` está 100% canônico nos tickets com `processing_phase IS NOT NULL`, e os targets principais de cobertura estão dentro do esperado.

Os principais riscos hoje não estão no miolo da taxonomia processada, mas em quatro frentes:

1. **Backlog relevante fora do contrato canônico**: 31.649 tickets ainda estão com `processing_phase IS NULL`, e 30.787 deles parecem elegíveis para processamento.
2. **Drift documental e contratual**: app e docs ainda misturam conceitos legacy e canônicos, o que aumenta o risco de leitura errada por humanos e futuros agentes.
3. **Constraint e resíduos legacy ainda aceitos no banco**: o `CHECK` de `root_cause` continua aceitando valores antigos, e os únicos `root_cause` não canônicos encontrados estão justamente no universo não processado.
4. **Leitura analítica parcial no app**: a taxonomia já prevê `is_proactive` e `has_interaction` como filtros críticos para leitura de sentimento/VoC, mas o app não os incorpora nas consultas principais.

---

## Fontes e Método

Esta auditoria se apoiou em quatro camadas:

- Contrato do domínio em `client-voice-data/_domain/START_HERE.md`
- Especificação semântica em `client-voice-data/_domain/_docs/TAXONOMY_3_AXES.md`
- Docs técnicas e semânticas de `ticket_insights`
- Consumo real do app em `client-voice/data/tickets.py` e `client-voice/data/sampling.py`

Também foi executada a auditoria empírica do banco via:

```bash
python -X utf8 scripts/audit_ticket_insights_vox_popular.py --top-n 20
```

---

## Arquitetura Real vs Documentada

### Arquitetura real observada

O app atualmente publicado em [streamlit.clientvoice.capim.tech](https://streamlit.clientvoice.capim.tech/) e o código em `client-voice/app.py` apontam para este desenho:

- **runtime principal**: Streamlit multipágina
- **fonte principal de dados**: PostgreSQL / `vox_popular.ticket_insights`
- **páginas principais**: `Início`, `Categorias`, `Explorador`, `Assistente`
- **drill-downs**: `perfil-tema` e `perfil-clinica`
- **Snowflake**: capacidade auxiliar e opcional no Assistente, não base do app

### Onde estava o drift

Antes desta rodada, parte da documentação do app ainda descrevia:

- `TICKET_ANALYSIS_V3` como principal tabela enriquecida
- Snowflake como conexão principal
- uma estrutura de páginas antiga com arquivos numerados

O `client-voice/START_HERE.md` foi **alinhado nesta rodada** para refletir a arquitetura real atual. O risco remanescente está concentrado em outros artefatos legados listados abaixo.

### Inventário original de arquivos que falavam a linguagem do desenho antigo

- `client-voice/docs/STREAMLIT_README.md` -> removido da superfície principal na quarta rodada
- `client-voice/docs/queries_workflow_v3.md` -> removido da superfície principal na quarta rodada
- `client-voice/docs/arquitetura_multi_agente.md` -> removido da superfície principal na quarta rodada
- `client-voice/reflex_app/README.md` -> mantido, mas explicitamente enquadrado como trilha experimental

Observação: nem todo arquivo com referência a Snowflake está “errado”. Em especial, `client-voice/pages/assistente.py`, `client-voice/ai/assistant.py` e `client-voice/data/snowflake_connection.py` continuam coerentes com o desenho atual porque tratam Snowflake como **fonte opcional para queries ad hoc no Assistente**, não como backbone do app.

---

## Contrato Canônico Confirmado

O contrato operacional confirmado hoje é:

- **Fonte de verdade**: `vox_popular.ticket_insights`
- **Marcador canônico de processamento**: `processing_phase IS NOT NULL`
- **Produto L1 canônico**: `product_area`
- **Produto L2 canônico**: `product_area_l2`
- **Natureza canônica**: `root_cause`
- **Atendimento canônico**: `service_type`
- **Flags complementares críticas**: `is_proactive`, `has_interaction`

O app já resolve o filtro de reprocessados para `processing_phase IS NOT NULL` quando a coluna existe:

```101:131:c:\Users\pedro.possani_capim\client-voice\data\tickets.py
def _reprocessed_filter(only_recent: bool = False) -> str:
    """
    Filtro global: só exibir tickets reprocessados (Phase 3).
    
    Quando only_recent=False:
      - Usa llm_processed_at IS NOT NULL (todos os reprocessados)
      - Fallback: customer_effort_score IS NOT NULL
    """
    if only_recent:
        if schema_has_column(TABLE_TICKET_INSIGHTS, "processing_phase"):
            return "AND processing_phase = 'phase_3.1_golden'"
    if schema_has_column(TABLE_TICKET_INSIGHTS, "processing_phase"):
        return "AND processing_phase IS NOT NULL"
    if schema_has_column(TABLE_TICKET_INSIGHTS, "llm_processed_at"):
        return "AND llm_processed_at IS NOT NULL"
```

O ponto importante aqui é que **o código está mais correto que a docstring**: o comportamento real prioriza `processing_phase`, mas o comentário ainda sugere `llm_processed_at` como padrão.

---

## Achados Confirmados

### 1. Backlog material fora do contrato canônico

- Total de tickets: **171.916**
- Tickets processados (`processing_phase IS NOT NULL`): **140.267 (81,6%)**
- Tickets não processados (`processing_phase IS NULL`): **31.649 (18,4%)**
- Backlog elegível (`full_conversation` preenchida e com tamanho > 100): **30.787**

Leitura: a base canônica está boa **onde já houve processamento**, mas ainda existe um universo grande que pode contaminar leituras se alguma consulta sair do recorte correto.

### 2. O contrato processado está semanticamente consistente

Nos tickets processados:

- `product_area_l1` preenchido em **100%**
- `atendimento_type` preenchido em **100%**
- Mismatches `product_area_l1 <> product_area`: **0**
- Mismatches `atendimento_type <> service_type`: **0**
- `root_cause` canônico v3.2: **100%**

Também houve consistência perfeita nos root causes exclusivos por produto:

- Root causes exclusivos de BNPL classificados como `BNPL`: **100%**
- Root causes exclusivos de SaaS classificados como `SaaS`: **100%**

### 3. Os targets centrais da taxonomia estão dentro da meta

No universo processado:

- `product_area = 'Indeterminado'`: **11.332 / 140.267 = 8,1%**
- `root_cause = 'Unclear'`: **9.971 / 140.267 = 7,1%**

Isso está abaixo dos targets definidos na taxonomia:

- Produto indeterminado: `< 12%`
- Natureza unclear: `< 15%`

### 4. O `CHECK` de `root_cause` ainda aceita valores legacy

A auditoria do banco mostrou que o constraint `check_root_cause_values` já contém os valores v3.2, mas **continua aceitando valores antigos**, incluindo:

- `unclear`
- `not_applicable`
- `debt_collection`
- `Contratacao`

Os resíduos não canônicos encontrados ficaram concentrados no universo **não processado**:

- `unclear`: **362**
- `not_applicable`: **77**
- `debt_collection`: **8**

Leitura: o contrato canônico está limpo nos processados, mas o banco ainda aceita semântica antiga. Isso aumenta o risco de regressão silenciosa em pipelines futuros.

### 5. Existe drift documental forte entre app, docs técnicas e docs semânticas

O drift documental foi confirmado em múltiplos artefatos. Desde a primeira versão desta auditoria, parte dele já foi saneado:

- `client-voice/START_HERE.md` foi alinhado à arquitetura real do app
- `client-voice-data/docs/reference/TICKET_INSIGHTS.md` foi alinhado ao schema/taxonomia atuais
- `client-voice-data/_domain/_docs/reference/TICKET_INSIGHTS_SEMANTIC.md` foi alinhado ao estado real das colunas canônicas e flags complementares
- `client-voice-data/_domain/START_HERE.md` foi alinhado ao pairing real com `client-voice/`
- `client-voice-data/_domain/_docs/TAXONOMY_3_AXES.md` foi normalizado para Natureza v3.2 com 19 valores
- `client-voice-data/_domain/_docs/TAXONOMY_MIGRATION_GUIDE.md` passou a carregar framing explícito de documento histórico, não contrato vigente

O problema remanescente agora persiste sobretudo em documentação técnica e histórica adjacente, não mais nesses três arquivos centrais.

Os blocos abaixo são mantidos como **snapshot do drift observado durante a auditoria**, antes da remediação desta segunda rodada:

Além disso, a doc técnica de `ticket_insights` descrevia `root_cause` como eixo com **15 valores canônicos** e exemplos legacy:

```24:43:c:\Users\pedro.possani_capim\client-voice-data\docs\reference\TICKET_INSIGHTS.md
| `via_channel` | `varchar` | YES | - | Entry channel: `whatsapp` (78.8%), `native_messaging` (14.9%), `web` (3.9%), `email` (2.3%), `api` (0.1%) |
| **`product_area`** | `varchar` | YES | - | **Eixo 1 L1**: `BNPL`, `SaaS`, `Onboarding`, `POS`, `Indeterminado` (Stage 1 legacy values also present) |
| **`product_area_l2`** | `varchar` | YES | - | **Eixo 1 L2**: 12 subcategorias (ex: `Cobranca`, `Clinico`, `Credenciamento`, `Operacao`) |
| **`workflow_type`** | `varchar` | YES | - | **LEGACY Stage 2** (`Suporte_L2`, `Info_L1`, etc.) — replaced by `root_cause` + `service_type` |
| **`root_cause`** | `varchar` | YES | - | **Eixo 2 (Natureza)**: 15 valores canônicos (CHECK constraint). Ex: `debt_collection`, `technical_issue`, `subscription_issue` |
| **`service_type`** | `varchar` | YES | - | **Eixo 3 (Atendimento)**: `Bot_Escalado`, `Bot_Resolvido`, `Escalacao_Solicitada`, `Humano_Direto` |
| **`llm_model`** | `varchar` | YES | - | Model used for LLM extraction (ex: `claude-haiku-4-5`) |
```

Enquanto isso, a doc semântica já falava em **19 valores v3.2**, mas marcava flags já existentes como “planned”:

```150:155:c:\Users\pedro.possani_capim\client-voice-data\_domain\_docs\reference\TICKET_INSIGHTS_SEMANTIC.md
### 3.3. Classification (3-Axis Taxonomy)

> **⚠️ SCHEMA PARTIALLY MIGRATED**: `root_cause`, `product_area_l2`, `service_type` are ✅ Active (§9).  
> Legacy columns (`product_area`, `workflow_type`) still exist for backwards compatibility.  
> **Pending**: `product_area_l1`, `via_channel`, `is_proactive`, `has_interaction` (⏳ Planned).  
```

Na prática, a auditoria do banco mostrou que `via_channel`, `is_proactive` e `has_interaction` **já existem e estão preenchidos nos tickets processados**.

### 6. O app consome o núcleo da taxonomia, mas ignora flags essenciais para leitura de VoC

As queries principais do app trabalham com `product_area`, `product_area_l2`, `root_cause`, `service_type` e `sentiment`, mas não usam `is_proactive` nem `has_interaction`:

```565:623:c:\Users\pedro.possani_capim\client-voice\data\tickets.py
def get_category_map(
    days: int = 90,
    product_areas: Optional[list[str]] = None,
    product_areas_l2: Optional[list[str]] = None,
    root_causes: Optional[list[str]] = None,
    atendimento_types: Optional[list[str]] = None,
    sentiment_range: Optional[tuple[float, float]] = None,
) -> pd.DataFrame:
    """
    Dados para treemap: product_area × root_cause com volume e sentimento.
    Só tickets reprocessados. Suporta filtros opcionais.
    """
    ...
    if root_causes:
        filters.append(f"root_cause IN ({rc_list})")
    if atendimento_types and has_atend:
        filters.append(f"service_type IN ({at_list})")
    if sentiment_range:
        filters.append(f"sentiment BETWEEN {sentiment_range[0]} AND {sentiment_range[1]}")
```

Isso conflita com a própria taxonomia, que documenta explicitamente que essas flags devem filtrar análises de sentimento:

```629:633:c:\Users\pedro.possani_capim\client-voice-data\_domain\_docs\TAXONOMY_3_AXES.md
### **`is_proactive`** — Direção do contato (Capim iniciou vs cliente iniciou)

**Motivação**: ~20-35% dos tickets são contatos proativos da Capim — não são "voz do cliente" orgânica. Misturá-los distorce análises de sentiment, NPS e root-cause.
```

```704:722:c:\Users\pedro.possani_capim\client-voice-data\_domain\_docs\TAXONOMY_3_AXES.md
### **`has_interaction`** — Houve conversa real?

**Motivação**: ~13.4% dos tickets têm tag `sem_interacao` — o ticket foi aberto mas não houve conversa real. Classificação LLM tem baixa confiança sem conversa.

**Uso**:
- Filtrar de análises de sentiment
- Medir taxa de resposta de outreach proativo
- NÃO excluir de contagens de volume
```

Cobertura observada nos tickets processados:

- `is_proactive = TRUE`: **46.825 / 140.267 = 33,4%**
- `has_interaction = FALSE`: **19.441 / 140.267 = 13,9%**

Leitura: o app está correto para volume temático básico, mas **subótimo para leitura de “voz do cliente orgânica”**.

### 7. Há risco residual se alguém voltar a usar `llm_processed_at` como marcador de reprocessamento

No recorte de 90 dias:

- `llm_processed_at IS NOT NULL`: **21.989**
- `processing_phase IS NOT NULL`: **21.700**
- Diferença: **289 tickets (1,3%)**

No histórico completo:

- `llm_processed_at IS NOT NULL`: **140.714**
- `processing_phase IS NOT NULL`: **140.267**
- Diferença: **447 tickets (0,3%)**

Como o runtime do app hoje resolve para `processing_phase`, isso não parece ser um problema operacional corrente. Mas o fallback/documentação ainda deixa espaço para reintroduzir uma população levemente mais larga e menos confiável.

### 8. A modelagem de atendimento está estável, mas um downstream ainda usa proxy envelhecido

A classificação de atendimento ficou fortemente aderente aos sinais empíricos:

- Linhas com forte expectativa de fluxo bot: **58.009**
- `service_type` alinhado ao esperado: **97,2%**

Ao mesmo tempo, a auditoria do banco indicou que a view `ticket_insights_enriched_v1` ainda contém `droz_` na definição de `is_bot_flow`.

Isso merece atenção porque o mesmo estudo mostrou forte drift temporal em `droz_ativo`:

- 2025-02: **46,9%**
- 2025-06: **50,6%**
- 2025-12: **4,5%**
- 2026-02: **2,8%**

Enquanto isso:

- `cloudhumans`: **31,8%** da base
- `transbordo_botweb`: **2,1%**
- `is_claudinha_assigned`: **16,7%**
- `bot_touched_any`: **39,5%**

Leitura: `service_type` está bom; o risco está mais em algum consumidor secundário reaproveitar proxy `droz_*` fora da taxonomia atual.

---

## O que está saudável hoje

- O recorte operacional de 90 dias baseado em `processing_phase` está consistente com o contrato canônico.
- Os tickets processados estão semanticamente limpos em `root_cause`.
- O sync entre colunas canônicas e colunas app-facing está efetivo no universo processado.
- O eixo de atendimento está empiricamente forte.
- Os targets principais de `Indeterminado` e `Unclear` estão dentro da meta.

---

## Riscos Prioritários

### Risco imediato

1. **Exposição analítica enviesada no app** por ausência de `is_proactive` e `has_interaction` nos cortes de sentimento e VoC.
2. **Confusão operacional/humana** por documentação conflitante entre app, dicionário técnico e docs semânticas.

### Risco estrutural

1. **Regressão semântica** se pipelines voltarem a escrever ou aceitar valores legacy de `root_cause`.
2. **Backlog acumulado** fora do universo canônico, com potencial de contaminar análises se consultas escaparem do filtro correto.
3. **Downstreams antigos** usando proxies `droz_*` ou artefatos legacy.

---

## Recomendações Priorizadas

### P0

1. Convergir toda a documentação remanescente do app para `vox_popular.ticket_insights` como fonte primária.
2. Corrigir `docs/reference/TICKET_INSIGHTS.md` e `*_SEMANTIC.md` para refletirem o estado real do schema e da taxonomia v3.2.
3. Revisar os pontos do app em que sentimento/VoC são exibidos sem considerar `is_proactive` e `has_interaction`.
4. Sanitizar ou rotular explicitamente como históricos os arquivos legados listados em `Arquitetura Real vs Documentada`.

### P1

1. Endurecer o `CHECK` de `root_cause` para reduzir a superfície legacy assim que o backlog antigo deixar de depender desses valores.
2. Planejar reprocessamento do backlog elegível de 30.787 tickets.
3. Revisar a view `ticket_insights_enriched_v1` para remover dependência implícita de `droz_*` como proxy principal de bot flow.

### P2

1. Formalizar um “contrato de consumo do app” separado do dicionário técnico, deixando claro:
   - população válida
   - filtros obrigatórios por tipo de análise
   - campos canônicos versus compatibilidade
2. Adicionar micro-auditorias recorrentes para:
   - backlog processado vs não processado
   - presença de valores legacy
   - drift de sinais de bot/proatividade

---

## Respostas às Perguntas da Auditoria

### O recorte padrão do app está exibindo a população correta?

**Sim, hoje sim**, porque a lógica de runtime usa `processing_phase IS NOT NULL` quando essa coluna existe.  
**Mas** a docstring e os fallbacks ainda preservam semântica antiga, o que merece limpeza.

### A taxonomia vigente está refletida na base física e nas docs?

**Na base processada, sim. Nas docs, ainda não completamente.** O `START_HERE.md` do app foi alinhado nesta rodada, mas ainda restam artefatos documentais com framing legado.

### Existem colunas/flags importantes previstas e ignoradas pelo app?

**Sim.** `is_proactive` e `has_interaction` já estão materializadas e deveriam influenciar leituras de sentimento/VoC, mas não entram nas queries principais.

### Quais sinais estão envelhecendo?

**Principalmente `droz_ativo` e resíduos legacy de `root_cause`.** O eixo canônico de atendimento parece saudável; o risco está nos legados periféricos.

### Onde está o maior risco de inconsistência para stakeholders?

**No contraste entre uma base relativamente madura e uma camada de documentação/consumo que ainda comunica parte do modelo anterior.**
