import tweepy
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from credentials import API_key, API_secret_key, access_token, access_token_secret

def build_post_string(agg):
    post_string = "Top 5 for the last 30 days:\n\n"
    for index, row in agg.iterrows():
        if index >= 5:
            break
        post_string += "{name}'s jet emitted {tons} tons of CO₂\n".format(
            i=index+1,
            name=row['name'],
            tons=round(row['c02_tons'])
        )
    print(post_string)
    print(len(post_string))
    return post_string


def generate_image(agg, pathname):
    """
    Generate an image with just the top person
    """

    post_string = "Over the last 30 days,\n"
    post_string += "{name}'s jet emitted {tons} tons of CO₂.\n\n".format(
        name=agg.iloc[0]['name'],
        tons=round(agg.iloc[0]['c02_tons'])
    )
    post_string += "The average american generated 1.3 tons."

    req = requests.get("https://github.com/googlefonts/roboto/blob/main/src/hinted/Roboto-Regular.ttf?raw=true")
    font = ImageFont.truetype(BytesIO(req.content), 32)
    width = 800
    height = 418
    img = Image.new('RGB', (width, height), color='black')
    d = ImageDraw.Draw(img)
    w, h = d.textsize(post_string, font=font)
    #d.text((20, 20), text='Over the last 30 days:\n', font=font, fill='white')
    d.text(((width-w)/2, (height-h)/2 - 50), text=post_string, font=font, fill='white')
    watermark = Image.open('watermark.png')
    watermark = watermark.resize((328, 122))
    img.paste(watermark, (460, 280))
    img.save(pathname)


def post_to_twitter(text, pathname):
    # authorization of consumer key and consumer secret
    auth = tweepy.OAuthHandler(API_key, API_secret_key)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)
    media_obj = api.media_upload(pathname)

    client = tweepy.Client(
        consumer_key=API_key,
        consumer_secret=API_secret_key,
        access_token=access_token,
        access_token_secret=access_token_secret
    )

    response = client.create_tweet(text=text, media_ids=[media_obj.media_id])
    return response
