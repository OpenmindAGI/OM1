import asyncio
import logging
import threading
import typing as T

from actions.base import AgentAction
from llm.output_model import Action
from runtime.config import RuntimeConfig


class ActionOrchestrator:
    """
    Manages data flow for the actions.

    Note: It is very important that the actions do not block the event loop.
    """

    promise_queue: T.List[asyncio.Task[T.Any]]
    _config: RuntimeConfig
    _impl_threads: T.Dict[str, threading.Thread]
    _connector_threads: T.Dict[str, threading.Thread]

    def __init__(self, config: RuntimeConfig):
        self._config = config
        self.promise_queue = []
        self._impl_threads = {}
        self._connector_threads = {}

    def start(self):
        """
        Start actions and connectors in separate threads
        """
        for agent_action in self._config.agent_actions:
            if agent_action.llm_label not in self._impl_threads:
                impl_thread = threading.Thread(
                    target=self._run_implementation_loop,
                    args=(agent_action,),
                    daemon=True,
                )
                self._impl_threads[agent_action.llm_label] = impl_thread
                impl_thread.start()

            if agent_action.llm_label not in self._connector_threads:
                conn_thread = threading.Thread(
                    target=self._run_connector_loop, args=(agent_action,), daemon=True
                )
                self._connector_threads[agent_action.llm_label] = conn_thread
                conn_thread.start()

        return asyncio.Future()  # Return future for compatibility

    def _run_implementation_loop(self, action: AgentAction):
        """
        Thread-based implementation loop
        """
        while True:
            try:
                action.implementation.tick()
            except Exception as e:
                logging.error(f"Error in implementation {action.llm_label}: {e}")

    def _run_connector_loop(self, action: AgentAction):
        """
        Thread-based connector loop
        """
        while True:
            try:
                action.connector.tick()
            except Exception as e:
                logging.error(f"Error in connector {action.llm_label}: {e}")

    async def flush_promises(self) -> tuple[list[T.Any], list[asyncio.Task[T.Any]]]:
        """
        Flushes the promise queue and returns the completed promises and the pending promises.
        """
        done_promises = []
        for promise in self.promise_queue:
            if promise.done():
                await promise
                done_promises.append(promise)
        self.promise_queue = [p for p in self.promise_queue if p not in done_promises]
        return done_promises, self.promise_queue

    async def promise(self, actions: list[Action]) -> None:
        # loop through commands and send the correct
        # command to the correct action
        for action in actions:
            logging.debug(f"Sending command: {action}")
            agent_action = next(
                (
                    m
                    for m in self._config.agent_actions
                    if m.llm_label == action.type.lower()
                ),
                None,
            )
            if agent_action is None:
                logging.warning(
                    f"Attempted to call non-existant action: {action.type.lower()}"
                )
                continue
            action_response = asyncio.create_task(
                self._promise_action(agent_action, action)
            )
            self.promise_queue.append(action_response)

    async def _promise_action(self, agent_action: AgentAction, action: Action) -> T.Any:
        logging.debug(
            f"Calling action {agent_action.llm_label} with type {action.type.lower()} and argument {action.value}"
        )
        input_interface = T.get_type_hints(agent_action.interface)["input"](
            **{"action": action.value}
        )
        action_response = await agent_action.implementation.execute(input_interface)
        logging.debug(f"Action {agent_action.llm_label} returned {action_response}")
        await agent_action.connector.connect(action_response)
        return action_response
