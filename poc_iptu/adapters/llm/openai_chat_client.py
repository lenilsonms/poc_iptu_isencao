from __future__ import annotations
from dataclasses import dataclass

from .chat_client import ChatCompletionClient, LlmTransportError

@dataclass(frozen=True)
class OpenAISettings:
    """Configuração de conexão com a OpenAI direta."""
    api_key: str
    model: str = "gpt-5.6-luna"
    response_format_json: bool = True

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "OpenAISettings | None":
        """Constrói a partir do ambiente; retorna None se a chave não existir."""
        api_key = env.get("OPENAI_API_KEY")
        if not api_key:
            return None
        return cls(
            api_key=api_key,
            model=env.get("OPENAI_MODEL", "gpt-5.6-luna")
        )

class OpenAIChatClient(ChatCompletionClient):
    """Cliente de chat completion sobre a OpenAI (não-Azure)."""

    def __init__(self, settings: OpenAISettings) -> None:
        self._settings = settings
        self._client = None

    @property
    def model_name(self) -> str:
        return f"openai:{self._settings.model}"

    def complete(self, system_prompt: str, user_prompt: str, *, temperature: float) -> str:
        client = self._get_client()
        
        # Verifica se o modelo possui restrições severas de API (como o gpt-5-mini ou família o1)
        is_restricted_model = "gpt-5.6-luna" in self._settings.model or self._settings.model.startswith("o1")
        
        messages = []
        if is_restricted_model:
            # Modelos restritos costumam preferir a role 'user' em vez de 'system'
            messages.append({"role": "user", "content": f"INSTRUÇÕES DE SISTEMA:\n{system_prompt}"})
            messages.append({"role": "user", "content": user_prompt})
        else:
            messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})

        kwargs = {
            "model": self._settings.model,
            "messages": messages,
        }

        # Injete temperatura e JSON mode nativo apenas se NÃO for um modelo restrito
        if not is_restricted_model:
            kwargs["temperature"] = temperature
            if self._settings.response_format_json:
                kwargs["response_format"] = {"type": "json_object"}
        else:
            # Força a temperatura exigida pela API para não estourar erro 400
            kwargs["temperature"] = 1 

        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as exc: 
            raise LlmTransportError(f"Falha ao chamar OpenAI: {exc}") from exc
        
        return response.choices[0].message.content or ""

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI  # Import preguiçoso
            except ImportError as exc:
                raise LlmTransportError("Pacote 'openai' não instalado.") from exc
            self._client = OpenAI(api_key=self._settings.api_key)
        return self._client