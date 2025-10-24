import tweepy

from src.config import settings

# Authenticate (v1.1 for lists)
auth = tweepy.OAuth1UserHandler(
    consumer_key=settings.X_CONSUMER_KEY,
    consumer_secret=settings.X_CONSUMER_SECRET,
    access_token=settings.X_ACCESS_TOKEN,
    access_token_secret=settings.X_ACCESS_TOKEN_SECRET,
)
api = tweepy.API(auth)

# Add users (returns list of added User objects)
added_users = api.add_list_member(list_id=settings.X_LIST_ID, screen_name="fazli30991")
print("Added:", [user.screen_name for user in added_users])
