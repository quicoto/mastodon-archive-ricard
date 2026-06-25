import json
import shutil
from collections import Counter
from os import path
from datetime import datetime
import sys
import re

imageHost = ''
if len(sys.argv) > 1:
    imageHost = sys.argv[1]

with open("archive/outbox.json", "r", encoding="utf-8") as outbox_file:
    outbox = json.loads(outbox_file.read())

with open("archive/actor.json", "r", encoding="utf-8") as actor_file:
    actor = json.loads(actor_file.read())

# map the outbox down to the actual objects
statuses = [status.get("object") for status in outbox.get("orderedItems")]

articles = []
# Count every hashtag occurrence (case-sensitive) and remember its href.
hashtagCounts = Counter()
hashtagHrefs = {}

# Minify the HTML content by removing unnecessary whitespace and line breaks.
# Content inside <pre> blocks is preserved so code/preformatted toots keep their
# original whitespace.
def minify_html(html):
    preBlocks = []

    def _stash(match):
        preBlocks.append(match.group(0))
        return "\x00PRE{0}\x00".format(len(preBlocks) - 1)

    html = re.sub(r"<pre\b.*?</pre>", _stash, html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r">\s+<", "><", html)  # Remove whitespace between tags
    html = re.sub(r"\s+", " ", html)    # Collapse multiple spaces into one

    for index, block in enumerate(preBlocks):
        html = html.replace("\x00PRE{0}\x00".format(index), block)
    return html

for status in statuses:
    # need to ignore objects that arent status dicts
    if isinstance(status, dict):
        if not "https://www.w3.org/ns/activitystreams#Public" in (status.get("to", []) + status.get("cc", [])):
            # Toot is not public, let's not output it.
            continue
        # get the date from the statuses (eg. 2024-01-15T16:52:47Z)
        date = status.get("published")
        # convert the date string to a datetime object, tolerating fractional
        # seconds and timezone offsets (e.g. 2024-01-15T16:52:47.123+00:00)
        date_obj = datetime.fromisoformat(date.replace("Z", "+00:00"))
        # format the datetime object to a more human-readable format
        date = date_obj.strftime("%B %d, %Y")

        url = status.get("url")

        htmlContent = status.get("content")

        # Find all the Hashtag tags and record them (case-sensitive) with their href
        for hashtag in status.get("tag", []):
            if hashtag.get("type") == "Hashtag":
                name = hashtag.get("name")
                hashtagCounts[name] += 1
                hashtagHrefs.setdefault(name, hashtag.get("href"))

        attachments = [
            attachment.get("url")
            for attachment in status.get("attachment", [])
            if attachment.get("url")
        ]

        images = ""
        for imageURL in attachments:
          images += "<a href='{0}{1}'><img loading='lazy' class='item__image' src='{0}{1}'></a>".format(imageHost, imageURL)

        summary = status.get("summary")
        if summary:
            summary = "<h4>{0}</h4>".format(summary)
        else:
            summary = ""

        article = "<article class='item'>\n\
  <div class='item__date'><a href='{3}'>{0}</a></div>\n\
  {4}\n\
  <div class='item__content'>{1}</div>\n\
  <div class='item__media'>{2}</div>\n\
</article>\n".format(date, htmlContent, images, url, summary)

        articles.append(article)

# Check if the folder has an "avatar.{jpg,png,webp}" and copy it to the docs folder
assetExtensions = ["jpg", "png", "webp"]
avatarExt = None
for ext in assetExtensions:
    avatarPath = "archive/avatar." + ext
    if path.exists(avatarPath):
        avatarExt = ext
        shutil.copyfile(avatarPath, "docs/avatar." + ext)
        break

# Build avatar image HTML conditionally
avatarImgHtml = ""
if avatarExt:
  avatarImgHtml = '<div><img class="avatar" src="./avatar.%s" alt="Avatar of %s"></div>' % (avatarExt, actor.get("name"))

# Extract the instance host from the actor URL, with a safe fallback.
actorUrl = actor.get("url", "")
hostMatch = re.search(r"https?://([^/]+)", actorUrl)
instanceHost = hostMatch.group(1) if hostMatch else ""

header = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>%s Mastodon archive</title>
  <link rel="stylesheet" href="styles.css?ver=3.1.0">
  <meta name="robots" content="noindex">
</head>
<body>
  <header>
    %s
    <div>
      <h1>Archive for <a href="%s">%s</a> posts</h1>
      <h2><a class="no-decoration" href="%s">@%s@%s</a></h2>
      <h3>Number of posts: %s</h3>
    </div>
  </header>
  <main>\n""" % (
    actor.get("name"),
    avatarImgHtml,
    actor.get("url"),
    actor.get("name"),
    actor.get("url"),
    actor.get("preferredUsername"),
    instanceHost,
    "{:,}".format(len(articles))
)

# Order the hashtags alphabetically by name (case-sensitive)
uniqueHashtags = sorted(hashtagCounts)

# Add the hashtags to the header
header += "<details class='hashtags-accordion'><summary>Hashtags ({0})</summary><ul class='hashtags'>".format(len(uniqueHashtags))

for name in uniqueHashtags:
    anchor = "<a href='{0}'>{1}</a>".format(hashtagHrefs.get(name, ""), name)
    header += "<li>{0} ({1})</li>".format(anchor, hashtagCounts[name])
header += "</ul></details>"

header += "<div class='items'>"
header = minify_html(header)

footer = """
    </div>
	</main>
  <footer>
    <p>
      <a href="https://github.com/quicoto/mastodon-archive">Grab the code on GitHub</a>
    </p>
  </footer>
</body>
</html>"""
footer = minify_html(footer)

with open("docs/index.html", "w", encoding="utf-8") as outfile:
    outfile.write(header)
    for article in reversed(articles):
        outfile.write(minify_html(article))
    outfile.write(footer)
