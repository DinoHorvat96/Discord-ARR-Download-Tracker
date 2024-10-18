"""
Copyright © Dino Horvat (Tremmert) 2024-Present - https://github.com/DinoHorvat96
Description:
A simple bot which tracks the download progress of Sonarr & Radarr instances and reports their status to a Discord channel

Version: 1.1.9
"""

import os
import logging
import discord
import requests
from discord.ext import tasks, commands
from dotenv import load_dotenv
from datetime import datetime, timezone
import gc
import sys
import asyncio
from discord.errors import HTTPException, NotFound, Forbidden
from requests.exceptions import RequestException
import time

async def delete_all_messages(channel):
    try:
        async for message in channel.history(limit=100):
            try:
                await message.delete()
            except discord.Forbidden:
                logging.error("Bot does not have permission to delete messages.")
            except discord.errors.NotFound:
                logging.warning(f"Message with ID {message.id} not found when attempting to delete.")
    except discord.errors.DiscordException as e:
        logging.error(f"Failed to delete messages in channel {channel.id}: {e}")

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

def query_sonarr(ip, port, api_key, app_title, max_retries=5, delay=10):
    headers = {"X-Api-Key": api_key}
    endpoint = f"http://{ip}:{port}/api/v3/queue/details?includeSeries=true&includeEpisode=true"

    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(endpoint, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an error for bad status codes
            json_data = response.json()
            break  # Exit the loop if the request is successful
        except RequestException as e:
            logging.error(f"An error occurred when querying Sonarr {app_title}: {e}")
            retries += 1
            if retries < max_retries:
                logging.info(f"Retrying in {delay} seconds... ({retries}/{max_retries})")
                time.sleep(delay)
            else:
                logging.error(f"Max retries exceeded. Failed to connect to Sonarr at {ip}:{port}.")
                return []  # Return an empty list to avoid further errors

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

def query_radarr(ip, port, api_key, app_title, max_retries=5, delay=10):
    headers = {"X-Api-Key": api_key}
    endpoint = f"http://{ip}:{port}/api/v3/queue/details?includeMovie=true"

    retries = 0
    while retries < max_retries:
        try:
            response = requests.get(endpoint, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an error for bad status codes
            json_data = response.json()
            break  # Exit the loop if the request is successful
        except RequestException as e:
            logging.error(f"An error occurred when querying Radarr {app_title}: {e}")
            retries += 1
            if retries < max_retries:
                logging.info(f"Retrying in {delay} seconds... ({retries}/{max_retries})")
                time.sleep(delay)
            else:
                logging.error(f"Max retries exceeded. Failed to connect to Radarr at {ip}:{port}.")
                return []  # Return an empty list to avoid further errors

    embeds = []
    # Extract fields from the main data
    for item in json_data:
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
    # If there are no messages yet or no embeds to display
    if not embeds:
        if default_message:
            try:
                await default_message.edit(content="No active downloads currently.")
            except discord.errors.NotFound:
                # If the default message was not found, delete all messages and regenerate
                await delete_all_messages(channel)
                default_message = await channel.send("No active downloads currently.")
        else:
            # If no default message exists, send a new default message
            default_message = await channel.send("No active downloads currently.")
        return default_message

    # Delete all previous messages if new data exists
    if bot_messages:
        for msg in bot_messages:
            try:
                await msg.delete()
            except discord.errors.NotFound:
                logging.warning(f"Message with ID {msg.id} not found when attempting to delete.")

    # Send new messages for each embed
    bot_messages = []
    for embed in embeds:
        try:
            msg = await channel.send(embed=embed)
            bot_messages.append(msg)
        except discord.errors.HTTPException as e:
            logging.error(f"Failed to send message: {e}")

    # Clear the default message if embeds are present
    if default_message:
        try:
            await default_message.delete()
        except discord.errors.NotFound:
            logging.warning(f"Default message with ID {default_message.id} not found when attempting to delete.")

    return None  # No default message needed if embeds are present

async def handle_rate_limit(error):
    """Handles rate limit errors by pausing execution for the specified retry_after time."""
    if error.code == 429:  # 429 status code indicates a rate limit
        retry_after = error.response.json().get('retry_after')
        logging.warning(f"Rate limited. Retrying in {retry_after} seconds.")
        await asyncio.sleep(retry_after)
    else:
        logging.error(f"Unexpected error occurred: {error}")
        raise error

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

TIME_NUMERIC = int(os.getenv('TIME_NUMERIC', 15))  # Default to 15 if not provided
TIME_FORMAT = os.getenv('TIME_FORMAT', 'seconds')  # Default to 'seconds' if not provided

# Convert the TIME_FORMAT into an appropriate loop interval
if TIME_FORMAT == 'seconds':
    interval_kwargs = {'seconds': TIME_NUMERIC}
elif TIME_FORMAT == 'minutes':
    interval_kwargs = {'minutes': TIME_NUMERIC}
elif TIME_FORMAT == 'hours':
    interval_kwargs = {'hours': TIME_NUMERIC}
else:
    raise ValueError(f"Invalid TIME_FORMAT: {TIME_FORMAT}. Use 'seconds', 'minutes', or 'hours'.")

handler = logging.StreamHandler(sys.stdout)  # Log to stdout
handler.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO, handlers=[handler], format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Global variables to store the default message and bot messages
default_message = None
bot_messages = []  # Placeholder for the bot's messages

# Discord Intents setup
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
client = commands.Bot(command_prefix='/', intents=intents)

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
        # Perform garbage collection
        gc.collect()
        # Start the task to update the messages every x minutes
        update_messages.start()
    else:
        print("Channel not found!")


@tasks.loop(**interval_kwargs)  # Task to run based on environment variables TIME_NUMERIC and TIME_FORMAT
async def update_messages():
    global default_message
    channel = client.get_channel(DISCORD_CHANNEL_ID)

    if channel:
        try:
            # Fetch data from Sonarr & Radarr instances
            embeds = []
            embeds += query_sonarr(SONARR_IP, SONARR_PORT, SONARR_API_KEY, SONARR_TITLE)
            embeds += query_sonarr(SONARR_IP_ANIME, SONARR_PORT_ANIME, SONARR_API_KEY_ANIME, SONARR_TITLE_ANIME)
            embeds += query_radarr(RADARR_IP, RADARR_PORT, RADARR_API_KEY, RADARR_TITLE)
            embeds += query_radarr(RADARR_IP_ANIME, RADARR_PORT_ANIME, RADARR_API_KEY_ANIME, RADARR_TITLE_ANIME)

            # Handle the new messages, delete the old ones
            default_message = await handle_messages(channel, embeds, default_message)
            # Perform garbage collection
            gc.collect()
        except Exception as e:
            logging.error(f"An error occurred in update_messages: {e}")
    else:
        logging.error("Channel not found!")

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
