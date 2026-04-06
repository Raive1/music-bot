import discord
from discord.ext import commands
import os
from flask import Flask
import threading

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Тестовая команда ---
@bot.command()
async def test(ctx):
    await ctx.send("✅ Бот работает! Команда test получена.")

# --- Событие on_ready ---
@bot.event
async def on_ready():
    print(f'✅ Бот {bot.user} подключился к Discord!')
    print(f'📡 На серверах: {len(bot.guilds)}')

# --- Событие on_message для логов ---
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    print(f'📩 Сообщение: "{message.content}" от {message.author}')
    await bot.process_commands(message)

# --- Flask сервер ---
app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
