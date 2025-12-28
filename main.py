# ========================================
# Discord Bot: otenz v1.1.0
# ========================================
import discord
from discord.ext import commands
import random
import logging
from openai import AsyncOpenAI  # OpenAI-compatible client (Groq uses the same API format)
import os
from dotenv import load_dotenv

# Load environment variables from .env file (contains DISCORD_TOKEN and GROQ_API_KEY)
load_dotenv()

# ========================================
# Configuration & Constants
# ========================================

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Role name used for !assign and !removerole commands
AGARTHA_ROLE_NAME = "agartha"

# Maximum number of previous messages to keep in history (user + assistant pairs)
# 12 keeps context reasonable without hitting token limits too fast
MAX_HISTORY = 12

# File containing one random word/phrase per line for the 1/50 chance event
RANDOM_WORDS_FILE = 'random_words.txt'

# ========================================
# System Prompt - THIS IS THE PERSONALITY OF THE BOT
# Edit this carefully if you want to tweak behavior
# ========================================

SYSTEM_PROMPT_FILE = 'system_prompt.txt'  # Name of the file (same folder as main.py)

try:
    with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()  # Read entire file and remove extra whitespace/newlines
    print(f"System prompt loaded from {SYSTEM_PROMPT_FILE} ({len(SYSTEM_PROMPT)} characters).")
except FileNotFoundError:
    print(f"ERROR: {SYSTEM_PROMPT_FILE} not found! Bot cannot start without it.")
    exit(1)  # Stop the bot if prompt is missing
except Exception as e:
    print(f"ERROR reading system prompt: {e}")
    exit(1)

# ========================================
# Bot Setup
# ========================================

# Enable necessary intents (permissions) for the bot
intents = discord.Intents.default()
intents.members = True  # To detect member joins and role management
intents.message_content = True  # To read message content

# Create the bot with ! prefix
bot = commands.Bot(command_prefix='!', intents=intents)

# Groq client (AsyncOpenAI works because Groq API is OpenAI-compatible)
groq_client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# Simple file logging for debugging (all bot events go to discord.log)
logging.basicConfig(handlers=[logging.FileHandler('discord.log', 'w', 'utf-8')], level=logging.DEBUG)

# In-memory conversation history: {channel_id: list of {"role": ..., "content": ...}}
conversation_history = {}

# Loaded random words for the 1/50 chance reply
random_words = []


# ========================================
# Helper Functions for Conversation History
# ========================================

def get_history(channel_id: int):
    """Get or create history list for a specific channel."""
    if channel_id not in conversation_history:
        conversation_history[channel_id] = []
    return conversation_history[channel_id]


def add_to_history(channel_id: int, role: str, content: str):
    """Add a message to history and trim if too long."""
    history = get_history(channel_id)
    history.append({"role": role, "content": content})

    # Keep only the most recent exchanges to avoid token overflow
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    conversation_history[channel_id] = history


# ========================================
# Bot Events
# ========================================

@bot.event
async def on_ready():
    """Runs once when the bot successfully connects to Discord."""
    print('otenZ bot is now online! v1.1.0')

    global random_words
    try:
        with open(RANDOM_WORDS_FILE, 'r', encoding='utf-8') as f:
            random_words = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(random_words)} random words from {RANDOM_WORDS_FILE}.")
    except FileNotFoundError:
        print(f"Warning: {RANDOM_WORDS_FILE} not found — random word feature disabled.")


@bot.event
async def on_member_join(member):
    """Sends a welcome DM when someone joins the server."""
    await member.send(f"welcome to the server {member.name}")


@bot.event
async def on_message(message):
    """Handles every incoming message with smart context-aware responding."""
    # Ignore messages from the bot itself (prevents loops)
    if message.author == bot.user:
        return

    # ------------------------------------------------------------------
    # 1/50 chance random word — works everywhere (DMs and servers)
    # ------------------------------------------------------------------
    if random_words and random.randint(1, 50) == 1:
        random_word = random.choice(random_words)
        await message.channel.send(random_word)

    # ------------------------------------------------------------------
    # Decide if we should trigger the AI response
    # ------------------------------------------------------------------
    # Condition A: It's a DM (private message) → respond to everything
    # Condition B: It's a server channel BUT the bot is explicitly mentioned
    should_respond_with_ai = (
            message.guild is None  # guild is None in DMs
            or bot.user in message.mentions
    )

    if should_respond_with_ai:
        async with message.channel.typing():  # Show typing indicator
            try:
                # Clean user input
                # In DMs: no mention to remove → use full content
                # In servers: remove the @mention if present
                user_content = message.content
                if message.guild and bot.user in message.mentions:
                    user_content = message.content.replace(f"<@{bot.user.id}>", "").strip()

                # Fallback if message is empty after cleaning (e.g. just a mention)
                if not user_content.strip():
                    user_content = "hey"

                channel_id = message.channel.id

                # Build message history for Groq
                history = get_history(channel_id)
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                ]
                messages.extend(history)
                messages.append({"role": "user", "content": user_content})

                # Call Groq API
                response = await groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    max_tokens=600,
                    temperature=0.8,
                    top_p=0.9
                )

                ai_reply = response.choices[0].message.content.strip()

                # Safety: Discord max message length
                if len(ai_reply) > 2000:
                    ai_reply = ai_reply[:1997] + "..."

                await message.channel.send(ai_reply)

                # Save conversation to history
                add_to_history(channel_id, "user", user_content)
                add_to_history(channel_id, "assistant", ai_reply)

            except Exception as e:
                await message.channel.send(f"AI error (check API key/rate limits): {str(e)}")

    # ------------------------------------------------------------------
    # Always process commands (!forget, !assign, etc.) — required!
    # ------------------------------------------------------------------
    await bot.process_commands(message)


# ========================================
# Commands
# ========================================

@bot.command()
async def forget(ctx):
    """!forget — Clears the conversation history for this channel."""
    if ctx.channel.id in conversation_history:
        del conversation_history[ctx.channel.id]
    await ctx.send("Conversation history reset.")
    print(f"Memory cleared for channel {ctx.channel.id}")


@bot.command()
async def assign(ctx):
    """!assign — Gives the user the 'agartha' role."""
    role = discord.utils.get(ctx.guild.roles, name=AGARTHA_ROLE_NAME)
    if role:
        await ctx.author.add_roles(role)
        await ctx.send(f"{ctx.author.mention} welcome to agartha.")
    else:
        await ctx.send("Role not found — check the name.")


@bot.command()
async def removerole(ctx):
    """!removerole — Removes the 'agartha' role from the user."""
    role = discord.utils.get(ctx.guild.roles, name=AGARTHA_ROLE_NAME)
    if role:
        await ctx.author.remove_roles(role)
        await ctx.send(f"{ctx.author.mention} just betrayed agartha")
    else:
        await ctx.send("Role not found — check the name.")


# ========================================
# Run the Bot
# ========================================

if __name__ == '__main__':
    print("Starting otenZ bot directly...")
    bot.run(DISCORD_TOKEN)