from collections import defaultdict
import asyncio
from typing import Any, Optional

from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig
from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary


class AntigravityClient(BaseLM):
    """
    LM Client for running models through the Google Antigravity SDK.
    Supports asynchronous execution, local streaming, and capability policies.
    """

    def __init__(
        self,
        model_name: str | None = "gemini-3.7-flash",
        system_instructions: str | None = None,
        capabilities: Optional[CapabilitiesConfig] = None,
        **kwargs,
    ):
        super().__init__(model_name=model_name or "gemini-3.7-flash", **kwargs)
        self.system_instructions = system_instructions or "You are an expert AI agent in MIT RLM."
        self.capabilities = capabilities or CapabilitiesConfig()

        self.model_call_counts: dict[str, int] = defaultdict(int)
        self.model_input_tokens: dict[str, int] = defaultdict(int)
        self.model_output_tokens: dict[str, int] = defaultdict(int)
        self.model_total_tokens: dict[str, int] = defaultdict(int)

        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0

    def completion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        return asyncio.run(self.acompletion(prompt, model=model))

    async def acompletion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        prompt_text = prompt if isinstance(prompt, str) else str(prompt)
        config = LocalAgentConfig(
            system_instructions=self.system_instructions,
            capabilities=self.capabilities,
        )
        tokens = []
        async with Agent(config) as agent:
            response = await agent.chat(prompt_text)
            async for token in response:
                tokens.append(token)

        result_text = "".join(tokens)

        # Track usage stats
        m_name = model or self.model_name
        self.model_call_counts[m_name] += 1
        est_in = max(1, len(prompt_text) // 4)
        est_out = max(1, len(result_text) // 4)
        self.model_input_tokens[m_name] += est_in
        self.model_output_tokens[m_name] += est_out
        self.model_total_tokens[m_name] += (est_in + est_out)
        self.last_prompt_tokens = est_in
        self.last_completion_tokens = est_out

        return result_text

    def get_usage_summary(self) -> UsageSummary:
        model_summaries = {}
        for model in self.model_call_counts:
            model_summaries[model] = ModelUsageSummary(
                total_calls=self.model_call_counts[model],
                total_input_tokens=self.model_input_tokens[model],
                total_output_tokens=self.model_output_tokens[model],
                total_cost=0.0,
            )
        return UsageSummary(model_usage_summaries=model_summaries)

    def get_last_usage(self) -> ModelUsageSummary:
        return ModelUsageSummary(
            total_calls=1,
            total_input_tokens=self.last_prompt_tokens,
            total_output_tokens=self.last_completion_tokens,
            total_cost=0.0,
        )
