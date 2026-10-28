"""Bounded public discovery adapters. No creator database or account analytics access."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener

class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

public_open = build_opener(NoRedirects()).open
_lock = threading.Lock()
_cache = {}
_retry_at = {}
TTL = 900
PLATFORMS = ['Reddit', 'X / Twitter', 'Instagram', 'YouTube', 'Twitch', 'Kick', 'TikTok', 'Facebook', 'Pinterest', 'Tumblr']
ENV = {
    'YouTube': ['GOODFORM_YOUTUBE_API_KEY'],
    'Twitch': ['GOODFORM_TWITCH_CLIENT_ID', 'GOODFORM_TWITCH_ACCESS_TOKEN'],
    'Kick': ['GOODFORM_KICK_ACCESS_TOKEN'],
    'X / Twitter': ['GOODFORM_X_BEARER_TOKEN'],
}
METHODS = {
    'Reddit': 'Hot discussions from r/popular; a community sample.',
    'YouTube': 'Regional mostPopular chart; not all YouTube categories or global growth.',
    'Twitch': 'First 20 live streams by concurrent viewers; not growth over time.',
    'Kick': 'First 20 active streams, oldest-first; not a popularity ranking.',
    'X / Twitter': 'Platform-provided topics for the configured location; no inferred growth.',
}

def stamp():
    return datetime.now(timezone.utc).isoformat()

def coverage(reddit_configured=False):
    return [{'platform': p, 'status': ('Ready to scan' if (reddit_configured if p=='Reddit' else all(os.environ.get(k) for k in ENV.get(p, []))) else 'Setup needed') if p in METHODS else 'Not implemented',
             'method': METHODS.get(p, 'Public discovery adapter and approved access are still required.'),
             'count': 0, 'observed_at': None} for p in PLATFORMS]

def text(value, limit=500):
    return value.strip()[:limit] if isinstance(value, str) else ''

def count(value):
    try:
        if isinstance(value, bool): return None
        n = float(value)
        return int(n) if math.isfinite(n) and n >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None

def rows(data, key='data'):
    values = data.get(key) if isinstance(data, dict) else None
    if not isinstance(values, list): raise ValueError('Invalid listing')
    return [r for r in values[:20] if isinstance(r, dict)]

def source(platform, identity, title, url, metrics, observed, category=''):
    return {'id': platform.lower().replace(' / ', '-')+':'+identity,
            'platform': platform, 'title': text(title), 'url': url, 'observed_at': observed,
            'category': text(category, 100), 'metrics': {k:v for k,v in metrics.items() if v is not None}}

def normalize(platform, data, observed):
    result = []
    for row in rows(data, 'items' if platform=='YouTube' else 'data'):
        if platform == 'YouTube':
            identity = text(row.get('id'))
            snippet = row.get('snippet') or {}
            stats = row.get('statistics') or {}
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}', identity) or not isinstance(snippet,dict) or not isinstance(stats,dict): continue
            item = source(platform, identity, snippet.get('title'), 'https://www.youtube.com/watch?v='+identity,
                          {'views':count(stats.get('viewCount')), 'likes':count(stats.get('likeCount')), 'comments':count(stats.get('commentCount'))}, observed)
        elif platform in ('Twitch', 'Kick'):
            kick = platform == 'Kick'
            channel = row.get('channel') or {}
            if not isinstance(channel, dict): continue
            slug = text(channel.get('slug') if kick else row.get('user_login'))
            identity = text(row.get('id'))
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',slug) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',identity): continue
            if row.get('has_mature_content') if kick else row.get('is_mature'): continue
            category = row.get('category') or {}
            if not isinstance(category,dict): continue
            item = source(platform, identity, row.get('title'), ('https://kick.com/' if kick else 'https://www.twitch.tv/')+slug,
                          {'concurrent viewers':count(row.get('viewer_count'))}, observed, category.get('name') if kick else row.get('game_name'))
        else:
            title = text(row.get('trend_name'))
            identity = hashlib.sha256(title.encode()).hexdigest()[:16]
            item = source(platform, identity, title, 'https://x.com/search?'+urlencode({'q':title}),
                          {'reported posts':count(row.get('tweet_count'))}, observed)
        if item['title']: result.append(item)
    return list({r['id']:r for r in result}.values())

def request_for(platform):
    if platform == 'YouTube':
        region = os.environ.get('GOODFORM_TREND_REGION', 'US').upper()
        if not re.fullmatch(r'[A-Z]{2}',region): raise ValueError('Invalid region')
        return Request('https://www.googleapis.com/youtube/v3/videos?'+urlencode({'part':'snippet,statistics','chart':'mostPopular','regionCode':region,'maxResults':20,'key':os.environ['GOODFORM_YOUTUBE_API_KEY']})), 'Chart region: '+region
    if platform == 'Twitch':
        return Request('https://api.twitch.tv/helix/streams?first=20&type=live', headers={'Authorization':'Bearer '+os.environ['GOODFORM_TWITCH_ACCESS_TOKEN'],'Client-Id':os.environ['GOODFORM_TWITCH_CLIENT_ID']}), 'All languages; current live streams'
    if platform == 'Kick':
        return Request('https://api.kick.com/public/v2/livestreams?limit=20',headers={'Authorization':'Bearer '+os.environ['GOODFORM_KICK_ACCESS_TOKEN']}), 'Oldest-first active stream sample'
    woeid = os.environ.get('GOODFORM_TREND_WOEID','1')
    if not re.fullmatch(r'[0-9]{1,12}',woeid): raise ValueError('Invalid location')
    return Request('https://api.x.com/2/trends/by/woeid/'+woeid,headers={'Authorization':'Bearer '+os.environ['GOODFORM_X_BEARER_TOKEN']}), 'WOEID: '+woeid

def fetch(platform):
    now = time.time()
    with _lock:
        cached = _cache.get(platform)
        if cached and now-cached[0] < TTL: return cached[1]
        if _retry_at.get(platform,0)>now: return {'status':'Cooling down','items':[],'error':'Provider cooldown is active; retry later.'}
        _retry_at[platform] = now+30
    try:
        req, scope = request_for(platform)
        with public_open(req, timeout=15) as response:
            raw = response.read(2_000_001)
        if len(raw)>2_000_000: raise ValueError('Response too large')
        observed = stamp()
        items = normalize(platform,json.loads(raw),observed)
        result = {'status':'Scanned' if items else 'No usable signals','items':items,'observed_at':observed,'scope':scope}
        with _lock: _cache[platform] = (now,result)
        return result
    except HTTPError as e:
        if e.code==429:
            retry = count(e.headers.get('Retry-After')) if e.headers else None
            with _lock: _retry_at[platform] = now+min(max(retry or 900,30),86400)
        message = {401:'Access expired or invalid.',403:'Access denied; verify app permissions and quota.',429:'Provider rate limit reached.'}.get(e.code, 'Provider request failed.')
        return {'status':'Unavailable','items':[],'error':message}
    except (URLError,OSError,ValueError,KeyError,TypeError):
        # Never serialize exceptions: URLs/headers can contain credentials.
        return {'status':'Unavailable','items':[],'error':'Check the public source configuration and connection.'}

def collect(reddit_reader, reddit_configured):
    statuses = coverage(reddit_configured)
    sources = []
    ready = [c['platform'] for c in statuses if c['status']=='Ready to scan']
    def read(platform):
        if platform != 'Reddit': return fetch(platform)
        try:
            result = reddit_reader()
            items = [source('Reddit',r['id'],r['title'],r['url'],{'net score':r.get('net_score'),'comments':r.get('comments')},r.get('observed_at',result['fetched_at']), 'r/'+r.get('community','popular')) for r in result['items']]
            return {'status':'Scanned' if items else 'No usable signals','items':items,'observed_at':result['fetched_at'],'scope':'r/popular'}
        except Exception:
            return {'status':'Unavailable','items':[],'error':'Public community research is unavailable; check approved access and retry later.'}
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = dict(zip(ready, pool.map(read, ready)))
    for c in statuses:
        if c['platform'] not in results: continue
        r = results[c['platform']]
        c.update({k:v for k,v in r.items() if k!='items'})
        c['count'] = len(r['items'])
        sources.extend(r['items'])
    return statuses, sources
