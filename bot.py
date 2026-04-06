import discord
from discord.ext import commands
import os
from flask import Flask
import threading

# Токен из переменной окружения Render
TOKEN = os.getenv('DISCORD_TOKEN')

# Настройки бота
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Простейшая команда ---
@bot.command()
async def ping(ctx):
    await ctx.send('Pong! 🏓')

# --- Событие on_ready для проверки подключения ---
@bot.event
async def on_ready():
    print(f'✅ Бот {bot.user} подключился!')
    print(f'📡 На серверах: {len(bot.guilds)}')

# --- Flask сервер для Render ---
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

# --- Запуск ---
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
