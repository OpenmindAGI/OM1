import asyncio
import logging
from queue import Empty, Queue
from typing import AsyncIterator, List, Optional, Dict, Any

# Import discord.py
import discord
from discord.ext import commands

from inputs.base import SensorConfig
from inputs.base.loop import FuserInput

# Try to import the Discord connector registration
try:
    from actions.speak.connector.discord_message import register_discord_client
    HAS_CONNECTOR = True
except ImportError:
    HAS_CONNECTOR = False
    logging.warning("Discord message connector not available, bot won't respond automatically")

class DiscordInput(FuserInput[str]):
    """Discord integration input handler for chatting with OM1."""

    def __init__(
        self,
        config: Optional[SensorConfig] = None,
    ):
        """Initialize DiscordInput with configuration.

        Parameters
        ----------
        config : Optional[SensorConfig]
            Configuration object from the runtime
        """
        if config is None:
            config = SensorConfig()

        super().__init__(config)

        self.buffer: List[str] = []
        self.message_buffer: Queue[str] = Queue()
        self.bot_token = getattr(config, "bot_token", None)
        self.channel_id = getattr(config, "channel_id", None)
        self.message_history: List[Dict[str, Any]] = []
        
        # Create Discord client with all intents
        intents = discord.Intents.default()
        intents.message_content = True  # Need to enable this to read message content
        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.is_running = False
        
        # Register this instance to receive messages from the connector
        if HAS_CONNECTOR:
            register_discord_client(self)
            logging.info("Discord input registered with connector")
        
        # Set up bot event handlers
        @self.bot.event
        async def on_ready():
            logging.info(f"Logged in as {self.bot.user}")
            logging.info(f"Monitoring channel: {self.channel_id}")
            self.is_running = True
            
        @self.bot.event
        async def on_message(message):
            # Ignore messages from the bot itself
            if message.author == self.bot.user:
                return
                
            # Only process messages from the specified channel if configured
            if self.channel_id and str(message.channel.id) != str(self.channel_id):
                return
            
            # Store the message in history
            self.message_history.append({
                "author": message.author.name,
                "content": message.content,
                "is_bot": False
            })
            
            # Add message to buffer
            msg_content = f"{message.author.name}: {message.content}"
            self.message_buffer.put_nowait(msg_content)
            self.buffer.append(msg_content)
            logging.info(f"Received message: {msg_content}")
            
            # Process commands
            await self.bot.process_commands(message)
            
            # Print conversation log after each message
            self.print_conversation_log()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.is_running:
            await self.bot.close()

    def print_conversation_log(self):
        """Print the current conversation log to the console."""
        print("\n=== CONVERSATION LOG ===")
        for idx, msg in enumerate(self.message_history):
            source = "BOT" if msg.get("is_bot", False) else "USER"
            print(f"[{idx+1}] [{source}] {msg['author']}: {msg['content']}")
        print("========================\n")

    async def raw_to_text(self, raw_input: Optional[str] = None):
        """Convert raw input to text format and add to buffer.

        Parameters
        ----------
        raw_input : Optional[str]
            Raw input to process. If None, process from message buffer.

        Returns
        -------
        str
            The processed text
        """
        if raw_input:
            self.message_buffer.put_nowait(raw_input)

        if self.message_buffer:
            try:
                message = self.message_buffer.get_nowait()
                if message:
                    if message not in self.buffer:
                        self.buffer.append(message)
                    logging.debug(f"Processing message: {message}")
                    return message
            except Empty:
                pass

        return ""

    async def start(self):
        """Start the Discord bot."""
        if not self.bot_token:
            logging.error("Discord bot token not provided")
            return
            
        logging.info(f"Starting Discord bot with token: {self.bot_token[:5]}...")
        
        # Start Discord bot in background task
        asyncio.create_task(self.bot.start(self.bot_token))
        
        # Wait for bot to be ready
        start_time = asyncio.get_event_loop().time()
        while not self.is_running:
            await asyncio.sleep(0.1)
            # Timeout after 30 seconds
            if asyncio.get_event_loop().time() - start_time > 30:
                logging.error("Timed out waiting for Discord bot to start")
                return

    async def listen(self) -> AsyncIterator[str]:
        """Listen for new Discord messages."""
        await self.start()

        while True:
            message = await self._poll()
            if message:
                yield message
            await asyncio.sleep(0.1)

    async def _poll(self) -> Optional[str]:
        """Poll for new messages."""
        await asyncio.sleep(0.5)
        try:
            message = self.message_buffer.get_nowait()
            return message
        except Empty:
            return None
            
    async def send_message(self, content):
        """Send a message to the configured Discord channel."""
        if not self.is_running:
            logging.error("Discord bot is not running")
            return False
            
        try:
            if not self.channel_id:
                logging.error("No channel_id configured")
                return False
                
            channel = self.bot.get_channel(int(self.channel_id))
            if not channel:
                # Try to fetch the channel if not found in cache
                try:
                    channel = await self.bot.fetch_channel(int(self.channel_id))
                except:
                    logging.error(f"Channel {self.channel_id} not found")
                    return False
                    
            if channel:
                await channel.send(content)
                
                # Store bot message in history
                self.message_history.append({
                    "author": self.bot.user.name if self.bot.user else "Bot",
                    "content": content,
                    "is_bot": True
                })
                
                logging.info(f"Sent message: {content}")
                self.print_conversation_log()
                return True
        except Exception as e:
            logging.error(f"Error sending message: {str(e)}")
            return False

    def formatted_latest_buffer(self) -> Optional[str]:
        """Format and return the conversation context."""
        if not self.buffer:
            return None

        # Get the last few messages from the buffer
        recent_messages = self.buffer[-10:] if len(self.buffer) > 10 else self.buffer
        content = "\n".join(recent_messages)

        result = f"""
DiscordInput CONVERSATION
// START
{content}
// END
"""
        return result

    async def speak(self, text):
        """Handle speaking action by sending to Discord."""
        if isinstance(text, dict) and 'action' in text:
            # Handle when receiving dict from passthrough
            content = text['action']
        else:
            # Handle direct string input
            content = text
            
        # Actually send the message
        success = await self.send_message(content)
        logging.info(f"Discord message sent: {content}, success: {success}")
        return success

    async def initialize_with_query(self, query: str):
        """Initialize with a query - not used for Discord but required by interface"""
        logging.info(f"[DiscordInput] Initializing with query: {query}")
        
        # Store system message in history
        self.message_history.append({
            "author": "System",
            "content": query,
            "is_bot": True
        })
        
        self.message_buffer.put_nowait(f"System: {query}")
        self.print_conversation_log()