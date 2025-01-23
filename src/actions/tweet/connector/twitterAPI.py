import logging
from actions.base import ActionConnector
from actions.tweet.interface import TwitterInput


class TweetAPIConnector(ActionConnector[TweetInput]):
    async def connect(self, output_interface: TweetInput) -> None:
        tweet_to_make = {'sentence': output_interface.tweet}
        logging.info(f"SendThisToTwitterAPI: {tweet_to_make}")
