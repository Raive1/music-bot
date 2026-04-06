import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
from dotenv import load_dotenv
import threading
from flask import Flask

# Загружаем токен
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Настройки бота
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Бот {bot.user} подключился к Discord!')
    print(f'📡 Он на {len(bot.guilds)} серверах.')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    print(f'📩 Сообщение: "{message.content}" от {message.author}')
    await bot.process_commands(message)

# Настройки для yt-dlp
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'no_warnings': True,
}

# Очередь
queues = {}

def get_queue(ctx):
    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []
    return queues[guild_id]

def search_youtube(query):
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            if 'youtube.com' in query or 'youtu.be' in query:
                info = ydl.extract_info(query, download=False)
                return info['url'], info.get('title', 'Неизвестный трек')
            else:
                info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
                return info['url'], info.get('title', 'Неизвестный трек')
        except Exception as e:
            print(f"Ошибка поиска: {e}")
            return None, None

async def play_next(ctx):
    queue = get_queue(ctx)
    if len(queue) > 0:
        next_track = queue.pop(0)
        url = next_track['url']
        title = next_track['title']
        
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        
        source = discord.FFmpegPCMAudio(url, **ffmpeg_options)
        
        def after_playing(error):
            if error:
                print(f"Ошибка воспроизведения: {error}")
            asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        
        ctx.voice_client.play(source, after=after_playing)
        await ctx.send(f"🎵 Сейчас играет: **{title}**")
    else:
        await ctx.send("📭 Очередь пуста. Отключаюсь...")
        await asyncio.sleep(60)
        if ctx.voice_client and not ctx.voice_client.is_playing():
            await ctx.voice_client.disconnect()

# --- Команды бота ---
@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()
        await ctx.send(f"✅ Подключился к каналу **{channel.name}**")
    else:
        await ctx.send("❌ Вы не в голосовом канале!")

@bot.command()
async def play(ctx, *, query):
    if not ctx.voice_client:
        await ctx.invoke(join)
    
    await ctx.send(f"🔍 Ищу: **{query}**...")
    url, title = await asyncio.to_thread(search_youtube, query)
    
    if url is None:
        await ctx.send("❌ Не удалось найти трек.")
        return
    
    queue = get_queue(ctx)
    queue.append({'url': url, 'title': title})
    
    if not ctx.voice_client.is_playing():
        next_track = queue.pop(0)
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        source = discord.FFmpegPCMAudio(next_track['url'], **ffmpeg_options)
        
        def after_playing(error):
            if error:
                print(f"Ошибка: {error}")
            asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        
        ctx.voice_client.play(source, after=after_playing)
        await ctx.send(f"🎵 Сейчас играет: **{next_track['title']}**")
    else:
        await ctx.send(f"➕ Добавлено в очередь: **{title}** (позиция {len(queue)})")

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Трек пропущен")
    else:
        await ctx.send("❌ Сейчас ничего не играет")

@bot.command()
async def queue(ctx):
    queue = get_queue(ctx)
    if len(queue) == 0:
        await ctx.send("📭 Очередь пуста")
    else:
        queue_list = []
        for i, track in enumerate(queue[:10], 1):
            queue_list.append(f"**{i}.** {track['title']}")
        embed = discord.Embed(
            title="📜 Очередь песен",
            description="\n".join(queue_list),
            color=discord.Color.blue()
        )
        if len(queue) > 10:
            embed.set_footer(text=f"и ещё {len(queue) - 10} треков...")
        await ctx.send(embed=embed)

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        guild_id = ctx.guild.id
        if guild_id in queues:
            queues[guild_id].clear()
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Отключаюсь... Очередь очищена")
    else:
        await ctx.send("❌ Я не в голосовом канале!")

@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸ Пауза")
    else:
        await ctx.send("❌ Сейчас ничего не играет")

@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶ Продолжаю")
    else:
        await ctx.send("❌ Музыка не на паузе")

@bot.command()
async def clear(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues:
        count = len(queues[guild_id])
        queues[guild_id].clear()
        await ctx.send(f"🗑️ Очередь очищена (удалено {count} треков)")
    else:
        await ctx.send("📭 Очередь и так пуста")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❓ Неизвестная команда. Доступные команды: `!play`, `!skip`, `!queue`, `!pause`, `!resume`, `!stop`, `!clear`, `!join`")
    else:
        print(f"Ошибка: {error}")

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
