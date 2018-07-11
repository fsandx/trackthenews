from io import BytesIO
import html2text
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from readability import Document
from twython import Twython, TwythonError

class Article:
    def __init__(self, outlet, title, url, delicate=False, redirects=False):
        self.outlet = outlet
        self.title = title
        self.url = url
        self.delicate = delicate
        self.redirects = redirects
        self.canonicalize_url()

        self.matching_grafs = []
        self.imgs = []
        self.tweeted = False

    def canonicalize_url(self):
        """Process article URL to produce something roughly canonical."""
        # These outlets use redirect links in their RSS feeds.
        # Follow those links, then store only the final destination.
        if self.redirects:
            res = requests.head(self.url, allow_redirects=True, timeout=30)
            self.url = res.headers['location'] if 'location' in res.headers \
                else res.url

        # Some outlets' URLs don't play well with modifications, so those we 
        # store crufty. Otherwise, decruft with extreme prejudice.
        print(self.url)
        if not self.delicate:
            self.url = Article.decruft_url(self.url)
    
    @staticmethod
    def decruft_url(url):
        """Attempt to remove extraneous characters from a given URL and return it."""
        url = url.split('?')[0].split('#')[0]
        return url
    
    def clean(self):
        """Download the article and strip it of HTML formatting."""
        self.res = requests.get(self.url, headers={'User-Agent':ua}, timeout=30)
        doc = Document(self.res.text)

        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_emphasis = True
        h.ignore_images = True
        h.body_width = 0

        self.plaintext = h.handle(doc.summary())

    def check_for_matches(self):
        """
        Clean up an article, check it against a block list, then for matches.
        """
        self.clean()
        plaintext_grafs = self.plaintext.split('\n')

        if blocklist_loaded and blocklist.check(self):
            pass
        else:
            for graf in plaintext_grafs:
                if (any(word.lower() in graf.lower() for word in matchwords) or \
                    any(word in graf for word in matchwords_case_sensitive)):
                    self.matching_grafs.append(graf)

    def tweet(self):
        """Send images to be rendered and tweet them with a text status."""
        square = False if len(self.matching_grafs) == 1 else True
        for graf in self.matching_grafs[:4]:
            self.imgs.append(render_img(graf, square=square))

        twitter = get_twitter_instance()

        media_ids = []

        for img in self.imgs:
            try:
                img_io = BytesIO()
                img.save(img_io, format='jpeg', quality=95)
                img_io.seek(0)
                res = twitter.upload_media(media=img_io)

                media_ids.append(res['media_id'])
            except TwythonError:
                pass

        source = self.outlet + ": " if self.outlet else ''

        status = "{}{} {}".format(source, self.title, self.url)
        twitter.update_status(status=status, media_ids=media_ids)
        print(status)

        self.tweeted = True
