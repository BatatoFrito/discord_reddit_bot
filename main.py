'''

This bot gets posts from subreddits and automatically sends them on Discord

'''

import discord
import praw
import asyncio
from prawcore import NotFound, Redirect
from sqlalchemy import create_engine, Column, String, Integer, ForeignKey, and_, select
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from pathlib import Path
from discord.ext import commands, tasks
from dotenv import dotenv_values

# Database settings
Base = declarative_base()

class Subreddit(Base):
    __tablename__ = 'subreddits'

    _id = Column('id', Integer, primary_key=True)
    name = Column('name', String)
    channels = relationship('Channel', backref='subreddit', lazy="selectin")

    def __init__(self, name):
        self.name = name

class Channel(Base):
    __tablename__ = 'channels'

    _id = Column('id', Integer, primary_key=True)
    sid = Column('sid', Integer, ForeignKey('subreddits.id'))
    channel_id = Column('channel_id', String)

    def __init__(self, channel_id, sid):
        self.channel_id = channel_id
        self.sid = sid

# Creates engine and sessionmaker
async def create_engine():
    engine = create_async_engine('sqlite+aiosqlite:///subreddits.db')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine

engine = asyncio.run(create_engine())
async_session = async_sessionmaker(engine, expire_on_commit=False)

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
intents.message_content = True

client = commands.Bot(command_prefix='!', intents=intents)

# Recent submissions list
latest_submissions = {}

@client.event
async def on_ready():
    synced = await client.tree.sync()
    print(f'Synced {len(synced)} command(s)')
    await sub_update.start()

# Newest post loop
@tasks.loop(seconds=10)
async def sub_update():
    async with async_session() as session:
        # Subreddits that the bot will monitor
        sub_list = []
        sub_db = await session.execute(select(Subreddit))
        sub_db = sub_db.scalars().all()

        for sub in sub_db:
            sub_list.append(sub.name)

        subreddits = {}
        submissions = {}

        # Creates the subs dict
        for sub in sub_list:
            # Checks if subreddit exists or is banned
            try:
                reddit_instance.subreddits.search_by_name(sub, exact=True)
            except(NotFound, Redirect):
                continue
            subreddits[sub] = reddit_instance.subreddit(sub)

        # Sends newest posts
        for sub in subreddits:
            # Checks if subreddit exists or is banned
            try:
                reddit_instance.subreddits.search_by_name(sub, exact=True)
            except(NotFound, Redirect):
                continue

            submissions[sub] = next(subreddits[sub].new(limit=1))
            content = submissions[sub]

            # Checks if sub is in latest_submissions
            if not sub in latest_submissions:
                latest_submissions[sub] = 0
            
            # Checks if already sent
            if content.id == latest_submissions[sub]:
                continue
            
            # Gets channels linked to sub
            sub_set = await session.execute(select(Subreddit).where(Subreddit.name == sub))
            sub_set = sub_set.scalars().first()
            sub_channel_list = [sub_channel.channel_id for sub_channel in sub_set.channels]

            # Sends content to channels
            for channel in sub_channel_list:
                channel_to_send = client.get_channel(int(channel))
                await channel_to_send.send(content.title)
                latest_submissions[sub] = content.id

# Set channel command
@client.tree.command(name='set_sub_to_channel', 
                     description='Sets subreddit posts to be sent to this channel, multiple subreddits can be set separating by space.')
async def sub_to_channel(interaction: discord.Interaction, subs: str):
    async with async_session() as session:
        await interaction.response.defer()

        subs_list = subs.split()
        channel = interaction.channel
        successes = 0
        exceptions = []

        for sub in subs_list:
            # Checks if subreddit already exists on database
            sub_query = await session.execute(select(Subreddit).where(Subreddit.name == sub))
            sub_query = sub_query.scalar()

            # Checks if subreddit exists or is banned
            try:
                reddit_instance.subreddits.search_by_name(sub, exact=True)
                # Adds subreddit to database if not there
                if not sub_query:
                    new_sub = Subreddit(sub)
                    session.add(new_sub)
                    await session.commit()
            except(NotFound, Redirect):
                exceptions.append(sub)
                continue

            # Checks if sub is already set to channel
            sub_set = await session.execute(select(Subreddit).where(Subreddit.name == sub))
            sub_set = sub_set.scalar()
            sub_channel_list = [sub_channel.channel_id for sub_channel in sub_set.channels]

            if str(channel.id) in sub_channel_list:
                continue

            # Sets sub to channel
            sub_to_channel = Channel(channel.id, sub_set._id)
            session.add(sub_to_channel)
            await session.commit()
            successes += 1

        if exceptions:
            await interaction.followup.send(f'Set {successes} new subreddit(s) to this channel!\nExceptions: {exceptions}', ephemeral=True)
        else:
            await interaction.followup.send(f'Set {successes} new subreddit(s) to this channel!', ephemeral=True)

# Remove from channel command
@client.tree.command(name='remove_sub_from_channel', 
                     description='Removes subs that were set in a channel, multiple subreddits can be removed separating by space.')
async def remove_from_channel(interaction: discord.Interaction, subs: str):
    async with async_session() as session:
        await interaction.response.defer()

        subs_list = subs.split()
        channel = interaction.channel
        successes = 0
        exceptions = []

        for sub in subs_list:
            # Checks if sub in database
            sub_query = await session.execute(select(Subreddit).where(Subreddit.name == sub))
            sub_query = sub_query.scalar()

            if sub_query:
                # Checks if channel in database
                channel_query = await session.execute(select(Channel).where(and_(Channel.channel_id == channel.id, Channel.sid == sub_query._id)))
                channel_query = channel_query.scalar()

                if channel_query:
                    await session.delete(channel_query)
                    await session.commit()
                    successes += 1
            else:
                exceptions.append(sub)

        if exceptions:
            await interaction.followup.send(f'Removed {successes} subreddit(s) from this channel!\nExceptions: {exceptions}', ephemeral=True)
        else:
            await interaction.followup.send(f'Removed {successes} subreddit(s) from this channel!', ephemeral=True)

# Show from channel command
@client.tree.command(name='show_channel_subs', description='Shows every sub connected to this channel')
async def show_channel_subs(interaction: discord.Interaction):
    async with async_session() as session:
        await interaction.response.defer()
        
        channel = interaction.channel

        subs_in_channel = await session.execute(select(Channel).where(Channel.channel_id == channel.id))
        subs_in_channel = subs_in_channel.scalars()
        sub_list_str = ''

        for channel_in_list in subs_in_channel:
            sub = await session.execute(select(Subreddit).where(Subreddit._id == channel_in_list.sid))
            sub = sub.scalar()
            sub_list_str += f'- {sub.name}\n'
        
        if sub_list_str:
            await interaction.followup.send(f'Subreddits connected to {channel.name}: \n\n{sub_list_str}', ephemeral=True)
        else:
            await interaction.followup.send(f'No subreddits are connected to {channel.name}', ephemeral=True)

# Runs Discord Bot
if __name__ == '__main__':
    client.run(DISCORD_TOKEN)