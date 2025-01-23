from dataclasses import dataclass
from actions.base import Interface


@dataclass
class TweetInput:
    tweet: str


@dataclass
class Tweet(Interface[TweetInput, TweetInput]):
    """
    Tweets to be made by the agent.

    Effect: Allows the agent to tweet.
    """

    input: TweetInput
    output: TweetInput
