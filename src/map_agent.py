#!/usr/bin/env python3
"""
Map Generation Agent

This script serves as a simple wrapper to run the mapper agent that generates
maps of unknown areas.
"""

import asyncio
import logging
import sys

import dotenv
import typer

from runtime.config import load_config
from runtime.cortex import CortexRuntime

app = typer.Typer()


@app.command()
def run(debug: bool = False) -> None:
    """
    Run the map generation agent to explore and create maps of unknown areas.
    """
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    logging.info("Starting map generation agent...")

    # Load the mapper configuration
    config = load_config("mapper")
    runtime = CortexRuntime(config)

    # Start the runtime
    try:
        asyncio.run(runtime.run())
    except KeyboardInterrupt:
        logging.info("Map generation stopped by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Error running map generation agent: {e}")
        sys.exit(1)


if __name__ == "__main__":
    dotenv.load_dotenv()
    app() 