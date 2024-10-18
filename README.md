# Discord-ARR-Download-Tracker

<p align="center">
  <a href="https://github.com/DinoHorvat96/Discord-ARR-Download-Tracker/releases"><img src="https://img.shields.io/github/v/release/DinoHorvat96/Discord-ARR-Download-Tracker"></a>
  <a href="https://github.com/DinoHorvat96/Discord-ARR-Download-Tracker/commits/main"><img src="https://img.shields.io/github/last-commit/DinoHorvat96/Discord-ARR-Download-Tracker"></a>
  <a href="https://github.com/DinoHorvat96/Discord-ARR-Download-Tracker/blob/main/LICENSE.md"><img src="https://img.shields.io/github/license/DinoHorvat96/Discord-ARR-Download-Tracker"></a>
  <a href="https://github.com/DinoHorvat96/Discord-ARR-Download-Tracker"><img src="https://img.shields.io/github/languages/code-size/DinoHorvat96/Discord-ARR-Download-Tracker"></a>
</p>

A simple bot which tracks the download progress of Sonarr &amp; Radarr instances and reports their status to a Discord channel.

## Support

Please keep in mind that at the time of writing this, I have just started dabbling in Discord bots, I am by no means an expert user. My code might not be optimized yet, but over time I am hoping to get there.

All the updates of the template are available [here](UPDATES.md).

## How to download

- Clone or download the repository
- Create a Discord bot [here](https://discord.com/developers/applications)
- Get your bot token under the "Bot" tab (you might have to click "Reset Token" the first time)
- Navigate to the OAuth2 tab and generate an invite link with the following permissions:
  Scopes: bot
  Bot Permissions: Send Messages & Manage Messages
  Integration Type: Guild Install
- Use the generated link to invite the bot to your Discord server

## How to configure the bot

There is an environment variable to edit in order to initialize the bot. Keep in mind that from the get-go, the Bot is configured to work with 2 Sonarr and 2 Radarr instances (one normal and one Anime). You will need to change the code if you do not wish to utilize that, however there should be no issues if you leave the code in, as the API calls will not go through to an unexisting Arr instance.

### `.env` file

To set up the bot you will have to make use of the [`.env.example`](.env.example) file, you should rename it to `.env` and replace the given variables with your own.
Replace `YOUR_BOT_TOKEN_HERE` with your bot's token that you've retrieved in the Bot tab of the [Discord's Bot Application page](https://discord.com/developers/applications), and `YOUR_DISCORD_CHANNEL_ID_HERE` is a numeric ID of the channel that the Bot will post it's messages into. All of the other environment variables should be self-explanatory.
***IMPORTANT TO NOTE:*** The bot will **_DELETE_** all messages in that channel, I highly encourage you to make a separate channel for this Bot that will not be used by anyone else (restrict everyone's "Send Messages" permission in that channel and let only the Bot post in it).

## How to start

To start the bot you simply need to launch either your terminal (Linux, Mac) or Command Prompt (Windows).

Before running the bot you will need to install all the requirements with this command:

```
python -m pip install -r requirements.txt
```

After that you can start it with

```
python bot.py
```

> **Note** You may need to replace `python` with `py`, `python3`, `python3.11`, etc. depending on what Python versions you have installed on the machine.

## Issues or Questions

If you have any issues or questions of how to code a specific command, you can post them to the [issues page](https://github.com/DinoHorvat96/Discord-ARR-Download-Tracker/issues)

Me or other people will take their time to answer and help you.

## License

This project is licensed under the GPL-3.0 license - see the [LICENSE.md](LICENSE.md) file for details.

## Screenshots

![image](https://github.com/user-attachments/assets/a6a99e31-39a5-4914-ab1e-a1d2de671b56)
