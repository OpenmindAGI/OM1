from dataclasses import dataclass

from actions.base import Interface


@dataclass
class TweetInput:
    """Input interface for tweet action."""

    action: str = ""  # Make tweet optional with default empty string


class Tweet(Interface):
    """Tweet action interface."""

    input: TweetInput
    output: TweetInput
