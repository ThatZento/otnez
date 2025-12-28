# otenZ Discord Bot

A fully customizable, lightweight, and extensible Discord bot built with discord.py and Groq's fast inference API.

This bot is designed as a blank-but-powerful template:  
- Per-channel conversation memory  
- Smart mention handling (requires @mention in servers, no mention needed in DMs)  
- Built-in conversation reset command  
- Easy role assignment/removal commands  
- Random surprise messages  
- Single primary + optional panic API key failover  
- External system prompt file for instant personality changes (no code edits needed)  
- Tiny Flask webserver keep-alive for 24/7 hosting on free platforms  

Everything is heavily commented and structured so you can tweak, replace, or expand any part without fighting the code.

## Features

- Responds to @mentions in servers  
- Responds to every message in DMs (no mention required)  
- Per-channel memory (resettable with !forget)  
- Simple role management (!assign / !removerole)  
- 1/50 chance random message from random_words.txt  
- External system_prompt.txt → change personality instantly  
- Optional panic API key fallback  
- Ready for Render / Railway / Fly.io / Replit (webserver.py included)

## Setup

1. Clone or download the project
2. Install dependencies  
   
   pip install -r requirements.txt
   
3. Create a `.env` file in the root folder:
   
   DISCORD_TOKEN=your_bot_token_here
   
   GROQ_API_KEY=your_groq_api_key_here

   PANIC_API_GROQ=your_optional_backup_key_here  # optional

   
5. (Optional) Edit `system_prompt.txt` → this completely controls the bot's personality  
6. (Optional) Edit `random_words.txt` → one surprise word/phrase per line  
7. Run locally:  
   
   python main.py
   
   Or deploy with the keep-alive web server:  
   
   python webserver.py
   

## Commands

- `!forget` → clears conversation history in the current channel  
- `!assign` → gives yourself the role defined in the code (default "agartha")  
- `!removerole` → removes that role  

Add more commands easily — the structure is ready for it.

## Customization

- Change the bot's entire personality by editing `system_prompt.txt` only  
- Swap the model in `main.py` (line 203 for main, 233 for panic)  
- Add/remove commands in `main.py`  
- Modify role name, prefix, intents, etc.
- 
The bot has no fixed theme out of the box. Make it whatever you want.

## Deployment

The included `webserver.py` runs a tiny Flask server on the port provided by most free hosts, keeping the bot alive 24/7.  
Set your start command to `python webserver.py` in Render/Railway/etc.

## Credits

by ThatZento

Enjoy building your perfect bot!
