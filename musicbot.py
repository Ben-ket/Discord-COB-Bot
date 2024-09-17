import asyncio
import re
import urllib.request
import urllib.parse
import random
import aiohttp

import discord
import yt_dlp
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()
discord_token = os.environ.get("TOKEN")
spotify_client_secret = os.environ.get("Spotify_Secret")

spotify_client_id = '35ed4bec7ee8456cba26c34e5c7710d4'


# Set up Spotify credentials
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=spotify_client_id, client_secret=spotify_client_secret))

queues = {}  # A dictionary to hold the queues for each server
queue_titles = {}  # A dictionary to hold the queue titles for each server


async def searchVid(prompt):
    search = urllib.parse.quote(prompt)
    url = f"https://www.youtube.com/results?search_query={search}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html_content = await response.text()
            video_ids = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})",
                                   html_content)
            if not video_ids:
                raise ValueError("No video IDs found for the search query.")
            url_used = "https://www.youtube.com/watch?v=" + video_ids[0]
            return url_used


def handle_spotify_url(url):
    if "track" in url:
        track_id = re.search(r"track/([a-zA-Z0-9]+)", url).group(1)
        track_info = sp.track(track_id)
        track_name = track_info['name']
        artist_name = track_info['artists'][0]['name']
        return f"{track_name} {artist_name}"
    elif "playlist" in url:
        playlist_id = re.search(r"playlist/([a-zA-Z0-9]+)", url).group(1)
        playlist_info = sp.playlist(playlist_id)
        track_names = []
        for item in playlist_info['tracks']['items']:
            track = item['track']
            track_name = track['name']
            artist_name = track['artists'][0]['name']
            track_names.append(f"{track_name} {artist_name}")
        return track_names


