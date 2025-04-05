import asyncio
import logging
import os

import dotenv
import typer
import discord
from discord.ext import commands

from runtime.config import load_config
from runtime.cortex import CortexRuntime

app = typer.Typer()

# Global variable to store the runtime instance
runtime_instance = None

class DiscordBot(discord.Client):
    def __init__(self, runtime, channel_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.runtime = runtime
        self.channel_id = channel_id
        
    async def on_ready(self):
        print(f'Bot is connected as {self.user}')
        
    async def on_message(self, message):
        # Ignore messages from the bot itself
        if message.author == self.user:
            return
            
        # Only respond in the specified channel
        if str(message.channel.id) != self.channel_id:
            return
            
        if message.content.startswith('!'):
            return
            
        # Fetch previous messages for context
        conversation_log = []
        
        async with message.channel.typing():
            # Get previous messages
            async for msg in message.channel.history(limit=15):
                if msg.content.startswith('!'):
                    continue
                if msg.author == self.user:
                    conversation_log.append({
                        "role": "assistant",
                        "content": msg.content,
                        "name": msg.author.name.replace(' ', '_').replace(r'[^\w\s]', '')
                    })
                elif msg.author == message.author:
                    conversation_log.append({
                        "role": "user",
                        "content": msg.content,
                        "name": message.author.name.replace(' ', '_').replace(r'[^\w\s]', '')
                    })
            
            # Reverse the conversation log to get chronological order
            conversation_log.reverse()
            
            try:
                # Use the OM1 runtime to generate a response
                print("Attempting to generate response...")
                print(f"Conversation log: {conversation_log}")
                response = await self.runtime.generate_response(conversation_log)
                print(f"Response received: {response}")
                await message.reply(response)
            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()
                print(f"Error: {e}")
                print(f"Full traceback:\n{error_traceback}")
                await message.reply(f"Error processing request: `{str(e)}`")

async def run_discord_bot(runtime):
    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True
    
    channel_id = os.getenv('CHANNEL_ID')
    
    # Create the bot instance
    bot = DiscordBot(runtime, channel_id, intents=intents)
    
    # Start the bot
    token = os.getenv('DISCORD_TOKEN')
    await bot.start(token)

@app.command()
def start(config_name: str, debug: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)

    # Load configuration
    config = load_config(config_name)
    runtime = CortexRuntime(config)
    
    global runtime_instance
    runtime_instance = runtime

    # Start the runtime and Discord bot together
    async def main():
        discord_task = asyncio.create_task(run_discord_bot(runtime))
        await asyncio.gather(discord_task)
    
    # Run the main async function
    asyncio.run(main())

if __name__ == "__main__":
    dotenv.load_dotenv()
    app()