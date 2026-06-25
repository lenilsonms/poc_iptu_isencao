"""Cliente de chat completion falso para testar os adapters Azure sem rede."""
from __future__ import annotations

from poc_iptu.adapters.llm import ChatCompletionClient


class ScriptedChatClient(ChatCompletionClient):
    """Devolve uma resposta fixa (JSON) a cada chamada."""

    def __init__(self, response: str, model_name: str = "fake-deployment") -> None:
        self._response = response
        self._model_name = model_name
        self.calls = 0
        self.last_system = None
        self.last_user = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def complete(self, system_prompt: str, user_prompt: str, *, temperature: float) -> str:
        self.calls += 1
        self.last_system = system_prompt
        self.last_user = user_prompt
        return self._response
