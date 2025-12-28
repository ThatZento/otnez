# webserver.py (alternative version)
from flask import Flask
import threading
import os
from main import bot, DISCORD_TOKEN  # import your bot and token

app = Flask(__name__)

@app.route('/')
def home():
    return "bot is alive."

def run_bot():
    bot.run(DISCORD_TOKEN)

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    port = int(os.environ.get('PORT', 5000))

    app.run(host='0.0.0.0', port=port)
