import asyncio
import logging
from typing import Any, Dict, List, Optional

from evaluation_logger import AgentEvaluationLogger

class CortexSimulator:
    """
    A simulator that can run the production CortexRuntime and log results
    without modifying the production code.
    """
    def __init__(self, cortex_runtime):
        self.cortex = cortex_runtime
        self.logger = AgentEvaluationLogger()
        
    async def simulate_tick(self, prompt: str) -> Dict[str, Any]:
        """
        Simulate a single tick of the cortex with a given prompt.
        Returns the results and logs them.
        """
        # Get the output from the cortex
        output = await self.cortex.config.cortex_llm.ask(prompt)
        if output is None:
            return {"error": "No output from LLM"}
            
        # Log the results
        self.logger.log_tick(
            prompt=prompt,
            output=output,
            actions=[command.dict() for command in output.commands],
            meta={
                "agent": self.cortex.config.name,
                "duty_cycle": getattr(self.cortex, "speech_duty_cycle", 0)
            }
        )
        
        return {
            "prompt": prompt,
            "output": output,
            "actions": [command.dict() for command in output.commands]
        }
        
    async def simulate_conversation(self, prompts: List[str]) -> List[Dict[str, Any]]:
        """
        Simulate a conversation with multiple prompts.
        Returns all results and logs them.
        """
        results = []
        for prompt in prompts:
            result = await self.simulate_tick(prompt)
            results.append(result)
        return results 