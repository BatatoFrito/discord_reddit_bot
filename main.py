'''

This bot gets posts from subreddits and automatically sends them on Discord

'''

import discord
import praw
from prawcore import NotFound, Redirect
from sqlalchemy import create_engine, Column, String, Integer, and_, exists
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path
from discord.ext import commands, tasks
from dotenv import dotenv_values

# Database settings
Base = declarative_base()

class Subreddit(Base):
    __tablename__ = 'subreddits'

    _id = Column('id', Integer, primary_key=True)
    guild_id = Column('guild_id', Integer)
    channel_id = Column('channel_id', Integer)
    name = Column('name', String)

    def __init__(self, guild_id, channel_id, name):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.name = name

engine = create_engine('sqlite:///subreddits.db')
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
session = Session()

# Paths
FILE_PATH = Path(__file__).absolute().parent

# Reddit app values
config = dotenv_values('.env')

REDDIT_USERNAME = config['REDDIT_USERNAME']
REDDIT_PASSWORD = config['REDDIT_PASSWORD']
REDDIT_CLIENT_ID = config['REDDIT_CLIENT_ID']
REDDIT_CLIENT_SECRET = config['REDDIT_CLIENT_SECRET']
REDDIT_USER_AGENT = config['REDDIT_USER_AGENT']

reddit_instance = praw.Reddit(client_id=REDDIT_CLIENT_ID, client_secret=REDDIT_CLIENT_SECRET, password=REDDIT_PASSWORD, 
                              user_agent=REDDIT_USER_AGENT, username=REDDIT_USERNAME, check_for_async=False)

# Discord bot values
DISCORD_TOKEN = config['DISCORD_TOKEN']
intents = discord.Intents.default()

client = commands.Bot(command_prefix='!', intents=intents)

# Subreddits that the bot will monitor
sub_list = ['cats', 'AceAttorney']
subreddits = {}
submissions = {}
last_submissions = []

# Creates the subs dict
for sub in sub_list:
    subreddits[f'{sub}'] = reddit_instance.subreddit(f'{sub}')

@client.event
async def on_ready():
    synced = await client.tree.sync()
    print(f'Synced {len(synced)} command(s)')
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

# Set channel command
@client.tree.command(name='set_sub_to_channel', 
                     description='Sets subreddit posts to be sent to this channel, multiple subreddits can be set separating by space.')
async def sub_to_channel(interaction: discord.Interaction, subs: str):
    subs_list = subs.split()
    channel = interaction.channel
    guild = interaction.guild
    successes = 0
    exceptions = []

    for sub in subs_list:
        # Checks if already exists on database
        sub_query = session.query(exists().where(and_(Subreddit.name == sub, Subreddit.channel_id == channel.id))).scalar()

        if sub_query:
            continue
        
        # Checks if subreddit exists or is banned
        try:
            reddit_instance.subreddits.search_by_name(sub, exact=True)
        except(NotFound, Redirect):
            exceptions.append(sub)
            continue

        sub_set = Subreddit(guild.id, channel.id, sub)
        session.add(sub_set)
        session.commit()
        successes += 1

    if exceptions:
        await interaction.response.send_message(f'Set {successes} new subreddit(s) to this channel!\nExceptions: {exceptions}', ephemeral=True)
    else:
        await interaction.response.send_message(f'Set {successes} new subreddit(s) to this channel!', ephemeral=True)

# Runs Discord Bot
if __name__ == '__main__':
    client.run(DISCORD_TOKEN)