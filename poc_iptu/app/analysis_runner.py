"""Orquestração da aplicação para a UI, isolada do Streamlit (e testável).

Decide o modo de execução pela presença de variáveis de ambiente do Azure OpenAI:
  - AZURE configurado  -> usa os adapters Azure (LLM real) + prompts.yaml versionado;
  - caso contrário      -> usa os adapters de demonstração offline (caso-ouro).

Em ambos os casos, monta o AnalyzeProcessUseCase completo (PDF + checklist + conclusão + minuta).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ..adapters import PyMuPdfDocumentReader
from ..adapters.llm import (
    AzureDocumentClassification,
    AzureFieldExtraction,
    AzureOpenAIChatClient,
    AzureOpenAISettings,
    OfflineDemoClassification,
    OfflineDemoExtraction,
    PromptLibrary,
    load_allowed_document_types,
)
from ..adapters.ocr import NoOpOcr, PaddleOcr
from ..application.analyze_process_use_case import (
    AnalyzeProcessRequest,
    AnalyzeProcessUseCase,
    build_analyze_process_use_case,
)
from ..domain.pipeline_models import ProcessAnalysisResult
from ..ports.ocr import OcrPort
from ..adapters.llm.openai_chat_client import OpenAIChatClient, OpenAISettings

class AnalysisMode(str, Enum):
    AZURE = "AZURE"
    OFFLINE_DEMO = "OFFLINE_DEMO"


@dataclass(frozen=True)
class RunnerContext:
    """Caso de uso pronto + descrição do modo, para a UI exibir."""

    use_case: AnalyzeProcessUseCase
    mode: AnalysisMode
    llm_provider: str
    llm_model: str
    prompt_version: str
    ocr_engine: str


def default_config_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "config"


def build_runner(
    config_dir: Path | str | None = None,
    prompts_path: Path | str | None = None,
    env: dict[str, str] | None = None,
) -> RunnerContext:
    """Monta o RunnerContext, escolhendo Azure ou demonstração offline."""
    env = dict(os.environ if env is None else env)
    config_dir = Path(config_dir) if config_dir else default_config_dir()
    prompts_path = Path(prompts_path) if prompts_path else config_dir / "prompts.yaml"
    ocr = _build_ocr(env)

    #azure_settings = AzureOpenAISettings.from_env(env)
    openai_settings = OpenAISettings.from_env(env)
    if openai_settings is not None:
        return _build_openai(config_dir, prompts_path, ocr, openai_settings)
    #if azure_settings is not None:
        #return _build_azure(config_dir, prompts_path, ocr, azure_settings)
    return _build_offline_demo(config_dir, ocr)

def _build_openai(
    config_dir: Path, prompts_path: Path, ocr: OcrPort, settings: OpenAISettings
) -> RunnerContext:
    prompts = PromptLibrary.from_yaml(prompts_path)
    chat_client = OpenAIChatClient(settings)
    allowed_types = load_allowed_document_types(config_dir)
    classifier = AzureDocumentClassification(chat_client, prompts, allowed_types)
    extractor = AzureFieldExtraction(chat_client, prompts)
    
    use_case = build_analyze_process_use_case(
        config_dir=config_dir,
        document_reader=PyMuPdfDocumentReader(ocr),
        classifier=classifier,
        field_extractor=extractor,
        ocr=ocr,
        llm_provider="openai",
        llm_model=chat_client.model_name,
        prompt_version=prompts.version,
    )
    return RunnerContext(
        use_case=use_case,
        mode=AnalysisMode.AZURE, # Reutilizamos o modo AZURE pois significa "LLM Real" na UI
        llm_provider="openai",
        llm_model=chat_client.model_name,
        prompt_version=prompts.version,
        ocr_engine=ocr.engine_name,
    )

def run_analysis(
    context: RunnerContext, pdf_bytes: bytes, file_name: str, process_id: str | None = None
) -> ProcessAnalysisResult:
    """Executa a análise de um PDF (em bytes) e devolve o resultado completo."""
    request = AnalyzeProcessRequest(
        source=pdf_bytes, file_name=file_name, process_id=process_id
    )
    return context.use_case.execute(request)


# --------------------------------------------------------------------- helpers


def _build_ocr(env: dict[str, str]) -> OcrPort:
    engine = env.get("POC_OCR_ENGINE", "").lower()
    
    if engine == "paddle":
        from ..adapters.ocr import PaddleOcr
        return PaddleOcr(lang=env.get("POC_OCR_LANG", "pt"))
        
    elif engine == "llm-vision":
        from ..adapters.ocr.llm_vision_ocr import LlmVisionOcr
        from openai import OpenAI
        # Aproveitamos a chave já existente do ambiente
        client = OpenAI(api_key=env.get("OPENAI_API_KEY")) 
        return LlmVisionOcr(client=client, model_name=env.get("OPENAI_MODEL_VISION", "gpt-5.4-mini"))
        
    from ..adapters.ocr import NoOpOcr
    return NoOpOcr()


def _build_azure(
    config_dir: Path, prompts_path: Path, ocr: OcrPort, settings: AzureOpenAISettings
) -> RunnerContext:
    prompts = PromptLibrary.from_yaml(prompts_path)
    chat_client = AzureOpenAIChatClient(settings)
    allowed_types = load_allowed_document_types(config_dir)
    classifier = AzureDocumentClassification(chat_client, prompts, allowed_types)
    extractor = AzureFieldExtraction(chat_client, prompts)
    use_case = build_analyze_process_use_case(
        config_dir=config_dir,
        document_reader=PyMuPdfDocumentReader(ocr),
        classifier=classifier,
        field_extractor=extractor,
        ocr=ocr,
        llm_provider="azure-openai",
        llm_model=chat_client.model_name,
        prompt_version=prompts.version,
    )
    return RunnerContext(
        use_case=use_case,
        mode=AnalysisMode.AZURE,
        llm_provider="azure-openai",
        llm_model=chat_client.model_name,
        prompt_version=prompts.version,
        ocr_engine=ocr.engine_name,
    )


def _build_offline_demo(config_dir: Path, ocr: OcrPort) -> RunnerContext:
    use_case = build_analyze_process_use_case(
        config_dir=config_dir,
        document_reader=PyMuPdfDocumentReader(ocr),
        classifier=OfflineDemoClassification(),
        field_extractor=OfflineDemoExtraction(),
        ocr=ocr,
        llm_provider="offline-demo",
        llm_model="n/a",
        prompt_version="offline-demo",
    )
    return RunnerContext(
        use_case=use_case,
        mode=AnalysisMode.OFFLINE_DEMO,
        llm_provider="offline-demo",
        llm_model="n/a",
        prompt_version="offline-demo",
        ocr_engine=ocr.engine_name,
    )
