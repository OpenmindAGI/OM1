import typing as T

from input.orchestrator import InputEvent
from modules import describe_module
from runtime.config import RuntimeConfig


class Fuser:
    """
    Fuses inputs into a single output
    """

    def __init__(self, config: RuntimeConfig):
        self.config = config

    def fuse(
        self, flushed_inputs: list[InputEvent], finished_promises: list[T.Any]
    ) -> str | None:
        """Combine all inputs, memories, and configurations into a single prompt"""
        system_prompt = self.config.system_prompt
        inputs_fused = " ".join(
            [s.text_prompt for s in flushed_inputs if s.text_prompt is not None]
        )
        modules_fused = "\n\n\n".join(
            [describe_module(module.name) for module in self.config.modules]
        )
        question_prompt = "What will you do? Command: "
        fused_prompt = f"{system_prompt}\n\n{inputs_fused}\n\nAVAILABLE MODULES:\n{modules_fused}\n\n{question_prompt}"
        return fused_prompt
