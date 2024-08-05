"""
Copyright © Dino Horvat (Tremmert) 2024-Present - https://github.com/DinoHorvat96
Description:
A simple bot which tracks the download progress of Sonarr & Radarr instances and reports their status to a Discord channel

Version: 1.0.0
"""

import os
import logging
import discord
import requests
from discord.ext import tasks, commands
from dotenv import load_dotenv
from datetime import datetime, timezone


async def delete_all_messages(channel):
    async for message in channel.history(limit=100):  # Adjust limit as needed
        try:
            await message.delete()
        except discord.Forbidden:
            print("Bot does not have permission to delete messages.")
            break
        except discord.HTTPException as e:
            print(f"Failed to delete message: {e}")


def format_progress_bar(size, sizeleft, bar_length=20):
    try:
        size = int(size)
        sizeleft = int(sizeleft)
        progress = size - sizeleft
        percentage = (progress / size) * 100
        filled_length = int(bar_length * progress // size)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        return f"[{bar}] {percentage:.1f}%"
    except (ValueError, ZeroDivisionError):
        return "Progress unavailable"


def query_sonarr(ip, port, api_key, app_title):
    headers = {"X-Api-Key": api_key}
    endpoint = f"http://{ip}:{port}/api/v3/queue/details?includeSeries=true&includeEpisode=true"
    response = requests.get(endpoint, headers=headers)
    json_data = response.json()

    embeds = []
    for item in json_data:
        # Extract fields from the main data
        main_title = item.get("title")
        status = item.get("status")
        timeleft = item.get("timeleft", "N/A")
        size = item.get("size", "N/A")
        sizeleft = item.get("sizeleft", "N/A")
        error_message = item.get("errorMessage", None)

        # Extract and format estimatedCompletionTime
        estimatedCompletionTime = item.get("estimatedCompletionTime", "N/A")
        try:
            est_time = datetime.fromisoformat(estimatedCompletionTime.replace("Z", "+00:00"))
            formatted_time = est_time.strftime("%d.%m.%Y %H:%M:%S")
        except ValueError:
            formatted_time = estimatedCompletionTime

        # Create the progress bar
        progress_bar = format_progress_bar(size, sizeleft)

        # Extract fields from the nested "series" object
        series = item.get("series", {})
        images = series.get("images", [])
        webimage = None
        for image in images:
            if image.get("coverType") == "poster":
                webimage = image.get("remoteUrl")
                break

        # Extract fields from the nested "episode" object
        episode = item.get("episode", {})
        episode_title = episode.get("title")
        season_number = episode.get("seasonNumber")
        episode_number = episode.get("episodeNumber")

        # Create an embed
        embed = discord.Embed(title=main_title,
                              colour=0x00b0f4,
                              timestamp=datetime.now(timezone.utc))
        embed.set_author(name=app_title)
        embed.add_field(name="Episode Title", value=episode_title, inline=True)
        embed.add_field(name="Season Number", value=season_number, inline=True)
        embed.add_field(name="Episode Number", value=episode_number, inline=True)
        embed.add_field(name="Time Left", value=timeleft, inline=True)
        embed.add_field(name="Estimated Completion Time", value=formatted_time, inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Progress", value=progress_bar, inline=False)
        if error_message:
            embed.add_field(name="Error message", value=error_message, inline=False)
        if webimage:
            embed.set_thumbnail(url=webimage)

        embeds.append(embed)
    return embeds


def query_radarr(ip, port, api_key, app_title):
    headers = {"X-Api-Key": api_key}
    endpoint = f"http://{ip}:{port}/api/v3/queue/details?includeMovie=true"
    response = requests.get(endpoint, headers=headers)
    json_data = response.json()

    embeds = []
    for item in json_data:
        # Extract fields from the main data
        main_title = item.get("title")
        status = item.get("status")
        timeleft = item.get("timeleft", "N/A")
        size = item.get("size", "N/A")
        sizeleft = item.get("sizeleft", "N/A")
        error_message = item.get("errorMessage", None)

        # Extract and format estimatedCompletionTime
        estimatedCompletionTime = item.get("estimatedCompletionTime", "N/A")
        try:
            est_time = datetime.fromisoformat(estimatedCompletionTime.replace("Z", "+00:00"))
            formatted_time = est_time.strftime("%d.%m.%Y %H:%M:%S")
        except ValueError:
            formatted_time = estimatedCompletionTime

        # Create the progress bar
        progress_bar = format_progress_bar(size, sizeleft)

        # Extract fields from the nested "movie" object
        movie = item.get("movie", {})
        images = movie.get("images", [])
        webimage = None
        for image in images:
            if image.get("coverType") == "poster":
                webimage = image.get("remoteUrl")
                break

        # Create an embed
        embed = discord.Embed(title=main_title,
                              colour=0xbd5b00,
                              timestamp=datetime.now(timezone.utc))
        embed.set_author(name=app_title)
        embed.add_field(name="Time Left", value=timeleft, inline=True)
        embed.add_field(name="Estimated Completion Time", value=formatted_time, inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Progress", value=progress_bar, inline=False)
        if error_message:
            embed.add_field(name="Error message", value=error_message, inline=False)
        if webimage:
            embed.set_thumbnail(url=webimage)

        embeds.append(embed)
    return embeds


def split_embeds(embeds, max_embeds=10):
    # Split embeds into chunks of max_embeds each
    return [embeds[i:i + max_embeds] for i in range(0, len(embeds), max_embeds)]


async def send_default_message(channel):
    # Send a default message indicating nothing is being downloaded
    default_message = await channel.send("Nothing is being downloaded at the moment. :)")
    return default_message


async def handle_messages(channel, embeds, default_message=None):
    global bot_messages
    if not embeds:
        if not default_message:
            default_message = await send_default_message(channel)
        if bot_messages:
            # If there are messages to delete, delete them
            for msg in bot_messages:
                await msg.delete()
            bot_messages = [default_message]
    else:
        if default_message:
            await default_message.delete()
        # Combine all embeds
        split_embed_chunks = split_embeds(embeds)
        for chunk in split_embed_chunks:
            if bot_messages:
                # Update existing messages if any
                for i, msg in enumerate(bot_messages):
                    if i < len(split_embed_chunks):
                        await msg.edit(embeds=chunk)
                    else:
                        # If there are more messages than chunks, delete the extra messages
                        await msg.delete()
                bot_messages = bot_messages[:len(split_embed_chunks)]
            # Add new messages if needed
            for chunk in split_embed_chunks[len(bot_messages):]:
                msg = await channel.send(embeds=chunk)
                bot_messages.append(msg)
    return default_message


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))

SONARR_IP = os.getenv('SONARR_IP')
SONARR_PORT = os.getenv('SONARR_PORT')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')
SONARR_TITLE = os.getenv('SONARR_TITLE')

SONARR_IP_ANIME = os.getenv('SONARR_IP_ANIME')
SONARR_PORT_ANIME = os.getenv('SONARR_PORT_ANIME')
SONARR_API_KEY_ANIME = os.getenv('SONARR_API_KEY_ANIME')
SONARR_TITLE_ANIME = os.getenv('SONARR_TITLE_ANIME')

RADARR_IP = os.getenv('RADARR_IP')
RADARR_PORT = os.getenv('RADARR_PORT')
RADARR_API_KEY = os.getenv('RADARR_API_KEY')
RADARR_TITLE = os.getenv('RADARR_TITLE')

RADARR_IP_ANIME = os.getenv('RADARR_IP_ANIME')
RADARR_PORT_ANIME = os.getenv('RADARR_PORT_ANIME')
RADARR_API_KEY_ANIME = os.getenv('RADARR_API_KEY_ANIME')
RADARR_TITLE_ANIME = os.getenv('RADARR_TITLE_ANIME')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
client = commands.Bot(command_prefix='/', intents=intents)
bot_messages = []  # Placeholder for the bot's messages
default_message = None


@client.event
async def on_ready():
    global bot_messages, default_message
    print(f'{client.user} has connected to Discord!')
    channel = client.get_channel(DISCORD_CHANNEL_ID)

    if channel:
        # Delete all messages in the channel
        await delete_all_messages(channel)

        # Fetch data from both Sonarr and Radarr instances
        embeds = []
        embeds += query_sonarr(SONARR_IP, SONARR_PORT, SONARR_API_KEY, SONARR_TITLE)
        embeds += query_sonarr(SONARR_IP_ANIME, SONARR_PORT_ANIME, SONARR_API_KEY_ANIME, SONARR_TITLE_ANIME)
        embeds += query_radarr(RADARR_IP, RADARR_PORT, RADARR_API_KEY, RADARR_TITLE)
        embeds += query_radarr(RADARR_IP_ANIME, RADARR_PORT_ANIME, RADARR_API_KEY_ANIME, RADARR_TITLE_ANIME)

        # Handle messages and default message
        default_message = await handle_messages(channel, embeds)
        # Start the task to update the messages every x minutes
        update_messages.start()
    else:
        print("Channel not found!")


@tasks.loop(minutes=1)  # Task to run every x minutes
async def update_messages():
    global bot_messages, default_message
    channel = client.get_channel(DISCORD_CHANNEL_ID)

    if channel:
        # Fetch data from Sonarr & Radarr instances
        embeds = []
        embeds += query_sonarr(SONARR_IP, SONARR_PORT, SONARR_API_KEY, SONARR_TITLE)
        embeds += query_sonarr(SONARR_IP_ANIME, SONARR_PORT_ANIME, SONARR_API_KEY_ANIME, SONARR_TITLE_ANIME)
        embeds += query_radarr(RADARR_IP, RADARR_PORT, RADARR_API_KEY, RADARR_TITLE)
        embeds += query_radarr(RADARR_IP_ANIME, RADARR_PORT_ANIME, RADARR_API_KEY_ANIME, RADARR_TITLE_ANIME)

        # Handle messages and default message
        default_message = await handle_messages(channel, embeds, default_message)


@client.tree.command(name="refresh", description="Refresh the current status of downloads")
async def refresh(interaction: discord.Interaction):
    global update_messages, default_message, bot_messages

    await interaction.response.send_message("Refreshing data...")

    if update_messages.is_running():
        update_messages.stop()

    channel = client.get_channel(DISCORD_CHANNEL_ID)

    if channel:
        await delete_all_messages(channel)

        embeds = []
        embeds += query_sonarr(SONARR_IP, SONARR_PORT, SONARR_API_KEY, SONARR_TITLE)
        embeds += query_sonarr(SONARR_IP_ANIME, SONARR_PORT_ANIME, SONARR_API_KEY_ANIME, SONARR_TITLE_ANIME)
        embeds += query_radarr(RADARR_IP, RADARR_PORT, RADARR_API_KEY, RADARR_TITLE)
        embeds += query_radarr(RADARR_IP_ANIME, RADARR_PORT_ANIME, RADARR_API_KEY_ANIME, RADARR_TITLE_ANIME)

        default_message = await handle_messages(channel, embeds)
        update_messages.start()
    else:
        print("Channel not found!")


client.run(TOKEN, log_handler=None)