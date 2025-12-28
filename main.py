# ========================================
# Discord Bot: otnez v1.1.0
# ========================================
import os
import random
import logging
from dotenv import load_dotenv

import discord
from discord.ext import commands

from openai import AsyncOpenAI

# ========================================
# 1. Load Environment & Constants
# ========================================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PANIC_API_GROQ = os.getenv("PANIC_API_GROQ")

if not DISCORD_TOKEN:
    raise SystemExit("ERROR: DISCORD_TOKEN not found in .env")
if not GROQ_API_KEY:
    raise SystemExit("ERROR: GROQ_API_KEY not found in .env")

# Config constants
AGARTHA_ROLE_NAME = "agartha"
MAX_HISTORY = 12
SYSTEM_PROMPT_FILE = "system_prompt.txt"
RANDOM_WORDS_FILE = "random_words.txt"
MODEL = "llama-3.3-70b-versatile"

# ========================================
# 2. Load External Files (prompt & random words)
# ========================================

def load_system_prompt() -> str:
    try:
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
        print(f"System prompt loaded ({len(prompt)} chars)")
        return prompt
    except FileNotFoundError:
        raise SystemExit(f"ERROR: {SYSTEM_PROMPT_FILE} not found!")

def load_random_words() -> list[str]:
    try:
        with open(RANDOM_WORDS_FILE, "r", encoding="utf-8") as f:
            words = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(words)} random words")
        return words
    except FileNotFoundError:
        print(f"Warning: {RANDOM_WORDS_FILE} not found – random word feature disabled")
        return []

SYSTEM_PROMPT = load_system_prompt()
random_words = load_random_words()

# ========================================
# 3. Bot & Client Setup
# ========================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Logging to file
logging.basicConfig(
    handlers=[logging.FileHandler("discord.log", "w", "utf-8")],
    level=logging.DEBUG,
)

# Conversation history: {channel_id: list[dict]}
conversation_history: dict[int, list[dict]] = {}

# Groq client (starts with primary key)
groq_client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
used_panic_key = False

# ========================================
# 4. Helper Functions
# ========================================

def get_history(channel_id: int) -> list[dict]:
    if channel_id not in conversation_history:
        conversation_history[channel_id] = []
    return conversation_history[channel_id]

def add_to_history(channel_id: int, role: str, content: str):
    history = get_history(channel_id)
    history.append({"role": role, "content": content})
    # Keep only the latest entries
    if len(history) > MAX_HISTORY:
        conversation_history[channel_id] = history[-MAX_HISTORY:]

def is_potential_command(content: str) -> bool:
    """Detect both normal (!cmd) and reversed (cmd!) style commands."""
    known = ["forget", "assign", "removerole"]
    stripped = content.strip()

    # Normal prefix
    if any(stripped.startswith(f"!{cmd}") for cmd in known):
        return True

    # Reversed style: "forget!" or "  assign   !"
    if stripped.endswith("!"):
        cmd_part = stripped[:-1].strip().lower()
        if cmd_part in known:
            return True

    return False

async def send_ai_response(channel, user_content: str, history: list[dict]):
    """Centralized function to call Groq and send reply (with panic key fallback)."""
    global used_panic_key

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_content})

    try:
        response = await groq_client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=600,
            temperature=0.8,
            top_p=0.9,
        )
        reply = response.choices[0].message.content.strip()
        if len(reply) > 2000:
            reply = reply[:1997] + "..."

        await channel.send(reply)
        return reply

    except Exception as e:
        print(f"Primary Groq API failed: {e}")

        # Try panic key once
        if not used_panic_key and PANIC_API_GROQ:
            print("Switching to panic key...")
            groq_client.api_key = PANIC_API_GROQ
            used_panic_key = True

            try:
                response = await groq_client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    max_tokens=600,
                    temperature=0.8,
                    top_p=0.9,
                )
                reply = response.choices[0].message.content.strip()
                if len(reply) > 2000:
                    reply = reply[:1997] + "..."

                await channel.send(reply + "\n(panic key activated — war never stops fr)")
                return reply
            except Exception as e2:
                print(f"Panic key failed: {e2}")
                await channel.send("Both keys down... otneZ lost the war :sob:" * 7)
                return None
        else:
            await channel.send("API dead... no 3-stars today :broken_heart:" * 3)
            return None

# ========================================
# 5. Events
# ========================================

@bot.event
async def on_ready():
    print("otneZ bot is now online! v1.1.0")

@bot.event
async def on_member_join(member: discord.Member):
    try:
        await member.send(f"welcome to the server {member.name}")
    except discord.Forbidden:
        pass  # User has DMs disabled

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    # 1/50 random word anywhere
    if random_words and random.randint(1, 50) == 1:
        await message.channel.send(random.choice(random_words))

    # Decide if we should respond with AI
    is_dm = message.guild is None
    is_mentioned = bot.user in message.mentions
    is_command = is_potential_command(message.content)

    should_ai_respond = (is_dm or is_mentioned) and not is_command

    if should_ai_respond:
        async with message.channel.typing():
            # Clean mention from content
            user_content = message.content
            if is_mentioned:
                user_content = user_content.replace(f"<@{bot.user.id}>", "").strip()
            if not user_content:
                user_content = "hey"

            history = get_history(message.channel.id)

            reply = await send_ai_response(message.channel, user_content, history)

            if reply is not None:
                add_to_history(message.channel.id, "user", user_content)
                add_to_history(message.channel.id, "assistant", reply)

    # Always let commands process
    await bot.process_commands(message)

# ========================================
# 6. Commands
# ========================================

@bot.command()
async def forget(ctx: commands.Context):
    """!forget — Clears conversation history in this channel"""
    if ctx.channel.id in conversation_history:
        del conversation_history[ctx.channel.id]
    await ctx.send("Conversation history reset.")
    print(f"Memory cleared for channel {ctx.channel.id}")

@bot.command()
async def assign(ctx: commands.Context):
    """!assign — Gives the caller the agartha role"""
    role = discord.utils.get(ctx.guild.roles, name=AGARTHA_ROLE_NAME)
    if not role:
        await ctx.send("Role not found — check the name.")
        return

    await ctx.author.add_roles(role)
    await ctx.send(f"{ctx.author.mention} welcome to agartha.")

@bot.command()
async def removerole(ctx: commands.Context):
    """!removerole — Removes the agartha role from the caller"""
    role = discord.utils.get(ctx.guild.roles, name=AGARTHA_ROLE_NAME)
    if not role:
        await ctx.send("Role not found — check the name.")
        return

    await ctx.author.remove_roles(role)
    await ctx.send(f"{ctx.author.mention} just betrayed agartha")

# ========================================
# 7. Run the Bot
# ========================================

if __name__ == "__main__":
    print("Starting otneZ bot...")
    bot.run(DISCORD_TOKEN)