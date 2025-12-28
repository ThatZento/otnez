# ========================================
# Discord Bot: otnez v1.1.0
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

# Load discord API key
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
# Load both Groq API keys + openai keys
GROQ_API_KEY = os.getenv('GROQ_API_KEY')          # Primary key
if not GROQ_API_KEY:
    print("ERROR: GROQ_API_KEY not found in .env!")
    exit(1)

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

# Initial client (Groq primary)
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
    print('otneZ bot is now online! v1.1.0')

    global random_words
    try:
        with open(RANDOM_WORDS_FILE, 'r', encoding='utf-8') as file:
            random_words = [line.strip() for line in file if line.strip()]
        print(f"Loaded {len(random_words)} random words from {RANDOM_WORDS_FILE}.")
    except FileNotFoundError:
        print(f"Warning: {RANDOM_WORDS_FILE} not found — random word feature disabled.")


@bot.event
async def on_member_join(member):
    """Sends a welcome DM when someone joins the server."""
    await member.send(f"welcome to the server {member.name}")


@bot.event
async def on_message(message):
    """Handles every incoming message with smart AI + command detection."""
    if message.author == bot.user:
        return

    # ------------------------------------------------------------------
    # 1/50 random word — works everywhere
    # ------------------------------------------------------------------
    if random_words and random.randint(1, 50) == 1:
        random_word = random.choice(random_words)
        await message.channel.send(random_word)

    # ------------------------------------------------------------------
    # Check if this could be a command (only for our known commands)
    # ------------------------------------------------------------------
    content = message.content.strip()
    known_commands = ['forget', 'assign', 'removerole']  # add more if you create new ones

    is_potential_command = False
    for cmd in known_commands:
        full_cmd = f'!{cmd}'
        # Case 1: Starts with !forget, !assign, etc. (classic)
        if content.startswith(full_cmd):
            is_potential_command = True
            break
        # Case 2: Ends with ! and the part before is exactly the command (e.g. "forget!")
        # This allows forgiving input like "forget !" or "  assign!"
        if content.endswith('!'):
            stripped = content[:-1].strip()  # remove trailing ! and whitespace
            if stripped.lower() == cmd:
                is_potential_command = True
                break

    # ------------------------------------------------------------------
    # Decide if we should trigger AI response
    # ------------------------------------------------------------------
    # AI responds if:
    # - It's a DM (guild is None)
    # - OR it's a server AND bot is mentioned
    # BUT NOT if it's a valid command (to avoid double-processing/tokens)
    should_respond_with_ai = (
            (message.guild is None or bot.user in message.mentions)
            and not is_potential_command
    )

    if should_respond_with_ai:
        async with message.channel.typing():
            try:
                # Clean user input
                user_content = message.content
                if message.guild and bot.user in message.mentions:
                    user_content = message.content.replace(f"<@{bot.user.id}>", "").strip()

                if not user_content.strip():
                    user_content = "hey"

                channel_id = message.channel.id
                history = get_history(channel_id)

                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                messages.extend(history)
                messages.append({"role": "user", "content": user_content})

                # SINGLE API CALL — you control the model here
                response = await groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b",  # ← CHANGE THIS TO YOUR FREE MODEL
                    # Examples:
                    # "llama-3.3-70b-versatile"
                    # "mixtral-8x7b-32768"
                    # "gemma2-9b-it"
                    # or whatever free/no-limit model you found
                    messages=messages,
                    max_tokens=600,
                    temperature=0.8,
                    top_p=0.9
                )

                ai_reply = response.choices[0].message.content.strip()
                if len(ai_reply) > 2000:
                    ai_reply = ai_reply[:1997] + "..."

                await message.channel.send(ai_reply)

                # Save to history
                add_to_history(channel_id, "user", user_content)
                add_to_history(channel_id, "assistant", ai_reply)

            except Exception as e:
                print(f"Groq API error: {e}")
                await message.channel.send(
                    "API down... otenZ no aura today :broken_heart::broken_heart::broken_heart::broken_heart:")
                # No retry, no switch — simple failure

            except Exception as primary_error:
                # ... your existing failover code here ...
                pass
    # ------------------------------------------------------------------
    # ALWAYS process commands at the end (required by discord.py)
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
    print("Starting otneZ bot directly...")
    bot.run(DISCORD_TOKEN)