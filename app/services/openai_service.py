from dataclasses import dataclass
from openai import OpenAI

@dataclass
class OpenAIService:
    client: OpenAI

    def warmup_models(self) -> None:
        for model in ("gpt-3.5-turbo", "gpt-4-turbo"):
            try:
                self.client.chat.completions.create(
                    model=model,
                    messages=[{"role":"system","content":""}, {"role":"user","content":""}],
                    max_tokens=1,
                )
            except Exception:
                pass
