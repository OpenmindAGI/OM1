import asyncio
import logging
import uuid

from fuser import Fuser
from input.orchestrator import InputOrchestrator
from modules.orchestrator import ModuleOrchestrator
from runtime.config import RuntimeConfig
from tooling.diagnostic_logger import DiagnosticLogger


class CortexRuntime:
    """
    The CortexRuntime is the main entry point for the omOS agent.
    It is responsible for running the agent, orchestrating communication between the memory, fuser, actions, and managing the inputs and outputs.
    """

    config: RuntimeConfig
    fuser: Fuser
    module_orchestrator: ModuleOrchestrator

    def __init__(self, config: RuntimeConfig):
        self.config = config
        self.fuser = Fuser(config)
        self.module_orchestrator = ModuleOrchestrator(config)
        self.input_orchestrator = InputOrchestrator(config.agent_inputs)
        self.diagnostic_logger = DiagnosticLogger.get_instance()

    async def run(self) -> None:
        input_listener_task = await self._start_input_listeners()
        cortex_loop_task = asyncio.create_task(self._run_cortex_loop())
        await asyncio.gather(input_listener_task, cortex_loop_task)

    async def _start_input_listeners(self) -> asyncio.Task:
        input_listener_task = asyncio.create_task(self.input_orchestrator.listen())
        return input_listener_task

    async def _run_cortex_loop(self) -> None:
        while True:
            await asyncio.sleep(1 / self.config.hertz)
            await self._tick()

    async def _tick(self) -> None:
        tick_id = str(uuid.uuid4())
        flushed_inputs = await self.input_orchestrator.flush()
        finished_promises, _ = await self.module_orchestrator.flush_promises()
        prompt = self.fuser.fuse(flushed_inputs, finished_promises)
        self.diagnostic_logger.log_input_events(tick_id, flushed_inputs)
        if prompt is None:
            logging.warning("No prompt to fuse")
            return
        self.diagnostic_logger.log_fuser_prompt(tick_id, prompt)
        output = await self.config.cortex_llm.ask(prompt)
        if output is None:
            logging.warning("No output from LLM")
            return
        self.diagnostic_logger.log_llm_events(tick_id, output.commands)
        logging.debug("I'm thinking... " + str(output))
        await self.module_orchestrator.promise(output.commands)
