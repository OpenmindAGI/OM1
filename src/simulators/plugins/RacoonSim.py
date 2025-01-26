import os
import re
from typing import List

import gif_pygame
import pygame

from llm.output_model import Command
from providers.io_provider import IOProvider

from threading import Event, Thread
import logging

class RacoonSim:

    def __init__(self):
        self.messages: list[str] = []

        self.io_provider = IOProvider()

        self.name = __class__
        pygame.init()

        # define the RGB value for white,
        #  green, blue colour .
        self.white = (255, 255, 255)
        self.green = (0, 255, 0)
        self.blue = (0, 0, 128)
        self.black = (0, 0, 0)
        self.lightblue = (84, 118, 156)

        self.X = 800
        self.Y = 630

        self.clock = pygame.Clock()

        self.display = pygame.display.set_mode((self.X, self.Y))
        pygame.display.set_caption("Racoon Simulator")
        self.display.fill(self.lightblue)

        self.surface_text = pygame.Surface((800, 230))
        self.surface_text.fill(self.white)

        self.surface_ani = pygame.Surface((400, 400))
        self.surface_ani.fill(self.lightblue)

        self.font = pygame.font.Font("freesansbold.ttf", 14)
        self.path = os.path.join(os.path.dirname(__file__), "assets")

        self.action_walk = gif_pygame.load(os.path.join(self.path, "walk.gif"))
        self.action_run = gif_pygame.load(os.path.join(self.path, "run.gif"))
        self.action_idle = gif_pygame.load(os.path.join(self.path, "idle.gif"))
        self.action_sit = gif_pygame.load(os.path.join(self.path, "crouch.gif"))

        self.a_s = ""

        self.cancel_future_calls = self.call_repeatedly()

    def call_repeatedly(self):
        stopped = Event()
        interval_s = 0.05
        def loop():
            while not stopped.wait(interval_s):
                # logging.info(f"Hello from the refresh timer")
                self._tick()
        Thread(target=loop).start()
        return stopped.set
        # to cancel call this
        # cancel_future_calls() 

    # async def _run_animation_loop(self) -> None:
    #     while True:
    #         await asyncio.sleep(0.1)
    #         await self._tick()

    def _tick(self) -> None:
        self.surface_ani.fill(self.lightblue)

        if self.a_s == "walk":
            self.action_walk.render(self.surface_ani, (0, 0))
        elif self.a_s == "run":
            self.action_run.render(self.surface_ani, (0, 0))
        elif self.a_s == "sit":
            self.action_sit.render(self.surface_ani, (0, 0))
        else:
            self.action_idle.render(self.surface_ani, (0, 0))

        self.display.blit(self.surface_ani, (180, 230))

        # this is what updates everything
        pygame.display.flip()

    def input_clean(self, input, earliest_time) -> str:
        st = input
        st = st.strip()
        st = st.replace("\n", "")
        st = re.sub(r"\s+", " ", st)  # replace runs of whitespace
        st = st.replace("INPUT // START ", "")
        st = st.replace(" // END", "")

        sts = st.split("::")
        time = float(sts[0])
        time_rezero = time - earliest_time
        time_st = f"{time_rezero:.3f}::{sts[-1]}"

        return time_st

    def get_earliest_time(self) -> float:
        earliest_time = float("inf")
        for value in self.io_provider.inputs.values():
            timestamp = value.timestamp
            if timestamp < earliest_time:
                earliest_time = timestamp
        return earliest_time

    # this updates the state of the simulator, but does not refresh the display -
    # that's done in call_repeatedly
    def run(self, commands: List[Command]) -> None:

        earliest_time = self.get_earliest_time()

        # make the background white
        self.surface_text.fill(self.white)

        y = 15
        for action, values in self.io_provider.inputs.items():
            inp = (
                f"{(values.timestamp - earliest_time):.3f}:: {action} :: {values.input}"
            )
            self.text = self.font.render(inp, True, self.black, self.white)
            self.textRect = self.text.get_rect()
            self.textRect.topleft = (20, y)
            y += 20
            self.surface_text.blit(self.text, self.textRect)

        dft = f"{self.io_provider.fuser_end_time - earliest_time:.3f}"
        self.text = self.font.render(f"Fuse_time: {dft}", True, self.black, self.white)
        self.textRect = self.text.get_rect()
        self.textRect.topleft = (20, y)
        y += 20
        self.surface_text.blit(self.text, self.textRect)

        dst = f"{float(self.io_provider.llm_start_time) - earliest_time:.3f}"
        self.text = self.font.render(f"LLM_begin: {dst}", True, self.black, self.white)
        self.textRect = self.text.get_rect()
        self.textRect.topleft = (20, y)
        y += 20
        self.surface_text.blit(self.text, self.textRect)

        processing_time_s = float(self.io_provider.llm_end_time) - float(
            self.io_provider.llm_start_time
        )
        dt = f"{processing_time_s:.3f}"
        self.text = self.font.render(
            f"LLM_proc time: {dt}", True, self.black, self.white
        )
        self.textRect = self.text.get_rect()
        self.textRect.topleft = (20, y)
        y += 20
        self.surface_text.blit(self.text, self.textRect)

        dtt = f"{float(self.io_provider.llm_end_time) - earliest_time:.3f}"
        self.text = self.font.render(f"LLM_done: {dtt}", True, self.black, self.white)
        self.textRect = self.text.get_rect()
        self.textRect.topleft = (20, y)
        y += 20
        self.surface_text.blit(self.text, self.textRect)

        for command in commands:
            action_type = command.name
            action_spec = command.arguments[0].value
            if action_type == "move":
                self.a_s = action_spec
            action = action_type + "::" + action_spec
            self.text = self.font.render(action, True, self.black, self.white)
            self.textRect = self.text.get_rect()
            self.textRect.topleft = (20, y)
            y += 20
            self.surface_text.blit(self.text, self.textRect)

        self.display.blit(self.surface_text, (0, 0))
