# Where Pixi gets its answers in General Mode.
#
# Wikipedia is tried first because the summary is clean, short and easy to
# read out loud.  If Wikipedia has nothing we fall back to scraping the
# answer box off a Google results page.

import datetime
import random

import requests
import wikipedia
from bs4 import BeautifulSoup

# The library still defaults to plain http, which Wikipedia now redirects
wikipedia.wikipedia.API_URL = 'https://en.wikipedia.org/w/api.php'

# Wikipedia rejects the library's stock user agent and hands back an HTML
# error page, which then blows up as a JSON decode error deep inside the
# library.  Their policy asks for a descriptive agent, so give them one.
wikipedia.set_user_agent('Pixi/1.0 (Roboway Labs autonomous librarian robot)')

# Google blocks the default python-requests user agent outright
HEADERS = {
    'User-Agent': ('Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36'),
    'Accept-Language': 'en-US,en;q=0.9',
}

REQUEST_TIMEOUT = 8

# Words we strip off the front of a question before searching for it
QUESTION_PREFIXES = [
    'tell me about', 'what is the', 'who is the', 'what is a', 'what is',
    'who is', 'what are', 'who are', 'search for', 'search', 'google',
    'define', 'meaning of', 'tell me',
]


def clean_query(command):
    """Turn a spoken sentence into something worth searching for."""
    query = command.lower().strip()
    for prefix in QUESTION_PREFIXES:
        if query.startswith(prefix):
            query = query[len(prefix):]
            break
    return query.strip(' ?.,')


# ---------------------------------------------------------------------------
# Wikipedia
# ---------------------------------------------------------------------------
def search_wikipedia(query, sentences=2):
    """Return (answer, source) or (None, None) if Wikipedia has nothing."""
    if not query:
        return None, None
    try:
        # auto_suggest is asked for LAST, not first.  Wikipedia's suggest
        # endpoint mangles perfectly good titles - it turns "alan turing"
        # into "alan tuning", which then matches no page at all.  Look the
        # title up as spoken first and only guess if that really fails.
        try:
            summary = wikipedia.summary(query, sentences=sentences,
                                        auto_suggest=False)
        except wikipedia.exceptions.PageError:
            summary = wikipedia.summary(query, sentences=sentences,
                                        auto_suggest=True)
        if summary:
            return summary.strip(), 'Wikipedia'
    except wikipedia.exceptions.DisambiguationError as e:
        # Pick the first suggestion rather than giving up on the user
        if e.options:
            try:
                summary = wikipedia.summary(e.options[0], sentences=sentences,
                                            auto_suggest=False)
                return summary.strip(), 'Wikipedia (%s)' % e.options[0]
            except Exception:
                pass
    except wikipedia.exceptions.PageError:
        pass
    except Exception as e:
        print("Wikipedia lookup failed: %s" % e)
    return None, None


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------
# www.google.com/search is deliberately NOT used here.
#
# Google now answers a plain requests.get with a JavaScript redirect stub -
# 90 kB of script and not one line of result text - so there is nothing to
# scrape without running a browser, which the Pi cannot spare the memory for.
# DuckDuckGo still serves real HTML and has a small answer API on top of it,
# so that is what Pixi searches with.
DDG_API_URL = 'https://api.duckduckgo.com/'
DDG_HTML_URL = 'https://html.duckduckgo.com/html/'


def _duckduckgo_answer(query):
    """The instant answer API. Clean JSON, no scraping, usually the best hit."""
    try:
        response = requests.get(DDG_API_URL,
                                params={'q': query, 'format': 'json',
                                        'no_html': 1, 'skip_disambig': 1},
                                headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("DuckDuckGo answer request failed: %s" % e)
        return None

    for key in ['Answer', 'AbstractText', 'Definition']:
        text = data.get(key)
        if text and len(text) > 20:
            return text
    return None


def _duckduckgo_snippet(query):
    """Fall back to the first real result snippet on the HTML page."""
    try:
        response = requests.post(DDG_HTML_URL, data={'q': query},
                                 headers=HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except Exception as e:
        print("DuckDuckGo search failed: %s" % e)
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    for node in soup.select('.result__snippet'):
        text = node.get_text(' ', strip=True)
        # Anything shorter is a page title, not a description
        if text and len(text) > 60:
            return text
    return None


def search_web(query):
    """Search the web and return (answer, source), or (None, None)."""
    if not query:
        return None, None

    text = _duckduckgo_answer(query)
    if text:
        return _trim(text), 'DuckDuckGo'

    text = _duckduckgo_snippet(query)
    if text:
        return _trim(text), 'DuckDuckGo'

    return None, None


def _trim(text, limit=400):
    """Keep the spoken answer short enough that nobody walks away."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    stop = cut.rfind('. ')
    if stop > 80:
        return cut[:stop + 1]
    return cut.rstrip() + '...'


# ---------------------------------------------------------------------------
# The one function General Mode actually calls
# ---------------------------------------------------------------------------
def answer(command, keywords_responses=None):
    """Answer a spoken question.  Returns (answer_text, source_label)."""
    command = (command or '').lower().strip()
    if not command:
        return "I did not catch that. Please say it again.", 'Pixi'

    # 1. Canned small talk from general_responses.json
    if keywords_responses:
        for keyword, replies in keywords_responses.items():
            if keyword in command:
                return random.choice(replies), 'Pixi'

    # 2. Things we can answer without the internet
    if 'time' in command:
        return ("It is " + datetime.datetime.now().strftime('%I:%M %p'),
                'Clock')

    if 'date' in command or "today" in command:
        return (datetime.datetime.now().strftime('Today is %A, %d %B %Y'),
                'Clock')

    if 'joke' in command:
        try:
            import pyjokes
            return pyjokes.get_joke(), 'Pyjokes'
        except Exception:
            return "I forgot the punchline. Ask me something else.", 'Pixi'

    # 3. Wikipedia, then Google
    query = clean_query(command)

    text, source = search_wikipedia(query)
    if text:
        return text, source

    text, source = search_web(query)
    if text:
        return text, source

    return ("Sorry, I could not find anything about %s." % query), 'Pixi'
