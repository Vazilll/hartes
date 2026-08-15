from collections import defaultdict
import asyncio
from typing import Any, Optional

from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary

# Primary brain: vazus_core.engine.llm_client.async_generate_llm (Tier-1 agy CLI
# on IDE session quota, 0 external API cost). Fallback to the Google Antigravity
# SDK only when vazus_core is not importable (standalone RLM runs).
try:
    from vazus_core.engine.llm_client import async_generate_llm

    _VAZUS_CORE_AVAILABLE = True
except ImportError:  # pragma: no cover - standalone environment
    _VAZUS_CORE_AVAILABLE = False


class AntigravityClient(BaseLM):
    """
    LM Client for running models through the Antigravity engine.

    Primary path: vazus_core.engine.llm_client.async_generate_llm, which routes
    through the official agy CLI binary on Antigravity IDE session quota
    (Gemini 3.7 Thinking / Claude Sonnet 4.6 Thinking, no external keys).
    Fallback (vazus_core unavailable): Google Antigravity SDK direct session.
    Supports asynchronous execution, local streaming, and capability policies.
    """

    def __init__(
        self,
        model_name: str | None = "gemini-3.7-flash",
        system_instructions: str | None = None,
        capabilities: Optional[Any] = None,
        **kwargs,
    ):
        super().__init__(model_name=model_name or "gemini-3.7-flash", **kwargs)
        self.system_instructions = system_instructions or "You are an expert AI agent in MIT RLM."
        # Only used by the SDK fallback path (kept as Any to avoid a hard
        # google.antigravity import at module level).
        self.capabilities = capabilities

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
        m_name = model or self.model_name

        if _VAZUS_CORE_AVAILABLE:
            # Tier-1: agy CLI on IDE quota via the canonical vazus brain.
            result_text = await async_generate_llm(
                prompt=prompt_text,
                system_prompt=self.system_instructions,
                model=m_name,
                temperature=0.2,
                timeout_seconds=120.0,
            )
        else:  # pragma: no cover - standalone fallback
            from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig

            config = LocalAgentConfig(
                system_instructions=self.system_instructions,
                capabilities=self.capabilities or CapabilitiesConfig(),
            )
            tokens = []
            async with Agent(config) as agent:
                response = await agent.chat(prompt_text)
                async for token in response:
                    tokens.append(token)
            result_text = "".join(tokens)

        # Track usage stats
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
