'''

This bot gets posts from subreddits and automatically sends them on Discord

'''

import discord
import praw
from discord.ext import commands, tasks
from dotenv import dotenv_values

# Reddit app values
config = dotenv_values('.env')

REDDIT_USERNAME = config['REDDIT_USERNAME']
REDDIT_PASSWORD = config['REDDIT_PASSWORD']
REDDIT_CLIENT_ID = config['REDDIT_CLIENT_ID']
REDDIT_CLIENT_SECRET = config['REDDIT_CLIENT_SECRET']
REDDIT_USER_AGENT = config['REDDIT_USER_AGENT']

reddit_instance = praw.Reddit(client_id=REDDIT_CLIENT_ID, client_secret=REDDIT_CLIENT_SECRET, password=REDDIT_PASSWORD, 
                              user_agent=REDDIT_USER_AGENT, username=REDDIT_USERNAME)

# Discord bot values
DISCORD_TOKEN = config['DISCORD_TOKEN']
intents = discord.Intents.default()

client = commands.Bot(command_prefix='!', intents=intents)

# Subreddits that the bot will monitor
sub_list = ['cats']
subreddits = {}
submissions = {}
last_submissions = []

# Creates the subs dict
for sub in sub_list:
    subreddits[f'{sub}'] = reddit_instance.subreddit(f'{sub}')

@client.event
async def on_ready():
    await sub_update.start()

# Newest post loop
@tasks.loop(seconds=5)
async def sub_update():
    channel = client.get_channel(1027351888053682249)
    # Sends newest posts
    for sub in sub_list:
        if f'{sub}' in submissions:
            if submissions[f'{sub}'] == next(subreddits[f'{sub}'].new(limit=1)):
                continue
        
        submissions[f'{sub}'] = next(subreddits[f'{sub}'].new(limit=1))
        await channel.send(submissions[f'{sub}'].title)

# Runs Discord Bot
client.run(DISCORD_TOKEN)