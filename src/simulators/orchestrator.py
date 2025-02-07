import asyncio
import logging
import threading
import typing as T

from llm.output_model import Command
from runtime.config import RuntimeConfig
from simulators.base import Simulator


class SimulatorOrchestrator:
    """
    Manages data flow to one or more simulators.
    Note: It is important that the simulators do not block the event loop.
    """

    promise_queue: T.List[asyncio.Task[T.Any]]
    _config: RuntimeConfig
    _simulator_threads: T.Dict[str, threading.Thread]

    def __init__(self, config: RuntimeConfig):
        self._config = config
        self.promise_queue = []
        self._simulator_threads = {}

    def start(self):
        """
        Start simulators in separate threads
        """
        for simulator in self._config.simulators:
            if simulator.name not in self._simulator_threads:
                thread = threading.Thread(
                    target=self._run_simulator_loop, args=(simulator,), daemon=True
                )
                self._simulator_threads[simulator.name] = thread
                thread.start()
        return asyncio.Future()  # Return future for compatibility

    def _run_simulator_loop(self, simulator: Simulator):
        """
        Thread-based simulator loop
        """
        while True:
            try:
                simulator.tick()
            except Exception as e:
                logging.error(f"Error in simulator {simulator.name}: {e}")

    async def flush_promises(self) -> tuple[list[T.Any], list[asyncio.Task[T.Any]]]:
        """
        Flushes the promise queue and returns the completed promises
        and the pending promises.
        """
        done_promises = []
        for promise in self.promise_queue:
            if promise.done():
                await promise
                done_promises.append(promise)
        self.promise_queue = [p for p in self.promise_queue if p not in done_promises]
        return done_promises, self.promise_queue

    async def promise(self, commands: T.List[Command]) -> None:
        # loop through simulators and send each one of them
        # the current LLM_full
        for simulator in self._config.simulators:
            simulator_response = asyncio.create_task(
                self._promise_simulator(simulator, commands)
            )
            self.promise_queue.append(simulator_response)

    async def _promise_simulator(
        self, simulator: Simulator, commands: T.List[Command]
    ) -> T.Any:
        logging.debug(f"Calling simulator {simulator.name} with commands {commands}")
        simulator.sim(commands)
        return None
