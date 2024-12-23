"""
Copyright © Dino Horvat (Tremmert) 2024-Present - https://github.com/DinoHorvat96
Description:
A simple bot which tracks the download progress of Sonarr & Radarr instances and reports their status to a Discord channel

Version: 1.2.0
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


def calculate_speed(size_left_gb, time_left_minutes):
    if time_left_minutes <= 0:
        return "N/A"
    # Convert size from GB to MB (1 GB = 1024 MB)
    size_left_mb = size_left_gb * 1024
    # Convert time from minutes to seconds
    time_left_seconds = time_left_minutes * 60
    # Calculate speed in MB/s
    speed_mb_per_sec = size_left_mb / time_left_seconds
    # Format speed to MB/s
    return f"{speed_mb_per_sec:.2f} MB/s"

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
        sizeleft_gb = item.get("sizeleft", 0) / (1024 ** 3)  # Convert bytes to GB
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

        # Convert timeleft to minutes safely
        if timeleft != "N/A" and ':' in timeleft:
            try:
                time_parts = [int(part) for part in timeleft.split(':')]
                time_left_minutes = time_parts[0] * 60 + time_parts[1] + (time_parts[2] / 60)
            except (ValueError, IndexError):
                time_left_minutes = 0  # Default to 0 if parsing fails
        else:
            time_left_minutes = 0  # Default to 0 for "N/A" or invalid formats

        # Calculate download speed if time_left_minutes > 0
        download_speed = calculate_speed(sizeleft_gb, time_left_minutes) if time_left_minutes > 0 else "N/A"

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
        embed.add_field(name="Download Speed", value=download_speed, inline=False)
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
        sizeleft_gb = item.get("sizeleft", 0) / (1024 ** 3)  # Convert bytes to GB
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

        # Convert timeleft to minutes safely
        if timeleft != "N/A" and ':' in timeleft:
            try:
                time_parts = [int(part) for part in timeleft.split(':')]
                time_left_minutes = time_parts[0] * 60 + time_parts[1] + (time_parts[2] / 60)
            except (ValueError, IndexError):
                time_left_minutes = 0  # Default to 0 if parsing fails
        else:
            time_left_minutes = 0  # Default to 0 for "N/A" or invalid formats

        # Calculate download speed if time_left_minutes > 0
        download_speed = calculate_speed(sizeleft_gb, time_left_minutes) if time_left_minutes > 0 else "N/A"

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
        embed.add_field(name="Download Speed", value=download_speed, inline=False)
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
    global bot_messages  # Dictionary to store active messages

    # If no active downloads and no embeds to show
    if not embeds:
        # Delete all existing download messages
        for message_id, msg_info in list(bot_messages.items()):
            try:
                await msg_info['message'].delete()
                del bot_messages[message_id]
            except discord.errors.NotFound:
                logging.warning(f"Message with ID {message_id} not found when attempting to delete.")

        # Display default message if it's not already displayed
        if not default_message:  # Only create the default message if it doesn't exist
            default_message = await channel.send("No active downloads currently.")
        return default_message  # Return the default message for future reference

    # If there are embeds (i.e., active downloads)
    # Delete the default message if it's currently displayed
    if default_message:
        try:
            await default_message.delete()
            default_message = None  # Set to None after deleting
        except discord.errors.NotFound:
            logging.warning(f"Default message with ID {default_message.id} not found when attempting to delete.")

    # Mark all existing messages as "inactive" initially
    for message_id in list(bot_messages.keys()):
        bot_messages[message_id]['active'] = False

    # Batch embeds into groups of up to 10 (Discord's limit)
    batched_embeds = [embeds[i:i + 10] for i in range(0, len(embeds), 10)]

    # Update or create new messages for active downloads
    for i, embed_batch in enumerate(batched_embeds):
        batch_id = f'batch_{i}'  # Unique ID for each batch of embeds

        if batch_id in bot_messages:
            # If the message exists, update the embed batch
            msg = bot_messages[batch_id]['message']
            try:
                await msg.edit(embeds=embed_batch)
                bot_messages[batch_id]['active'] = True  # Mark the message as active
            except discord.errors.NotFound:
                logging.warning(f"Message for batch {batch_id} not found. Creating a new one.")
                new_msg = await channel.send(embeds=embed_batch)
                bot_messages[batch_id] = {'message': new_msg, 'active': True}
        else:
            # If the message doesn't exist, create a new one
            new_msg = await channel.send(embeds=embed_batch)
            bot_messages[batch_id] = {'message': new_msg, 'active': True}

    # Delete messages for downloads that are no longer active
    for download_id, msg_info in list(bot_messages.items()):
        if not msg_info['active']:
            try:
                await msg_info['message'].delete()
                del bot_messages[download_id]
            except discord.errors.NotFound:
                logging.warning(f"Message for download {download_id} not found when attempting to delete.")

    return None  # Return None as no default message is needed when there are active downloads

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
    bot_messages = {}  # Ensure bot_messages is initialized as a dictionary
    default_message = None  # Reset default_message

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
            # Fetch data from Sonarr & Radarr
            embeds = []
            # Get Sonarr and Radarr data
            sonarr_embeds = query_sonarr(SONARR_IP, SONARR_PORT, SONARR_API_KEY, SONARR_TITLE)
            sonarr_anime_embeds = query_sonarr(SONARR_IP_ANIME, SONARR_PORT_ANIME, SONARR_API_KEY_ANIME, SONARR_TITLE_ANIME)
            radarr_embeds = query_radarr(RADARR_IP, RADARR_PORT, RADARR_API_KEY, RADARR_TITLE)
            radarr_anime_embeds = query_radarr(RADARR_IP_ANIME, RADARR_PORT_ANIME, RADARR_API_KEY_ANIME, RADARR_TITLE_ANIME)

            # Combine data from both sources
            embeds += sonarr_embeds
            embeds += radarr_embeds
            embeds += sonarr_anime_embeds
            embeds += radarr_anime_embeds

            # Update messages
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
