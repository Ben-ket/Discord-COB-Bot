import asyncio
import re
import urllib.request

import discord
import yt_dlp
from dotenv import load_dotenv

discord_token = 'MTIyMzcyNTEzMTY2NzQ3MjQ2NA.GYmChj.QYr_6cyRaHKKAq0pDWFX6WpS8hrVsxVbuC8230'


def searchVid(prompt):
  search = prompt.replace(" ", "+")

  html = urllib.request.urlopen(
      f"https://www.youtube.com/results?search_query={search}")

  video_ids = re.findall(r"watch\?v=(\S{11})", html.read().decode())
  url_used = "https://www.youtube.com/watch?v=" + video_ids[0]
  return url_used


def run_bot():
  load_dotenv()
  TOKEN = discord_token
  intents = discord.Intents.default()
  intents.message_content = True
  client = discord.Client(intents=intents)

  queues = {}
  voice_clients = {}
  yt_dl_options = {"format": "bestaudio/best"}
  ytdl = yt_dlp.YoutubeDL(yt_dl_options)

  ffmpeg_options = {
      'before_options':
      '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
      'options': '-vn -filter:a "volume=0.25"'
  }

  @client.event
  async def on_ready():
    print(f'{client.user} is now jamming')

  @client.event
  async def on_message(message):
    if message.content.startswith("?play"):
      try:
        voice_client = await message.author.voice.channel.connect()
        voice_clients[voice_client.guild.id] = voice_client
      except Exception as e:
        print(e)

      try:
        if "https" in message.content:
          url, result_string = message.content.split()[1]
          
        else:
          result_string = " ".join(
              [str(element) for element in message.content.split()[1:]])
          url = searchVid(result_string)
        loop = asyncio.get_event_loop()
        await message.channel.send(f"Searching For : {result_string}")

        data = await loop.run_in_executor(
            None, lambda: ytdl.extract_info(url, download=False))

        song = data['url']
        player = discord.FFmpegOpusAudio(song, **ffmpeg_options)
        

        voice_clients[message.guild.id].play(player)
       

        await message.channel.send(f"**🎵----Playing----🎵**\n{url}")

      except Exception as e:
        print(e)

    if message.content.startswith("?pause"):
      try:
        voice_clients[message.guild.id].pause()
      except Exception as e:
        print(e)

    if message.content.startswith("?resume"):
      try:
        voice_clients[message.guild.id].resume()
      except Exception as e:
        print(e)

    if message.content.startswith("?stop"):
      try:
        voice_clients[message.guild.id].stop()
        await voice_clients[message.guild.id].disconnect()
      except Exception as e:
        print(e)
    if "nigger" in message.content.lower() or "nigga" in message.content.lower(
    ):
      await message.channel.send("⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫")

  client.run(TOKEN)
