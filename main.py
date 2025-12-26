from email import message_from_file
from operator import truediv

import discord
from discord.ext import commands
import random
import logging
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
import webserver

load_dotenv()
token = os.getenv('discord_token')

groq_client = AsyncOpenAI(
    api_key=os.getenv('GROQ_API_KEY'),
    base_url="https://api.groq.com/openai/v1"
)

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.members = True
intents.presences = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

conversation_history = {}
MAX_HISTORY = 12
assignrole = "agartha"
ranwords = []


def get_history(channel_id):
    if channel_id not in conversation_history:
        conversation_history[channel_id] = []
    return conversation_history[channel_id]


def add_to_history(channel_id, role, content):
    history = get_history(channel_id)
    history.append({"role": role, "content": content})

    # Trim history to prevent it from growing forever and hitting token limits
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]  # Keep only the most recent
    conversation_history[channel_id] = history

@bot.event
async def on_ready():
    print('halo bot online')
    global ranwords
    try:
        with open('random_words.txt', 'r', encoding='utf-8') as f:
            ranwords = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(ranwords)} random words.")

    except FileNotFoundError as e:
        print(f"Error: {e.filename} not found")


@bot.event
async def on_member_join(member):
    await member.send(f"welcome to the server {member.name}")


@bot.event
async def on_message(message):
    responded = False
    if message.author == bot.user:
        return

    if not responded and ranwords:
        if random.randint(1, 5) == 1:  # 1 in 20 chance
            random_word = random.choice(ranwords)
            await message.channel.send(random_word)
            responded = True

    SYSTEM_PROMPT = """
    You are otenz, you are chaotic, blunt and problematic
    - Always be unpredictable, sometimes very serious, sometimes off topic and unserious
    - Never use emojis
    - Use of grammar is also random, have yourself be extremely formal once, then make immense mistake with no uppercase other times
    - If someone says something dumb, point it out, unpredictability rule applies here too so dont hesitate to point out someone thats completely right and justify that what they say is wrong.
    - Stay in character — you're part of the community, not a generic assistant.
    - Keep responses short (2-15 words)
    - You can swear whenever you want
    - Reference inside jokes like "panda is Noham", "67", "Edin Dzeko will be the next Ballon D'Or", whenever you want
    - Dont hesitate to switch vibes whithin a same answer (first half serious, other half unserious, et caetera)
    """

    if bot.user in message.mentions and not responded:
        async with message.channel.typing():
            try:
                # Clean user input (remove mention)
                user_content = message.content.replace(f"<@{bot.user.id}>", "").strip()
                if not user_content:
                    user_content = "hey"  # Fallback if just mentioned

                channel_id = message.channel.id

                # Load system prompt + past conversation
                history = get_history(channel_id)

                # Build messages: system prompt first, then history, then new user message
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                messages.extend(history)  # Add previous exchanges
                messages.append({"role": "user", "content": user_content})

                # Call Groq with full context
                response = await groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    max_tokens=600,
                    temperature=0.8,
                    top_p=0.9
                )

                ai_reply = response.choices[0].message.content.strip()

                # Optional: truncate long replies
                if len(ai_reply) > 2000:
                    ai_reply = ai_reply[:1997] + "..."

                await message.channel.send(ai_reply)

                # === SAVE TO MEMORY ===
                # Save user's message
                add_to_history(channel_id, "user", user_content)
                # Save bot's reply
                add_to_history(channel_id, "assistant", ai_reply)

            except Exception as e:
                await message.channel.send(f"bruh my brain broke: {str(e)}")

    await bot.process_commands(message)

@bot.command()
async def forget(ctx):
    if ctx.channel.id in conversation_history:
        del conversation_history[ctx.channel.id]
    await ctx.send("Reset successful.")

@bot.command()
async def assign(ctx):
    role = discord.utils.get(ctx.guild.roles, name=assignrole)
    if role:
        await ctx.author.add_roles(role)
        await ctx.send(f"{ctx.author.mention} welcome to agartha.")

@bot.command()
async def removerole(ctx):
    role = discord.utils.get(ctx.guild.roles, name=assignrole)
    if role:
        await ctx.author.remove_roles(role)
        await ctx.send(f"{ctx.author.mention} just betrayed agartha")

webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)

