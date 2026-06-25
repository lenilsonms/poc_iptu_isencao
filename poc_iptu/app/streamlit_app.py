"""Interface Streamlit da POC de isenção de IPTU.

Execução:
    pip install -e ".[ui]"            # instala streamlit
    streamlit run poc_iptu/app/streamlit_app.py

Modo de operação:
  - se as variáveis AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_API_KEY / AZURE_OPENAI_DEPLOYMENT
    estiverem definidas, usa o Azure OpenAI real;
  - caso contrário, roda em "modo demonstração" (dados do caso-ouro), deixando isso explícito.

Esta camada é apenas apresentação; toda a lógica vive em poc_iptu.app.analysis_runner.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite executar o arquivo diretamente, mesmo sem instalação editável.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

from poc_iptu.app.analysis_runner import (
    AnalysisMode,
    RunnerContext,
    build_runner,
    run_analysis,
)
from poc_iptu.domain.enums import ChecklistStatus, ConclusionStatus

_STATUS_BADGE = {
    ChecklistStatus.OK: "✅ OK",
    ChecklistStatus.NAO_APRESENTADO: "❌ Não apresentado",
    ChecklistStatus.VERIFICAR: "⚠️ A verificar",
    ChecklistStatus.NAO_APLICAVEL: "➖ Não aplicável",
}

_CONCLUSION_LABEL = {
    ConclusionStatus.INDEFERIMENTO_SUGERIDO: "Indeferimento sugerido",
    ConclusionStatus.APTO_PARA_ANALISE_DE_DEFERIMENTO: "Apto para análise de deferimento",
    ConclusionStatus.VERIFICAR_MANUALMENTE: "Verificação manual necessária",
    ConclusionStatus.FORA_DO_ESCOPO_POC: "Fora do escopo da POC",
}


@st.cache_resource(show_spinner=False)
def _get_runner() -> RunnerContext:
    return build_runner()


def _render_sidebar(context: RunnerContext) -> None:
    with st.sidebar:
        st.header("Configuração")
        if context.mode == AnalysisMode.AZURE:
            st.success("Modo: Azure OpenAI (LLM real)")
        else:
            st.warning("Modo: demonstração offline (caso-ouro)")
            st.caption(
                "Defina AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY e AZURE_OPENAI_DEPLOYMENT "
                "para usar o LLM real."
            )
        st.write(f"**Provedor:** {context.llm_provider}")
        st.write(f"**Modelo:** {context.llm_model}")
        st.write(f"**Prompts:** {context.prompt_version}")
        st.write(f"**OCR:** {context.ocr_engine}")
        st.divider()
        st.caption(
            "A IA não decide. O núcleo determinístico sugere a conclusão; a minuta é revisável "
            "pela autoridade competente."
        )


def _render_conclusion(result) -> None:
    status = result.conclusion.status
    label = _CONCLUSION_LABEL.get(status, status.value)
    text = f"**Conclusão sugerida:** {label}"
    if status == ConclusionStatus.INDEFERIMENTO_SUGERIDO:
        st.error(text)
    elif status == ConclusionStatus.APTO_PARA_ANALISE_DE_DEFERIMENTO:
        st.success(text)
    elif status == ConclusionStatus.VERIFICAR_MANUALMENTE:
        st.warning(text)
    else:
        st.info(text)
    if result.conclusion.legal_basis:
        st.write("**Fundamento normativo:** " + "; ".join(result.conclusion.legal_basis))


def _render_summary(result) -> None:
    st.subheader("Resumo do pedido")
    col1, col2, col3 = st.columns(3)
    col1.metric("Exercício", result.request.requested_year)
    col2.metric("Tipo de pedido", result.request.benefit_type.value)
    col3.metric("Páginas (OCR)", f"{result.total_page_count} ({result.ocr_page_count})")
    st.write(
        f"**Requerente:** {result.applicant.name}  |  **CPF:** "
        f"{result.applicant.cpf_masked or '—'}  |  **Inscrição:** "
        f"{result.property.registration_number or '—'}  |  **Vínculo:** "
        f"{result.property.relationship_type.value}"
    )
    if result.property.multiple_inscriptions_detected:
        st.warning("Múltiplas inscrições detectadas — conferir a inscrição pleiteada.")


def _render_checklist(result) -> None:
    st.subheader("Checklist documental")
    rows = [
        {
            "Item": item.label,
            "Status": _STATUS_BADGE.get(item.status, item.status.value),
            # CORREÇÃO 1: Envolvemos o item.page em str() para não misturar int com string
            "Página": str(item.page) if (item.page is not None and item.evidence) else "—",
            "Evidência": item.evidence if (item.page is not None and item.evidence) else "—",
        }
        for item in result.checklist
    ]
    
    # CORREÇÃO 2: Trocamos use_container_width=True por width="stretch"
    st.dataframe(rows, width="stretch", hide_index=True)

    if result.conclusion.missing_required_documents:
        st.error(
            "Documentos obrigatórios ausentes: "
            + ", ".join(result.conclusion.missing_required_documents)
        )
    if result.conclusion.items_to_verify:
        st.warning("Itens a verificar: " + ", ".join(result.conclusion.items_to_verify))


def _render_minuta(result) -> None:
    st.subheader("Minuta de decisão (revisável)")
    if not result.draft_text:
        st.info("Sem minuta de mérito para esta conclusão.")
        return
    st.text_area("Minuta", result.draft_text, height=420, label_visibility="collapsed")
    st.download_button(
        "Baixar minuta (.txt)",
        data=result.draft_text,
        file_name=f"minuta_{result.process_id}.txt",
        mime="text/plain",
    )


def _render_traceability(result) -> None:
    meta = result.metadata
    with st.expander("Rastreabilidade e auditoria"):
        st.write(f"**ID da análise:** {meta.analysis_id}")
        st.write(f"**Data/hora (UTC):** {meta.created_at.isoformat()}")
        st.write(
            "**Versões:** legal_references "
            f"{meta.legal_references_version} | business_rules {meta.business_rules_version} | "
            f"checklist {meta.checklist_version} | prompts {meta.prompt_version}"
        )
        st.write(f"**LLM:** {meta.llm_provider}/{meta.llm_model} | **OCR:** {meta.ocr_engine}")
        st.write(f"**Política de PII:** {meta.pii_policy}")


def main() -> None:
    st.set_page_config(page_title="POC IPTU — Isenção", page_icon="🏛️", layout="wide")
    st.title("🏛️ POC — Triagem e Minuta de Isenção de IPTU (Guarulhos)")
    st.caption(
        "Faça upload do PDF do processo SEI. A POC lê, classifica, monta o checklist, sugere "
        "a conclusão e gera uma minuta revisável."
    )

    context = _get_runner()
    _render_sidebar(context)

    uploaded = st.file_uploader("PDF do processo", type=["pdf"])
    process_id = st.text_input("Número do processo (PAT)", value="SEI-DEMO")

    if uploaded is not None and st.button("Analisar processo", type="primary"):
        with st.spinner("Analisando o processo…"):
            result = run_analysis(
                context, uploaded.getvalue(), uploaded.name, process_id or None
            )
        st.session_state["result"] = result

    result = st.session_state.get("result")
    if result is None:
        st.info("Envie um PDF e clique em **Analisar processo** para ver a triagem e a minuta.")
        return

    _render_conclusion(result)
    _render_summary(result)
    _render_checklist(result)
    _render_minuta(result)
    _render_traceability(result)


if __name__ == "__main__":
    main()
