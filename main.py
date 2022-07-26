from data_fetch import download_data
from twitterbot import build_post_string, generate_image, post_image_to_twitter

PATHNAME = 'tmp.png'
df = download_data()
agg = df.groupby('name').sum().sort_values(by='c02_tons', ascending=False).reset_index()
post_string = build_post_string(agg)
generate_image(post_string, PATHNAME)
post_image_to_twitter(PATHNAME)