'''

This bot grabs posts from subreddits and automatically sends them on Discord

'''

import praw
from dotenv import dotenv_values

# Reddit app values
config = dotenv_values('.env')

USERNAME = config['USERNAME']
PASSWORD = config['PASSWORD']
CLIENT_ID = config['CLIENT_ID']
CLIENT_SECRET = config['CLIENT_SECRET']
USER_AGENT = config['USER_AGENT']

reddit_instance = praw.Reddit(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, password=PASSWORD, user_agent=USER_AGENT, username=USERNAME)
