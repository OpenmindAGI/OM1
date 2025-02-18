import logging
from typing import Dict

import requests


def setup_beamer(api_key: str, uuid: str, raw_config: Dict) -> bool:
    """
    Setup the beamer for caching

    Parameters
    ----------
    api_key : str
        The API key for the beamer
    uuid : str
        The UUID for the beamer
    raw_config : dict
        The raw configuration

    Returns
    -------
    bool
        True if cache is enabled, False otherwise
    """
    cache = False
    if raw_config.get("cache", False) and api_key is not None and api_key != "":
        cache = send_beams_to_beamer(api_key, uuid, raw_config)

    if "beamer_url" in raw_config:
        del raw_config["beamer_url"]

    return cache


def send_beams_to_beamer(api_key: str, uuid: str, raw_config: Dict) -> bool:
    """
    Send beams to the beamer

    Parameters
    ----------
    api_key : str
        The API key for the beamer
    uuid : str
        The UUID for the beamer
    raw_config : dict
        The raw configuration

    Returns
    -------
    bool
        True if beams were sent successfully, False otherwise
    """
    beamer_url = raw_config.get(
        "beamer_url", "https://api.openmind.org/api/core/beamer"
    )
    try:
        response = requests.post(
            beamer_url,
            json=raw_config,
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "x-uuid": uuid,
            },
        )
        if response.status_code == 200:
            logging.info(
                "Caching is enabled for TTS requests. Beams have been sent to the beamer. Please be mindful of potential privacy implications."
            )
            return True
        else:
            logging.error(
                "Caching is enabled for TTS requests, but beams could not be sent to the beamer. Please check your configuration. error: %s",
                response.text,
            )
            return False
    except Exception as e:
        logging.error(
            "Caching is enabled for TTS requests, but beams could not be sent to the beamer. Please check your configuration. error: %s",
            e,
        )
        return False