async def run_bot():
    load_dotenv()
    TOKEN = discord_token
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    voice_clients = {}
    yt_dl_options = {"format": "bestaudio/best", "nocheckcertificate": True}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)
    ffmpeg_options = {
        'before_options':
        '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -filter:a "volume=0.25"'
    }

    async def play_next_in_queue(guild_id):
        if guild_id not in queues or not queues[guild_id]:
            return

        url = queues[guild_id].pop(0)
        global title
        title = queue_titles[guild_id].pop(0)


        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(
                None, lambda: ytdl.extract_info(url, download=False))
            song = data['url']
            player = discord.FFmpegOpusAudio(song, **ffmpeg_options)
            voice_clients[guild_id].play(
                player,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    play_next_in_queue(guild_id), loop))
        except Exception as e:
            print(f"Error playing the next song: {e}")
            await play_next_in_queue(guild_id)  # Try playing the next one

    @client.event
    async def on_ready():
        print(f'{client.user} is now jamming')

    @client.event
    async def on_message(message):
        guild_id = message.guild.id
        if message.content.startswith("?play"):
            try:
                if guild_id not in voice_clients or not voice_clients[
                        guild_id].is_connected():
                    voice_client = await message.author.voice.channel.connect()
                    voice_clients[guild_id] = voice_client
                else:
                    voice_client = voice_clients[guild_id]

                url = message.content.split()[1]
                if guild_id not in queues:
                    queues[guild_id] = []
                    queue_titles[guild_id] = []

                if "spotify" in url:
                    track_or_playlist = handle_spotify_url(url)
                    if isinstance(track_or_playlist, list):
                        youtube_urls = await asyncio.gather(
                            *[searchVid(track) for track in track_or_playlist])
                        queues[guild_id].extend(youtube_urls)
                        queue_titles[guild_id].extend(track_or_playlist)
                        embed = discord.Embed(
                            title="Spotify Playlist Added",
                            description=
                            "The playlist has been added to the queue.",
                            color=discord.Color.green())
                        await message.channel.send(embed=embed)
                    else:
                        youtube_url = await searchVid(track_or_playlist)
                        queues[guild_id].append(youtube_url)
                        queue_titles[guild_id].append(track_or_playlist)
                        embed = discord.Embed(
                            title="Spotify Track Added",
                            description=f"Added to queue: {track_or_playlist}",
                            color=discord.Color.green())
                        await message.channel.send(embed=embed)
                else:
                    result_string = " ".join(message.content.split()[1:])
                    youtube_url = await searchVid(result_string)
                    queues[guild_id].append(youtube_url)
                    queue_titles[guild_id].append(result_string)
                    embed = discord.Embed(
                        title="YouTube Video Added",
                        description=f"Added to queue: {result_string}",
                        color=discord.Color.green())
                    await message.channel.send(embed=embed)

                if not voice_client.is_playing():
                    await play_next_in_queue(guild_id)

            except Exception as e:
                print(e)

        elif message.content.startswith("?queue"):
            if guild_id in queues and queues[guild_id]:
                queue_list = "\n".join([
                    f"{i+1}. {title}"
                    for i, title in enumerate(queue_titles[guild_id])
                ])
                embed = discord.Embed(title="Current Queue",
                                      description=f"**Queue:**\n{queue_list}",
                                      color=discord.Color.blue())
                await message.channel.send(embed=embed)
            else:
                embed = discord.Embed(title="Queue Status",
                                      description="The queue is empty.",
                                      color=discord.Color.red())
                await message.channel.send(embed=embed)

        elif message.content.startswith("?skip"):
            if guild_id in voice_clients and voice_clients[guild_id].is_playing():
                current_song_title = queue_titles[guild_id][0] if queues[guild_id] else "Unknown"
                next_title = title
                if next_title:
                    embed = discord.Embed(
                        title="Song Skipped",
                        description=f"Next Song: {current_song_title}",
                        color=discord.Color.orange())
                else:
                    embed = discord.Embed(
                        title="Song Skipped",
                        description=f"Skipping the current song. The queue is now empty.",
                        color=discord.Color.orange())
                voice_clients[guild_id].stop()
                await message.channel.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="No Song Playing",
                    description="No song is currently playing.",
                    color=discord.Color.red())
                await message.channel.send(embed=embed)

        elif message.content.startswith("?pause"):
            try:
                voice_clients[guild_id].pause()
                embed = discord.Embed(title="Song Paused",
                                      description="The song has been paused.",
                                      color=discord.Color.orange())
                await message.channel.send(embed=embed)
            except Exception as e:
                print(e)

        elif message.content.startswith("?resume"):
            try:
                voice_clients[guild_id].resume()
                embed = discord.Embed(title="Song Resumed",
                                      description="The song has been resumed.",
                                      color=discord.Color.green())
                await message.channel.send(embed=embed)
            except Exception as e:
                print(e)

        elif message.content.startswith("?stop"):
            try:
                if guild_id in voice_clients:
                    if voice_clients[guild_id].is_playing():
                        voice_clients[guild_id].stop()
                    await voice_clients[guild_id].disconnect()
                    queues[guild_id] = []
                    queue_titles[guild_id] = []
                    embed = discord.Embed(
                        title="Playback Stopped",
                        description=
                        "Playback stopped and disconnected from the voice channel. Queue cleared.",
                        color=discord.Color.red())
                    await message.channel.send(embed=embed)
            except Exception as e:
                print(e)

        elif message.content.startswith("?shuffle"):
            if guild_id in queues and queues[guild_id]:
                # Extract the first track and the rest of the queue
                first_track = queues[guild_id][0]
                first_title = queue_titles[guild_id][0]
                remaining_tracks = queues[guild_id][1:]
                remaining_titles = queue_titles[guild_id][1:]

                # Shuffle the remaining tracks
                combined = list(zip(remaining_tracks, remaining_titles))
                random.shuffle(combined)
                shuffled_tracks, shuffled_titles = zip(*combined) if combined else ([], [])

                # Reassemble the queue with the first track followed by the shuffled tracks
                queues[guild_id] = [first_track] + list(shuffled_tracks)
                queue_titles[guild_id] = [first_title] + list(shuffled_titles)

                embed = discord.Embed(
                    title="Queue Shuffled",
                    description="The queue has been shuffled, but the first track remains in place.",
                    color=discord.Color.purple())
                await message.channel.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="Queue Status",
                    description="The queue is empty or does not exist.",
                    color=discord.Color.red())
                await message.channel.send(embed=embed)

    await client.start(TOKEN)


def run():
    asyncio.run(run_bot())


if __name__ == "__main__":
    run()
