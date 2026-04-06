import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
from dotenv import load_dotenv

# Загружаем токен из файла .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Настройки бота
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

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

# Очередь песен (словарь: guild_id -> список словарей с информацией о треках)
queues = {}

def get_queue(ctx):
    """Получить очередь для текущего сервера"""
    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []
    return queues[guild_id]

def search_youtube(query):
    """Ищет видео на YouTube и возвращает URL и название"""
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
    """Воспроизводит следующий трек из очереди"""
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
        # Очередь пуста, бот отключается через 60 секунд бездействия
        await ctx.send("📭 Очередь пуста. Отключаюсь через 60 секунд бездействия...")
        await asyncio.sleep(60)
        if ctx.voice_client and not ctx.voice_client.is_playing():
            await ctx.voice_client.disconnect()
            await ctx.send("👋 Отключился из-за бездействия")

@bot.command()
async def join(ctx):
    """Бот заходит в ваш голосовой канал"""
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
    """Добавляет песню в очередь и начинает играть, если ничего не играет"""
    # Проверяем, в голосовом ли канаде
    if not ctx.voice_client:
        await ctx.invoke(join)
    
    await ctx.send(f"🔍 Ищу: **{query}**...")
    
    # Ищем аудио
    url, title = await asyncio.to_thread(search_youtube, query)
    
    if url is None:
        await ctx.send("❌ Не удалось найти трек. Попробуйте другое название или ссылку.")
        return
    
    # Добавляем трек в очередь
    queue = get_queue(ctx)
    queue.append({'url': url, 'title': title})
    
    # Если ничего не играет, начинаем воспроизведение
    if not ctx.voice_client.is_playing():
        next_track = queue.pop(0)
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        source = discord.FFmpegPCMAudio(next_track['url'], **ffmpeg_options)
        
        def after_playing(error):
            if error:
                print(f"Ошибка воспроизведения: {error}")
            asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        
        ctx.voice_client.play(source, after=after_playing)
        await ctx.send(f"🎵 Сейчас играет: **{next_track['title']}**")
    else:
        await ctx.send(f"➕ Добавлено в очередь: **{title}** (позиция {len(queue)})")

@bot.command()
async def skip(ctx):
    """Пропускает текущий трек и начинает следующий из очереди"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Трек пропущен")
    else:
        await ctx.send("❌ Сейчас ничего не играет")

@bot.command()
async def queue(ctx):
    """Показывает текущую очередь песен"""
    queue = get_queue(ctx)
    if len(queue) == 0:
        await ctx.send("📭 Очередь пуста")
    else:
        # Показываем первые 10 треков в очереди
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
    """Останавливает музыку, очищает очередь и отключает бота"""
    if ctx.voice_client:
        # Очищаем очередь
        guild_id = ctx.guild.id
        if guild_id in queues:
            queues[guild_id].clear()
        
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Отключаюсь... Очередь очищена")
    else:
        await ctx.send("❌ Я не в голосовом канале!")

@bot.command()
async def pause(ctx):
    """Ставит музыку на паузу"""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸ Пауза")
    else:
        await ctx.send("❌ Сейчас ничего не играет")

@bot.command()
async def resume(ctx):
    """Продолжает играть после паузы"""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶ Продолжаю")
    else:
        await ctx.send("❌ Музыка не на паузе")

@bot.command()
async def clear(ctx):
    """Очищает очередь, не останавливая текущую музыку"""
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

# Запускаем бота
if __name__ == "__main__":
    bot.run(TOKEN)