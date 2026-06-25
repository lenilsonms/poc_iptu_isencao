# POC IPTU — Isenção de IPTU / Guarulhos

Agente de IA para triagem e minuta de isenção de IPTU. Arquitetura *ports & adapters*: a IA
(Azure OpenAI) lê/classifica/extrai; o **núcleo determinístico** sugere a conclusão; a **minuta**
é montada de forma determinística por configuração. A decisão final é sempre humana.

> **Princípio inegociável:** o LLM não decide. O código determinístico sugere e redige por template; o servidor valida.

## Estado atual — POC demonstrável de ponta a ponta

- ✅ Ajustes **P0** nas configurações (`config/CHANGELOG_P0.md`).
- ✅ **Núcleo determinístico**: confiança, seleção de regime, montagem de checklist e
  resolução de conclusão por tabela de precedência explícita.
- ✅ **Entrada**: `AnalyzeProcessUseCase` + portas + adapter de PDF (PyMuPDF) com OCR seletivo.
- ✅ **LLM real**: adapters **Azure OpenAI** para classificação e extração, com transporte
  injetável (testável offline) e **`prompts.yaml` versionado** (registrado na auditoria).
- ✅ **Minuta**: `DecisionDraftService` (determinístico, `conclusion_mapping.yaml`) com
  ciência/recurso obrigatória, CPF mascarado e rastreabilidade.
- ✅ **UI Streamlit**: upload do PDF → resumo, checklist, conclusão e minuta (com download).
- ✅ **53 testes verdes**, incluindo o pipeline completo pelo caminho Azure (transporte falso).
- ⏳ Próximos: exportação (Markdown/DOCX/JSON); ajuste de prompts com casos reais; pendências P1.

## Como executar

```bash
pip install -e ".[dev]"          # núcleo + PyMuPDF + pytest
pytest                           # 53 testes

# UI de demonstração:
pip install -e ".[ui]"           # streamlit
streamlit run poc_iptu/app/streamlit_app.py
```

### Modo Azure vs. demonstração

A UI e o runner escolhem o modo automaticamente:

```bash
# LLM real (Azure OpenAI):
export AZURE_OPENAI_ENDPOINT="https://<seu-recurso>.openai.azure.com"
export AZURE_OPENAI_API_KEY="<chave>"
export AZURE_OPENAI_DEPLOYMENT="<deployment>"
export AZURE_OPENAI_API_VERSION="2024-08-01-preview"   # opcional
pip install -e ".[llm]"          # openai
# OCR real opcional: export POC_OCR_ENGINE=paddle ; pip install -e ".[ocr]"
```

Sem essas variáveis, roda em **modo demonstração offline** (caso-ouro), deixando isso explícito na UI.

## Fluxo completo

```
PDF → [DocumentReaderPort: PyMuPDF] → páginas (+OCR seletivo via OcrPort)
    → [DocumentClassificationPort: Azure OpenAI] → documentos classificados (restritos à taxonomia)
    → [FieldExtractionPort: Azure OpenAI] → campos (requerente, imóvel, renda, regime)
    → [ChecklistAssembler: determinístico] → checklist ("documento parecido não satisfaz")
    → [ProcessEvaluator: determinístico] → conclusão sugerida
    → [DecisionDraftService: determinístico] → minuta (conclusion_mapping.yaml)
    → ProcessAnalysisResult com draft_text + metadados (inclui prompt_version)
```

O transporte do LLM (`ChatCompletionClient`) é injetável: produção usa `AzureOpenAIChatClient`;
testes usam um cliente falso que devolve JSON canônico. Montagem de checklist, avaliação e
minuta são determinísticas e reais.

## Arquitetura

```
config/                         YAMLs = única fonte da verdade
  ├─ legal_references.yaml       (1.2.0-poc-p0-fixes)
  ├─ business_rules.yaml         (1.2.0-poc-p0-fixes) escopo, confiança, PRECEDÊNCIA
  ├─ checklist_iptu.yaml         (1.0.0, frozen)
  ├─ conclusion_mapping.yaml     textos por estado + seções + ciência/recurso
  ├─ document_taxonomy.yaml      (1.0.0, frozen)
  ├─ prompts.yaml                (1.0.0-poc) prompts de classificação/extração
  └─ CHANGELOG_P0.md

poc_iptu/
  ├─ domain/                    PURO (enums, modelos imutáveis, erros, modelos de minuta)
  ├─ config/                    schemas tipados + loader (valida depends_on entre versões)
  ├─ ports/                     CONTRATOS (reader, ocr, classification, extraction)
  ├─ adapters/
  │   ├─ pymupdf_reader.py        leitura de PDF + OCR seletivo
  │   ├─ ocr/                     NoOp, PaddleOCR (import preguiçoso)
  │   └─ llm/                     AZURE OPENAI + demonstração offline
  │       ├─ chat_client.py        transporte injetável + AzureOpenAIChatClient (lazy)
  │       ├─ prompt_library.py     carrega prompts.yaml (render por tokens)
  │       ├─ azure_classification.py / azure_extraction.py
  │       └─ offline_demo.py        adapters de demonstração (caso-ouro)
  ├─ rules/                     NÚCLEO DETERMINÍSTICO (confiança, regime, checklist, conclusão)
  ├─ drafting/                  minuta determinística + guardrails (sem "DEFIRO", CPF mascarado)
  ├─ application/               AnalyzeProcessUseCase + composition root
  └─ app/                       UI
      ├─ analysis_runner.py        wiring testável (Azure ou demo) — sem Streamlit
      └─ streamlit_app.py          interface de demonstração

examples/minuta_exemplo_SEI_5737.txt   minuta gerada para o caso-ouro
tests/  unit | integration | regression | fakes
```

## Próximos incrementos sugeridos

1. Exportação da minuta (Markdown/DOCX) e da análise (JSON).
2. Ajuste/avaliação dos prompts com processos reais (o `prompts.yaml` já é versionado e auditado).
3. Endereçar as pendências P1 do `CHANGELOG_P0.md`.
