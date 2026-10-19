"""Ollama implementation of ModelAdapter."""

import httpx

from model.base import Generation, ModelTimeoutError


class OllamaAdapter:
    """ModelAdapter backed by a local Ollama generate endpoint.

    Posts to ``{host}/api/generate`` with streaming off and temperature 0.
    """

    provider = "ollama"

    def __init__(
        self,
        model_id: str = "qwen3:8b",
        host: str = "http://host.docker.internal:11434",
        thinking: bool = False
    ) -> None:
        """Use ``model_id`` and the Ollama ``host`` generate URL."""
        self.model_id = model_id
        self._url = f"{host}/api/generate"
        self.thinking = thinking

    def generate(self, prompt: str) -> Generation:
        """Return Ollama's completion for ``prompt``."""
        try:
            response = httpx.post(
                self._url,
                json={
                    "model": self.model_id,
                    "prompt": prompt,
                    "stream": False,
                    "think": self.thinking,
                    "options": {"temperature": 0, "seed": 42},
                },
                timeout=120.0,
            )
        except httpx.TimeoutException as exc:
            raise ModelTimeoutError(str(exc)) from exc

        response.raise_for_status()
        body = response.json()
        
        return Generation(
            text=body["response"].strip(),
            input_tokens=body.get("prompt_eval_count", 0),
            output_tokens=body.get("eval_count", 0),
        )
