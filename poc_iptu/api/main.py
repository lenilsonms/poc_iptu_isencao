from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from poc_iptu.app.analysis_runner import RunnerContext, build_runner, run_analysis

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND_DIR = _REPO_ROOT / "frontend"
_FRONTEND_INDEX = _FRONTEND_DIR / "iptu_interface.html"


@lru_cache(maxsize=1)
def get_runner_context() -> RunnerContext:
    """
    Cria o RunnerContext uma única vez por processo.

    Isso evita recarregar config, prompts e adapters a cada upload.
    """
    return build_runner()


def enum_value(value: Any) -> Any:
    """
    Converte Enum para string, preservando tipos simples.
    """
    return getattr(value, "value", value)


def serialize_analysis_result(result: Any) -> dict[str, Any]:
    """
    Adapta o ProcessAnalysisResult da POC para o contrato esperado pelo frontend.

    O HTML espera:
    - conclusion.status
    - request.benefit_type
    - applicant.cpf_masked
    - property.relationship_type
    - checklist[].status
    - metadata.*
    - draft_text
    """
    return {
        "process_id": result.process_id,
        "file_name": result.file_name,
        "request": {
            "benefit_type": enum_value(result.request.benefit_type),
            "requested_year": result.request.requested_year,
            "explicit_decree_mention": result.request.explicit_decree_mention,
            "page": result.request.page,
        },
        "applicant": {
            "name": result.applicant.name,
            "cpf_masked": result.applicant.cpf_masked,
            "estado_civil": result.applicant.estado_civil,
            "process_indicates_spouse_or_partner": (
                result.applicant.process_indicates_spouse_or_partner
            ),
            "has_representative": result.applicant.has_representative,
            "has_civil_incapacity": result.applicant.has_civil_incapacity,
            "has_disability_requiring_legal_representative": (
                result.applicant.has_disability_requiring_legal_representative
            ),
        },
        "property": {
            "registration_number": result.property.registration_number,
            "relationship_type": enum_value(result.property.relationship_type),
            "multiple_inscriptions_detected": result.property.multiple_inscriptions_detected,
            "residence_confirmed": result.property.residence_confirmed,
        },
        "income": {
            "benefit_condition": enum_value(result.income.benefit_condition),
            "benefit_document_found": result.income.benefit_document_found,
            "income_document_found": result.income.income_document_found,
            "other_sources_flag": result.income.other_sources_flag,
            "income_status": enum_value(result.income.income_status),
        },
        "conclusion": {
            "status": enum_value(result.conclusion.status),
            "main_reason": result.conclusion.main_reason,
            "missing_required_documents": result.conclusion.missing_required_documents,
            "items_to_verify": result.conclusion.items_to_verify,
            "legal_basis": result.conclusion.legal_basis,
            "warnings": result.conclusion.warnings,
            "generate_merit_draft": result.conclusion.generate_merit_draft,
        },
        "checklist": [
            {
                "code": item.code,
                "label": item.label,
                "required": item.required,
                "status": enum_value(item.status),
                "page": item.page,
                "evidence": item.evidence,
                "confidence": item.confidence,
                "legal_basis": item.legal_basis,
                "warnings": item.warnings,
            }
            for item in result.checklist
        ],
        "documents": [
            {
                "document_type": doc.document_type,
                "page_start": doc.page_start,
                "page_end": doc.page_end,
                "title_detected": doc.title_detected,
                "evidence": doc.evidence,
                "confidence": doc.confidence,
            }
            for doc in result.documents
        ],
        "metadata": {
            "analysis_id": result.metadata.analysis_id,
            "created_at": result.metadata.created_at.isoformat(),
            "app_version": result.metadata.app_version,
            "legal_references_version": result.metadata.legal_references_version,
            "business_rules_version": result.metadata.business_rules_version,
            "checklist_version": result.metadata.checklist_version,
            "llm_provider": result.metadata.llm_provider,
            "llm_model": result.metadata.llm_model,
            "ocr_engine": result.metadata.ocr_engine,
            "pii_policy": result.metadata.pii_policy,
            "prompt_version": result.metadata.prompt_version,
            "source_page_semantics": result.metadata.source_page_semantics,
        },
        "draft_text": result.draft_text,
        "ocr_page_count": result.ocr_page_count,
        "total_page_count": result.total_page_count,
    }


app = FastAPI(
    title="POC IPTU — API",
    version="0.1.0",
)

# Necessário se você abrir o HTML em outra porta, por exemplo localhost:5500.
# Se o HTML for servido pelo próprio FastAPI, CORS não é necessário, mas manter isso ajuda no dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if _FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    if not _FRONTEND_INDEX.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend não encontrado. Coloque iptu_interface.html em ./frontend/",
        )

    return FileResponse(_FRONTEND_INDEX)


@app.get("/api/health")
def health() -> dict[str, Any]:
    context = get_runner_context()

    return {
        "status": "ok",
        "mode": context.mode.value,
        "llm_provider": context.llm_provider,
        "llm_model": context.llm_model,
        "prompt_version": context.prompt_version,
        "ocr_engine": context.ocr_engine,
    }


@app.post("/api/analyze")
async def analyze_process(
    file: UploadFile = File(...),
    process_id: str | None = Form(default=None),
) -> dict[str, Any]:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(
            status_code=400,
            detail="Arquivo inválido. Envie um PDF.",
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Arquivo inválido. A extensão deve ser .pdf.",
        )

    pdf_bytes = await file.read()

    if not pdf_bytes:
        raise HTTPException(
            status_code=400,
            detail="PDF vazio.",
        )

    try:
        context = get_runner_context()

        result = await run_in_threadpool(
            run_analysis,
            context,
            pdf_bytes,
            file.filename,
            process_id,
        )

        return serialize_analysis_result(result)

    except Exception as exc:
        logger.exception("Erro ao analisar processo IPTU.")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao analisar processo: {exc}",
        ) from exc