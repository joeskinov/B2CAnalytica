import tweepy
import re
import sys
from googletrans import Translator

#override tweepy.StreamListener to add logic to on_status
class MyStreamListener(tweepy.StreamListener):

    def on_status(self, status):
        print(status.text)

class Twitter:
    data = []
    def __init__(self, api_key, api_secret, access_key, access_secret):
        # Authentification
        auth = tweepy.OAuthHandler(api_key, api_secret)
        auth.set_access_token(access_key, access_secret)
        # Get API
        self.api = tweepy.API(auth)
        #initialise streamer
        myStreamListener = MyStreamListener()
        self.myStream = tweepy.Stream(auth = self.api.auth, listener=myStreamListener)
    
    def preprocess_word(self, word):
        # Remove punctuation
        word = word.strip('\'"?!,.():;')
        # Convert more than 2 letter repetitions to 2 letter
        # funnnnny --> funny
        word = re.sub(r'(.)\1+', r'\1\1', word)
        # Remove - & '
        word = re.sub(r'(-|\')', '', word)
        return word


    def is_valid_word(self, word):
        # Check if word begins with an alphabet
        return (re.search(r'^[a-zA-Z][a-z0-9A-Z\._]*$', word) is not None)


    def handle_emojis(self, tweet):
        # Smile -- :), : ), :-), (:, ( :, (-:, :')
        tweet = re.sub(r'(:\s?\)|:-\)|\(\s?:|\(-:|:\'\))', ' EMO_POS ', tweet)
        # Laugh -- :D, : D, :-D, xD, x-D, XD, X-D
        tweet = re.sub(r'(:\s?D|:-D|x-?D|X-?D)', ' EMO_POS ', tweet)
        # Love -- <3, :*
        tweet = re.sub(r'(<3|:\*)', ' EMO_POS ', tweet)
        # Wink -- ;-), ;), ;-D, ;D, (;,  (-;
        tweet = re.sub(r'(;-?\)|;-?D|\(-?;)', ' EMO_POS ', tweet)
        # Sad -- :-(, : (, :(, ):, )-:
        tweet = re.sub(r'(:\s?\(|:-\(|\)\s?:|\)-:)', ' EMO_NEG ', tweet)
        # Cry -- :,(, :'(, :"(
        tweet = re.sub(r'(:,\(|:\'\(|:"\()', ' EMO_NEG ', tweet)
        return tweet


    def preprocess_tweet(self, tweet):
        processed_tweet = []
        # Convert to lower case
        tweet = tweet.lower()
        # Replaces URLs with the word URL
        tweet = re.sub(r'((www\.[\S]+)|(https?://[\S]+))', ' URL ', tweet)
        # Replace @handle with the word USER_MENTION
        tweet = re.sub(r'@[\S]+', 'USER_MENTION', tweet)
        # Replaces #hashtag with hashtag
        tweet = re.sub(r'#(\S+)', r' \1 ', tweet)
        # Remove RT (retweet)
        tweet = re.sub(r'\brt\b', '', tweet)
        # Replace 2+ dots with space
        tweet = re.sub(r'\.{2,}', ' ', tweet)
        # Strip space, " and ' from tweet
        tweet = tweet.strip(' "\'')
        # Replace emojis with either EMO_POS or EMO_NEG
        tweet = self.handle_emojis(tweet)
        # Replace multiple spaces with a single space
        tweet = re.sub(r'\s+', ' ', tweet)
        words = tweet.split()

        for word in words:
            word = self.preprocess_word(word)
            if self.is_valid_word(word):
                processed_tweet.append(word)

        return ' '.join(processed_tweet)


    def preprocess_data(self, data):
        translator = Translator()
        pre_data = data
        for i, status in enumerate(data):
            if(status.lang != 'en'):
                pre_data[i].text = translator.translate(pre_data[i].text).text
            print (i, ' --> ',  pre_data[i].text)
            pre_data[i].text = self.preprocess_tweet(pre_data[i].text)
        return pre_data

    def get_timeline(self, user_name, count):
        pre_data = self.preprocess_data(self.api.user_timeline(screen_name=user_name, count=count)) 
        return pre_data
    
    def get_user_replies(self, user_name, count, rep_count):
        replies=[] 
        non_bmp_map = dict.fromkeys(range(0x10000, sys.maxunicode + 1), 0xfffd)
        for full_tweets in tweepy.Cursor(self.api.user_timeline,screen_name=user_name,timeout=999999, wait_on_rate_limit=True).items(count):
            for tweet in tweepy.Cursor(self.api.search,q='to:'+user_name,result_type='recent',timeout=999999, wait_on_rate_limit=True).items(rep_count):
                if hasattr(tweet, 'in_reply_to_status_id_str'):
                    if (tweet.in_reply_to_status_id_str==full_tweets.id_str):
                        replies.append(tweet)
        print(replies)
        return self.preprocess_data(replies)
    
    def live_stream(self):
        self.myStream.filter(track=['python'])