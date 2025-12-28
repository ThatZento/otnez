# webserver.py
from flask import Flask
import threading
import os
from main import bot, DISCORD_TOKEN  # Import bot and token from main.py

app = Flask(__name__)

@app.route('/')
def home():
    return "otenZ bot is alive and brainrotting! 67"

def run_bot():
    print("Starting otenZ bot from webserver thread...")
    bot.run(DISCORD_TOKEN)

if __name__ == '__main__':
    # Start bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Run Flask web server
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)