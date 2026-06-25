import base64
from poc_iptu.ports.ocr import OcrPort
from poc_iptu.domain.errors import PocIptuError

class LlmVisionOcr(OcrPort):
    """Motor de OCR baseado em LLM Multimodal otimizado para velocidade."""

    def __init__(self, client, model_name: str = "gpt-5-mini"):
        self._client = client
        self._model_name = model_name

    @property
    def engine_name(self) -> str:
        return f"llm-vision:{self._model_name}"

    def extract_text(self, page_image_png: bytes) -> str:
        base64_image = base64.b64encode(page_image_png).decode("utf-8")

        # Prompt super direto para evitar geração de tokens inúteis
        system_prompt = (
            "Transcreva o texto da imagem. Apenas o texto bruto. "
            "Sem formatação markdown, sem explicações."
        )

        # Montagem dinâmica dos argumentos
        kwargs = {
            "model": self._model_name,
            "messages": [
                {"role": "user", "content": system_prompt}, # Modelos de raciocínio preferem instruções no 'user'
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                                "detail": "auto"  # <-- CRÍTICO PARA VELOCIDADE: Evita fatiamento de alta resolução
                            }
                        }
                    ]
                }
            ]
        }

        # Aplica a trava de raciocínio se for um modelo da família o1/gpt-5
        if "gpt-5.4-mini" in self._model_name or self._model_name.startswith("o1"):
            kwargs["reasoning_effort"] = "low" # <-- Faz o modelo "pensar" o mínimo possível
        else:
            kwargs["temperature"] = 0.0 # Para modelos padrão (gpt-4o), fixa o determinismo

        try:
            response = self._client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise PocIptuError(f"Falha ao realizar OCR veloz via LLM: {exc}") from exc