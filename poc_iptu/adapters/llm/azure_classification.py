"""Adapter de classificação documental sobre o LLM (Azure OpenAI).

Responsabilidade: montar o prompt de classificação, chamar o LLM (via ChatCompletionClient),
fazer parse do JSON e mapear para list[ClassifiedDocument]. Documentos com tipo fora da
taxonomia são descartados (guardrail: o LLM não pode introduzir tipos inexistentes).
"""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from ...domain.pipeline_models import ClassifiedDocument, ExtractedDocument
from ...ports.document_classification import DocumentClassificationPort
from .chat_client import ChatCompletionClient
from .prompt_library import PromptLibrary
from .serialization import LlmResponseError, parse_json_object, serialize_pages



class _LlmClassifiedDocument(BaseModel):
    """Schema intermediário do JSON devolvido pelo LLM (tolerante a campos extras)."""

    document_type: str
    page_start: int
    page_end: int
    title_detected: str | None = None
    evidence: str = ""
    confidence: float = 1.0


class AzureDocumentClassification(DocumentClassificationPort):
    """Classificação documental via LLM, restrita à taxonomia."""

    def __init__(
        self,
        chat_client: ChatCompletionClient,
        prompts: PromptLibrary,
        allowed_document_types: list[str],
    ) -> None:
        self._chat = chat_client
        self._prompts = prompts
        self._allowed = set(allowed_document_types)
        self._allowed_rendered = "\n".join(f"- {t}" for t in allowed_document_types)

    def classify(self, document: ExtractedDocument) -> list[ClassifiedDocument]:
        template = self._prompts.classification
        user_prompt = template.render_user(
            pages=serialize_pages(document, self._prompts.max_page_chars),
            allowed_document_types=self._allowed_rendered,
        )
        content = self._chat.complete(
            template.system, user_prompt, temperature=self._prompts.temperature
        )
        return self._parse(content)

    def _parse(self, content: str) -> list[ClassifiedDocument]:
        data = parse_json_object(content)
        raw_documents = data.get("documents", [])
        if not isinstance(raw_documents, list):
            raise LlmResponseError("Campo 'documents' ausente ou inválido na classificação.")

        result: list[ClassifiedDocument] = []
        for entry in raw_documents:
            try:
                parsed = _LlmClassifiedDocument.model_validate(entry)
            except ValidationError:
                continue  # ignora entradas malformadas, sem quebrar o pipeline
            if parsed.document_type not in self._allowed:
                continue  # guardrail: descarta tipos fora da taxonomia
            result.append(
                ClassifiedDocument(
                    document_type=parsed.document_type,
                    page_start=parsed.page_start,
                    page_end=parsed.page_end,
                    title_detected=parsed.title_detected,
                    evidence=parsed.evidence,
                    confidence=parsed.confidence,
                )
            )
        return result
