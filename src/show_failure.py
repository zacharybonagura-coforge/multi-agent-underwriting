"""Show a risk-scoring timeout: one retry, then escalate."""

from model.base import Generation, ModelTimeoutError
from model.ollama import OllamaAdapter
from pipeline import run


class TimeoutOnRisk:
    """Call Ollama for every agent except risk scoring."""

    def __init__(self) -> None:
        self._ollama = OllamaAdapter()
        self.provider = self._ollama.provider
        self.model_id = self._ollama.model_id
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> Generation:
        self.prompts.append(prompt)
        if prompt.startswith("Score this insurance application"):
            raise ModelTimeoutError("risk scoring timed out")
        return self._ollama.generate(prompt)


def main() -> None:
    model = TimeoutOnRisk()
    result = run(
        {
            "applicant_name": "Ada Lovelace",
            "date_of_birth": "1815-12-10",
            "address": "12 St James Square, London",
            "product": "AUTO",
            "coverage_amount": "16000",
            "stated_income": "120000",
        },
        model,
    )
    risk_prompts = [prompt for prompt in model.prompts if prompt.startswith("Score this")]
    print("--- risk calls:", len(risk_prompts))
    for number, prompt in enumerate(risk_prompts, start=1):
        label = "first call" if number == 1 else f"retry {number - 1}"
        print(f"--- {label} ends with ---")
        print("\n".join(prompt.splitlines()[-4:]))
    print("--- kept intake:", result.intake.message.applicant_name if result.intake else None)
    print("--- kept enrichment:", result.enrichment.message.credit_band if result.enrichment else None)
    print("--- risk:", result.risk)
    print("--- recommendation:", result.recommendation)
    print("--- final_decision:", result.final_decision)


if __name__ == "__main__":
    main()
