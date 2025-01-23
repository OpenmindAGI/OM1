from actions.base import ActionImplementation

from actions.tweet.interface import TweetInput


class TweetPassthroughImplementation(ActionImplementation[TweetInput, TweetInput]):
    """
    A passthrough implementation of the tweet action. Output is the same as the input.
    """

    async def execute(self, input_interface: TweetInput) -> TweetInput:
        return input_interface
