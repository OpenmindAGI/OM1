import math
from typing import List

import pyglet
from pyglet.window import key

from llm.output_model import Command
from providers.io_provider import IOProvider


class RacoonSim(pyglet.window.Window):
    """
    RacoonSim is a simple simulator for the Racoon robot.
    """

    def __init__(self, width=800, height=600, io_provider: IOProvider = None):
        super().__init__(width, height, caption="Racoon Simulator")

        # Initialize variables
        self.io_provider = io_provider
        self.time = 0
        self.commands: List[Command] = []

        # Set up rendering
        # clock.schedule_interval(self.tick, 1.0 / 60.0)  # 60 FPS
        self.fps_display = pyglet.window.FPSDisplay(self)

        # Initialize graphics resources
        self.batch = pyglet.graphics.Batch()
        self.setup_graphics()

        pyglet.app.run()

    def setup_graphics(self):
        """Initialize all graphic elements"""
        # Example: Create a simple robot representation
        self.robot = pyglet.shapes.Rectangle(
            x=self.width // 2,
            y=self.height // 2,
            width=50,
            height=50,
            color=(255, 0, 0),
            batch=self.batch,
        )

    def tick(self, dt=1 / 60):
        """Update simulation state"""
        print("tick")
        self.time += dt

        # Update robot position or state based on commands
        if self.commands:
            self.process_commands()

        # Example: Make the robot move in a circle
        radius = 100
        self.robot.x = self.width // 2 + radius * math.cos(self.time)
        self.robot.y = self.height // 2 + radius * math.sin(self.time)

    def process_commands(self):
        """Process any pending commands from the IO provider"""
        if self.io_provider:
            new_commands = self.io_provider.get_commands()
            if new_commands:
                self.commands.extend(new_commands)

        # Process each command in the queue
        for cmd in self.commands:
            # Add your command processing logic here
            pass

        # Clear processed commands
        self.commands.clear()

    def on_draw(self):
        """Render the simulation"""
        self.clear()

        # Draw the background
        # glClearColor(0.2, 0.2, 0.2, 1.0)
        # glClear(GL_COLOR_BUFFER_BIT)

        # Draw all objects in the batch
        self.batch.draw()

        # Draw FPS display
        self.fps_display.draw()

    def on_key_press(self, symbol, modifiers):
        """Handle keyboard input"""
        if symbol == key.ESCAPE:
            self.close()