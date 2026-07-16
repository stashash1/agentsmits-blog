#!/usr/bin/env python3
"""
AI News Scanner — deterministic Python script.
Replaces LLM-based scan with reliable duplicate checking.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError
import re
import fcntl
import time

sys.path.insert(0, os.path.dirname(__file__))
from metrics import (
    log_event, log_error,
    log_source_health, funnel_set, log_run_event, log_alert, _load_metrics,
)
from _config import PENDING_QUEUE, SELECTION_QUEUE

try:
    from impact_scoring import compute_impact
except ImportError:
    try:
        from scripts.impact_scoring import compute_impact
    except ImportError:
        compute_impact = None

SCRIPT_NAME = "scan"


def load_queue():
    with open(PENDING_QUEUE) as f:
        return json.load(f)

def save_queue(d):
    with open(PENDING_QUEUE, 'w') as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

def load_selection():
    with open(SELECTION_QUEUE) as f:
        return json.load(f)

def save_selection(d):
    with open(SELECTION_QUEUE, 'w') as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def filter_already_seen(articles, queue_file=PENDING_QUEUE):
    """Remove articles whose URL is already known (pending/published in queue).

    Optimization: scanners fetch RSS/sitemap entries going back ~2 weeks, but the
    vast majority are already in pending_queue.json. Filter at source so the main
    dedup loop doesn't waste cycles (previously 99-115 dups per run).

    Compares normalized URLs (trailing slash stripped). On any error, returns
    the original list unchanged (fail-open: never block a scanner).
    """
    if not articles:
        return articles
    try:
        with open(queue_file, encoding='utf-8') as f:
            state = json.load(f)
        seen_urls = set()
        for section in ('pending', 'published'):
            for item in state.get(section, []):
                u = item.get('url')
                if u:
                    seen_urls.add(u.rstrip('/'))
        return [
            a for a in articles
            if (a.get('url') or '').rstrip('/') not in seen_urls
        ]
    except Exception as e:
        log_error(SCRIPT_NAME, f"filter_already_seen failed: {e}")
        return articles


def make_article_id(prefix, url, max_len=60):
    """Generate a short deterministic ID from URL, using hash when URL is too long.
    
    Truncating the last path segment causes collisions (different URLs -> same ID).
    Instead, use a hash suffix when the URL-based ID would exceed max_len.
    """
    # Get the last URL path segment
    path = url.rstrip('/').split('/')[-1]
    # If it's short enough, use it directly
    base_id = f"{prefix}-{path}"
    if len(base_id) <= max_len:
        return base_id
    # Otherwise use hash of full URL for uniqueness
    import hashlib
    hash_suffix = hashlib.md5(url.encode()).hexdigest()[:12]
    short_path = path[:max_len - len(prefix) - 2]  # room for prefix + hyphen + hash
    return f"{prefix}-{short_path}-{hash_suffix}"

def is_fresh(url_date_str, cutoff_days=14):
    """Check if date string is within cutoff_days from today."""
    if not url_date_str:
        return True  # no date = assume fresh
    try:
        # Try DD/MM/YYYY format from RBC URLs
        dt = datetime.strptime(url_date_str, "%d/%m/%Y")
        days_ago = (datetime.now() - dt).days
        return days_ago <= cutoff_days
    except ValueError:
        return True  # can't parse = assume fresh

def extract_date_from_url(url):
    """Extract date from URL like /20/01/2026/"""
    match = re.search(r'/(\d{2})/(\d{2})/(\d{4})/', url)
    if match:
        return f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
    return None

def fetch_url(url, timeout=10):
    """Simple fetch with browser-like headers to avoid bot detection."""
    import time as _t
    t0 = _t.monotonic()
    try:
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        with urlopen(req, timeout=timeout) as r:
            data = r.read().decode('utf-8', errors='ignore')
        fetch_url.last_ms = int((_t.monotonic() - t0) * 1000)
        fetch_url.last_err = None
        return data
    except (URLError, OSError) as e:
        fetch_url.last_ms = int((_t.monotonic() - t0) * 1000)
        fetch_url.last_err = str(e)[:200]
        return None


def _track_source(source_name, articles, ok=True, error=None):
    """Wrap source scanner call: track health + count + funnel."""
    if ok:
        log_source_health(source_name, ok=True,
                          fetch_ms=getattr(fetch_url, 'last_ms', None),
                          items_found=len(articles))
    else:
        log_source_health(source_name, ok=False,
                          error=error or getattr(fetch_url, 'last_err', None))
        # If a source has 3+ fails in a row, raise alert
        m = _load_metrics()
        sh = m.get('source_health', {}).get(source_name, {})
        if sh.get('fail_streak', 0) >= 3:
            log_alert(
                'source_unhealthy',
                f"Source '{source_name}' has {sh['fail_streak']} consecutive failures",
                severity='error',
                details={'source': source_name,
                         'fail_streak': sh['fail_streak'],
                         'last_error': sh.get('last_error', '')[:200]},
            )
    for a in articles:
        funnel_set(a['id'], 'enqueued',
                   source=a.get('source', source_name),
                   title=a.get('title', '')[:80])


def scan_anthropic(queue):
    """Scan Anthropic news via sitemap.

    Sitemap lastmod = last-modified of the page, not publication date.
    Strategy: collect all /news/ URLs, sort by lastmod desc, take top 20.
    Titles from slug (titlecased) — good enough for a news digest.
    """
    KNOWN_TITLES = {
        "seoul-office-partnerships-korean-ai-ecosystem": "Seoul Office: Partnerships for Korea's AI Ecosystem",
        "developing-nuclear-safeguards-for-ai-through-public-private-partnership": "Developing Nuclear Safeguards for AI",
        "tcs-anthropic-partnership": "Anthropic Partners with TCS to Advance Enterprise AI Safety",
        "core-views-on-ai-safety": "Core Views on AI Safety",
        "claude-fable-5-mythos-5": "Claude Fable 5 and Mythos 5",
        "fable-mythos-access": "Fable and Mythos Access Update",
        "anthropic-public-record": "Anthropic Public Record",
        "dxc-anthropic-alliance": "DXC and Anthropic Alliance",
        "claude-corps": "Introducing Claude Corps",
        "chris-olah-pope-leo-encyclical": "Chris Olah, Pope Leo, and the Encyclical on AI",
        "widening-conversation-ai": "Widening the Conversation on AI",
        "AI-enabled-cyber-threats-mitre-attack": "AI-Enabled Cyber Threats and MITRE ATT\u0026CK",
        "services-track-partner-hub": "Services Track Partner Hub",
        "expanding-project-glasswing": "Expanding Project Glasswing",
        "confidential-draft-s1-sec": "Confidential Draft S-1",
        "announcing-our-updated-responsible-scaling-policy": "Announcing Our Updated Responsible Scaling Policy",
    }

    articles = []
    xml = fetch_url("https://www.anthropic.com/sitemap.xml")
    if not xml:
        return articles

    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=7)  # only last week

    url_blocks = re.findall(r'<url>(.*?)</url>', xml, re.DOTALL)
    news_entries = []
    for block in url_blocks:
        loc_match = re.search(r'<loc>(https://www\.anthropic\.com/news/[^<]+)</loc>', block)
        lm_match = re.search(r'<lastmod>([^<]+)</lastmod>', block)
        if not loc_match:
            continue

        article_url = loc_match.group(1)
        if article_url == "https://www.anthropic.com/news":
            continue

        slug = article_url.rstrip('/').split('/')[-1]

        article_dt = None
        article_date = None
        if lm_match:
            try:
                # Anthropic sitemap uses ISO 8601 (e.g. 2026-06-22T16:10:15.486Z),
                # not RFC 2822 — use fromisoformat, not parsedate_to_datetime.
                article_dt = datetime.fromisoformat(lm_match.group(1).replace('Z', '+00:00'))
                article_date = article_dt.strftime('%Y-%m-%d')
            except:
                pass

        if article_dt and article_dt < cutoff:
            continue

        news_entries.append((article_dt or today, article_date or today.strftime('%Y-%m-%d'), slug, article_url))

    # Sort by lastmod desc, take top 5 (avoid spam from one source)
    news_entries.sort(key=lambda x: x[0], reverse=True)
    for _, article_date, slug, article_url in news_entries[:5]:
        title = KNOWN_TITLES.get(slug) or slug.replace('-', ' ').title()
        article_id = make_article_id("anthropic", article_url)
        articles.append({
            'id': article_id,
            'title': title,
            'url': article_url,
            'date': article_date,
            'importance': 4
        })
    articles = filter_already_seen(articles)
    return articles

def scan_openai(queue):
    """Scan OpenAI news via RSS feed."""
    articles = []
    url = "https://openai.com/blog/rss.xml"
    xml = fetch_url(url)
    if not xml:
        return articles
    
    import re
    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=14)
    
    for item in items:
        title_match = re.search(r'<title><!\[CDATA\[([^\]]+)\]\]></title>', item)
        link_match = re.search(r'<link>([^<]+)</link>', item)
        date_match = re.search(r'<pubDate>([^<]+)</pubDate>', item)
        
        if not title_match or not link_match:
            continue
        
        title = title_match.group(1).strip()
        article_url = link_match.group(1).strip()
        
        if len(title) < 10:
            continue
        
        article_date = None
        article_dt = None
        if date_match:
            try:
                from email.utils import parsedate_to_datetime
                article_dt = parsedate_to_datetime(date_match.group(1))
                article_date = article_dt.strftime('%Y-%m-%d')
            except:
                pass
        
        # Skip old articles (>7 days)
        if article_dt and article_dt < cutoff:
            continue
        
        article_id = make_article_id("openai", article_url)
        
        importance = 4
        if any(x in article_url.lower() for x in ['s-1', 'confidential', 'ipo', 'acquisition']):
            importance = 5
        
        # Extract description from CDATA
        desc_match = re.search(r'<description><!\[CDATA\[([^\]]+)\]\]></description>', item)
        description = desc_match.group(1).strip() if desc_match else None
        
        articles.append({
            'id': article_id,
            'title': title,
            'url': article_url,
            'date': article_date or today.strftime('%Y-%m-%d'),
            'importance': importance,
            'description': description
        })
    articles = filter_already_seen(articles)
    return articles

def scan_deepmind(queue):
    """Scan DeepMind blog via sitemap.
    
    DeepMind articles are loaded via JavaScript, so we can't parse HTML for links.
    Instead, we fetch the sitemap, get recent blog URLs, and fetch each page
    to extract the title.
    """
    articles = []
    
    # Fetch sitemap
    sitemap_url = "https://deepmind.google/sitemap.xml"
    xml = fetch_url(sitemap_url)
    if not xml:
        return articles
    
    # Parse blog URLs from sitemap
    blog_urls = re.findall(r'<loc>(https://deepmind\.google/blog/[^<]+)</loc>', xml)
    blog_urls = [u for u in blog_urls if not u.endswith('/blog/')]
    
    if not blog_urls:
        return articles
    
    # Sort by URL (reverse) to get most recent first
    blog_urls.sort(reverse=True)
    
    # Take only last 5 to avoid too many HTTP requests
    for article_url in blog_urls[:5]:
        article_html = fetch_url(article_url)
        if not article_html:
            continue
        
        # Extract title from <title> tag
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', article_html)
        if not title_match:
            continue
        
        title = title_match.group(1).strip()
        # Clean common suffixes
        title = re.sub(r'\s*[-–] Google DeepMind\s*$', '', title)
        
        if len(title) < 10:
            continue
        
        article_id = make_article_id("deepmind", article_url)
        
        # Extract meta description from article page
        # DeepMind uses <meta content="..." name=description> (no quotes around name=value)
        desc_match = re.search(r'<meta content="([^"]+)" name=description', article_html)
        if not desc_match:
            desc_match = re.search(r'<meta content="([^"]+)" property="og:description"', article_html)
        description = desc_match.group(1).strip() if desc_match else None
        
        articles.append({
            'id': article_id,
            'title': title,
            'url': article_url,
            'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'importance': 4,
            'description': description
        })
    
    articles = filter_already_seen(articles)
    return articles

def scan_rbc(queue):
    """Scan RBC AI news."""
    articles = []
    url = "https://trends.rbc.ru/trends/industry/69e87e5f9a7947ca488a8d90"
    html = fetch_url(url)
    if not html:
        return articles
    
    # RBC: only match actual article URLs (contain /technology_and_media/ or /economics/ etc.)
    # Skip navigation links with utm_source, from=topline, etc.
    article_pattern = re.compile(
        r'href="(https://www\.rbc\.ru/(?:technology_and_media|economics|politics|society)/[^"]+)"[^>]*>([^<]{20,200})<'
    )
    today = datetime.now()
    cutoff = today - timedelta(days=14)
    
    seen_ids = set()
    for match in article_pattern.finditer(html):
        article_url = match.group(1)
        title = match.group(2).strip()
        
        # Skip if contains tracking params
        if 'utm_source' in article_url or 'from=' in article_url:
            continue
        
        url_date = extract_date_from_url(article_url)
        if url_date:
            try:
                dt = datetime.strptime(url_date, "%d/%m/%Y")
                if dt < cutoff:
                    continue
            except ValueError:
                pass
        
        article_id = article_url.rstrip('/').split('/')[-1]
        # Skip if ID is too short (likely navigation)
        if len(article_id) < 10:
            continue
        if article_id in seen_ids:
            continue
        seen_ids.add(article_id)
        
        article_id = f"rbc-{article_id}"
        
        articles.append({
            'id': article_id,
            'title': title,
            'url': article_url,
            'date': url_date or today.strftime('%Y-%m-%d'),
            'importance': 4
        })
    articles = filter_already_seen(articles)
    return articles

def scan_huggingface(queue):
    """Scan Hugging Face blog via RSS."""
    articles = []
    url = "https://huggingface.co/blog/feed.xml"
    xml = fetch_url(url)
    if not xml:
        return articles
    
    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=14)
    
    for item in items:
        # Support both CDATA and plain text formats
        title_match = re.search(r'<title>(?:<!\[CDATA\[)?([^\]<]+)(?:\]\]>)?</title>', item)
        link_match = re.search(r'<link>([^<]+)</link>', item)
        date_match = re.search(r'<pubDate>([^<]+)</pubDate>', item)
        desc_match = re.search(r'<description>(?:<!\[CDATA\[)?([^\]<]+)(?:\]\]>)?</description>', item)
        
        if not title_match or not link_match:
            continue
        
        title = title_match.group(1).strip()
        article_url = link_match.group(1).strip()
        
        if len(title) < 10:
            continue
        
        article_dt = None
        article_date = None
        if date_match:
            try:
                from email.utils import parsedate_to_datetime
                article_dt = parsedate_to_datetime(date_match.group(1))
                article_date = article_dt.strftime('%Y-%m-%d')
            except:
                pass
        
        if article_dt and article_dt < cutoff:
            continue
        
        article_id = make_article_id("huggingface", article_url)
        
        description = desc_match.group(1).strip() if desc_match else None
        # Strip HTML tags from description
        if description:
            description = re.sub(r'<[^>]+>', '', description)[:300]
        
        articles.append({
            'id': article_id,
            'title': title,
            'url': article_url,
            'date': article_date or today.strftime('%Y-%m-%d'),
            'importance': 4,
            'description': description
        })
    articles = filter_already_seen(articles)
    return articles

def scan_arxiv_ai(queue):
    """Scan arxiv cs.AI via API (Atom feed). Returns list of articles."""
    articles = []
    # arxiv API: latest 15 papers from cs.AI category
    url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI&start=0&max_results=15&sortBy=submittedDate&sortOrder=descending"
    xml = fetch_url(url, timeout=15)
    if not xml:
        return articles

    # Atom feed: <entry>...</entry>
    items = re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL)
    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=7)  # arxiv moves fast, only last week

    for item in items:
        # Atom uses <title>, <id>, <updated>, <summary>
        title_match = re.search(r'<title>(?:<!\[CDATA\[)?([^\]<]+)(?:\]\]>)?</title>', item)
        id_match = re.search(r'<id>([^<]+)</id>', item)
        updated_match = re.search(r'<updated>([^<]+)</updated>', item)
        summary_match = re.search(r'<summary>(?:<!\[CDATA\[)?([^\]<]+)(?:\]\]>)?</summary>', item)

        if not title_match or not id_match:
            continue

        title = title_match.group(1).strip()
        # Strip newlines and extra spaces
        title = re.sub(r'\s+', ' ', title)
        if len(title) < 10:
            continue

        arxiv_id = id_match.group(1).strip()
        # arxiv id looks like http://arxiv.org/abs/2506.12345v1
        # extract the paper id part
        abs_match = re.search(r'abs/([^v]+)', arxiv_id)
        if not abs_match:
            continue
        paper_id = abs_match.group(1)
        article_url = f"https://arxiv.org/abs/{paper_id}"

        # Parse updated date
        article_date = None
        article_dt = None
        if updated_match:
            try:
                article_dt = datetime.fromisoformat(updated_match.group(1).replace('Z', '+00:00'))
                article_date = article_dt.strftime('%Y-%m-%d')
            except:
                pass

        if article_dt and article_dt < cutoff:
            continue

        description = None
        if summary_match:
            description = re.sub(r'\s+', ' ', summary_match.group(1).strip())[:300]

        article_id_str = f"arxiv-{paper_id}"

        articles.append({
            'id': article_id_str,
            'title': title,
            'url': article_url,
            'date': article_date or today.strftime('%Y-%m-%d'),
            'importance': 3,  # arxiv papers are research, lower default priority
            'description': description
        })
    articles = filter_already_seen(articles)

    # === ARXIV AI-IMPACT FILTER ===
    # cs.AI категория содержит много академических работ без реального AI-impact.
    # Оставляем только те, что содержат ключевые слова про модели/возможности/архитектуры.
    if articles:
        AI_IMPACT_ARXIV_KEYWORDS = [
            # Model releases / capabilities
            r"\bGPT\b", r"\bClaude\b", r"\bGemini\b", r"\bLlama\b", r"\bGrok\b",
            r"\bMixtral\b", r"\bMistral\b", r"\bDeepSeek\b", r"\bQwen\b",
            r"\bPhi\b", r"\bSora\b", r"\bDALL-?E\b",
            # Capabilities
            r"\bagent", r"\btool use", r"\breasoning", r"\bchain[- ]of[- ]thought",
            r"\bmultimodal\b", r"\bvision", r"\bRLHF\b", r"\bRLAIF\b",
            r"\bsafety\b", r"\balignment\b", r"\binterpretability\b",
            r"\bcontext window\b", r"\btoken\b",
            r"\bretrieval\b", r"\bRAG\b",
            r"\bbenchmark\b", r"\bSOTA\b",
            r"\bAGI\b", r"\bsuperintelligence\b",
            # Architectures / methods (high impact)
            r"\bMixture of Experts\b", r"\bMoE\b",
            r"\bdiffusion\b", r"\btransformer\b",
            r"\bfine[- ]tune", r"\bpre[- ]train",
            r"\bin[- ]context learning\b",
        ]
        _arxiv_pat = re.compile("|".join(AI_IMPACT_ARXIV_KEYWORDS), re.IGNORECASE)
        _arxiv_filtered = []
        for _a in articles:
            _text = f"{_a.get('title', '')} {_a.get('description', '')}"
            if _arxiv_pat.search(_text):
                # Keep arxiv importance at 3+ (don't lower it via AI scoring)
                _a['importance'] = max(_a.get('importance', 3), 3)
                _arxiv_filtered.append(_a)
        try:
            log_event(SCRIPT_NAME, "arxiv_filter", {
                "before": len(articles),
                "after": len(_arxiv_filtered),
            })
        except Exception:
            pass
        articles = _arxiv_filtered

    return articles

def scan_mistral(queue):
    """Scan Mistral AI news via their news page."""
    articles = []
    url = "https://mistral.ai/news/"
    html = fetch_url(url)
    if not html:
        return articles
    
    # Find news item links
    pattern = re.compile(r'href="(https://mistral\.ai/news/[^ "]+)"[^>]*>([^<]{10,100})<')
    today = datetime.now()
    cutoff = today - timedelta(days=14)
    
    for match in pattern.finditer(html):
        article_url = match.group(1)
        title = match.group(2).strip()
        
        if len(title) < 10:
            continue
        
        article_id = make_article_id("mistral", article_url)
        
        articles.append({
            'id': article_id,
            'title': title,
            'url': article_url,
            'date': today.strftime('%Y-%m-%d'),
            'importance': 4
        })
    articles = filter_already_seen(articles)
    return articles

def scan_meta_ai(queue):
    """Scan Meta AI blog via RSS."""
    articles = []
    url = "https://ai.meta.com/blog/rss.xml"
    xml = fetch_url(url)
    if not xml:
        # Try alternative feed
        url = "https://about.fb.com/news/rss/"
        xml = fetch_url(url)
    if not xml:
        return articles
    
    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=14)
    
    for item in items:
        title_match = re.search(r'<title>(?:<!\[CDATA\[)?([^\]<]+)(?:\]\]>)?</title>', item)
        link_match = re.search(r'<link>([^<]+)</link>', item)
        date_match = re.search(r'<pubDate>([^<]+)</pubDate>', item)
        
        if not title_match or not link_match:
            continue
        
        title = title_match.group(1).strip()
        article_url = link_match.group(1).strip()
        
        if len(title) < 10:
            continue
        
        article_dt = None
        article_date = None
        if date_match:
            try:
                from email.utils import parsedate_to_datetime
                article_dt = parsedate_to_datetime(date_match.group(1))
                article_date = article_dt.strftime('%Y-%m-%d')
            except:
                pass
        
        if article_dt and article_dt < cutoff:
            continue
        
        article_id = make_article_id("meta", article_url)
        
        articles.append({
            'id': article_id,
            'title': title,
            'url': article_url,
            'date': article_date or today.strftime('%Y-%m-%d'),
            'importance': 4
        })
    articles = filter_already_seen(articles)
    return articles

def scan_microsoft_ai(queue):
    """Scan Microsoft AI blog via RSS."""
    articles = []
    url = "https://techcommunity.microsoft.com/api/rss/ai-and-mixed-reality/?direction=desc"
    xml = fetch_url(url)
    if not xml:
        # Try Microsoft Research AI feed
        url = "https://www.microsoft.com/en-us/research/feed/"
        xml = fetch_url(url)
    if not xml:
        return articles
    
    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=14)
    
    for item in items:
        title_match = re.search(r'<title>(?:<!\[CDATA\[)?([^\]<]+)(?:\]\]>)?</title>', item)
        link_match = re.search(r'<link>([^<]+)</link>', item)
        date_match = re.search(r'<pubDate>([^<]+)</pubDate>', item)
        
        if not title_match or not link_match:
            continue
        
        title = title_match.group(1).strip()
        article_url = link_match.group(1).strip()
        
        if len(title) < 10:
            continue
        
        article_dt = None
        article_date = None
        if date_match:
            try:
                from email.utils import parsedate_to_datetime
                article_dt = parsedate_to_datetime(date_match.group(1))
                article_date = article_dt.strftime('%Y-%m-%d')
            except:
                pass
        
        if article_dt and article_dt < cutoff:
            continue
        
        article_id = make_article_id("microsoft", article_url)
        
        articles.append({
            'id': article_id,
            'title': title,
            'url': article_url,
            'date': article_date or today.strftime('%Y-%m-%d'),
            'importance': 4
        })
    articles = filter_already_seen(articles)
    return articles

def scan_stanford_hai(queue):
    """Scan Stanford HAI AI Index Report."""
    articles = []
    # The AI Index Report is a major annual publication
    url = "https://hai.stanford.edu/ai-index/2026-ai-index-report"
    html = fetch_url(url)
    if not html:
        return articles
    
    title = "Stanford HAI AI Index Report 2026"
    article_id = "stanford-hai-ai-index-2026"
    
    # Extract description
    desc_match = re.search(r'<meta content="([^"]+)" name="description"', html)
    description = desc_match.group(1).strip() if desc_match else None
    
    articles.append({
        'id': article_id,
        'title': title,
        'url': url,
        'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'importance': 5,
        'description': description or "Stanford HAI опубликовал ежегодный AI Index Report 2026 — ключевой документ о состоянии AI-индустрии."
    })
    articles = filter_already_seen(articles)
    return articles

def scan_google_ai(queue):
    """Scan Google AI blog via RSS."""
    articles = []
    url = "https://blog.google/technology/ai/rss/"
    xml = fetch_url(url)
    if not xml:
        return articles

    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=14)

    for item in items:
        title_match = re.search(r'<title>(?:<!\[CDATA\[)?([^<\]]+)(?:\]\]>)?</title>', item)
        link_match = re.search(r'<link>([^<]+)</link>', item)
        date_match = re.search(r'<pubDate>([^<]+)</pubDate>', item)

        if not title_match or not link_match:
            continue

        title = title_match.group(1).strip()
        article_url = link_match.group(1).strip()

        if len(title) < 10:
            continue

        article_dt = None
        article_date = None
        if date_match:
            try:
                from email.utils import parsedate_to_datetime
                article_dt = parsedate_to_datetime(date_match.group(1))
                article_date = article_dt.strftime('%Y-%m-%d')
            except:
                pass

        if article_dt and article_dt < cutoff:
            continue

        article_id = make_article_id("google", article_url)

        articles.append({
            'id': article_id,
            'title': title,
            'url': article_url,
            'date': article_date or today.strftime('%Y-%m-%d'),
            'importance': 4
        })
    articles = filter_already_seen(articles)
    return articles


def scan_techcrunch_ai(queue):
    """Scan TechCrunch AI news via RSS."""
    articles = []
    url = "https://techcrunch.com/category/artificial-intelligence/feed/"
    xml = fetch_url(url)
    if not xml:
        return articles

    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=14)

    for item in items:
        title_match = re.search(r'<title>(?:<!\[CDATA\[)?([^<\]]+)(?:\]\]>)?</title>', item)
        link_match = re.search(r'<link>([^<]+)</link>', item)
        date_match = re.search(r'<pubDate>([^<]+)</pubDate>', item)


        if not title_match or not link_match:
            continue

        title = title_match.group(1).strip()
        article_url = link_match.group(1).strip()


        if len(title) < 10:
            continue

        article_dt = None
        article_date = None
        if date_match:
            try:
                from email.utils import parsedate_to_datetime
                article_dt = parsedate_to_datetime(date_match.group(1))
                article_date = article_dt.strftime('%Y-%m-%d')
            except:
                pass

        if article_dt and article_dt < cutoff:
            continue

        article_id = make_article_id("techcrunch", article_url)


        articles.append({
            'id': article_id,
            'title': title,
            'url': article_url,
            'date': article_date or today.strftime('%Y-%m-%d'),
            'importance': 4
        })
    articles = filter_already_seen(articles)
    return articles


def scan_justai(queue):
    """Scan JustAI blog news."""
    articles = []
    url = "https://just-ai.com/blog/news"
    html = fetch_url(url)
    if not html:
        return articles

    pattern = re.compile(r'href="(https://just-ai\.com/blog/[^"]+)"[^>]*>([^<]{10,200})<')
    today = datetime.now()
    cutoff = today - timedelta(days=14)

    for match in pattern.finditer(html):
        article_url = match.group(1)
        title = match.group(2).strip()


        if len(title) < 10:
            continue

        article_id = make_article_id("justai", article_url)

        articles.append({
            'id': article_id,
            'title': title,
            'url': article_url,
            'date': today.strftime('%Y-%m-%d'),
            'importance': 4
        })
    articles = filter_already_seen(articles)
    return articles


def scan_neural_digest(queue):
    """Scan Neural Digest — Russian AI news aggregator via RSS."""
    articles = []
    url = "https://neural-digest.ru/feed/"
    xml = fetch_url(url)
    if not xml:
        return articles

    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=14)


    for item in items:
        title_match = re.search(r'<title>(?:<!\[CDATA\[)?([^<\]]+)(?:\]\]>)?</title>', item)
        link_match = re.search(r'<link>([^<]+)</link>', item)
        date_match = re.search(r'<pubDate>([^<]+)</pubDate>', item)

        if not title_match or not link_match:
            continue

        title = title_match.group(1).strip()
        article_url = link_match.group(1).strip()

        if len(title) < 10:
            continue

        article_dt = None
        article_date = None
        if date_match:
            try:
                from email.utils import parsedate_to_datetime
                article_dt = parsedate_to_datetime(date_match.group(1))
                article_date = article_dt.strftime('%Y-%m-%d')
            except:
                pass

        if article_dt and article_dt < cutoff:
            continue

        article_id = make_article_id("neuraldigest", article_url)

        articles.append({
            'id': article_id,
            'title': title,
            'url': article_url,
            'date': article_date or today.strftime('%Y-%m-%d'),
            'importance': 4
        })
    articles = filter_already_seen(articles)
    return articles


# === NEW SCANNERS (added 2026-07-13) ===
# Эти сканеры используют существующий fetch_url() helper (urllib), чтобы не тянуть requests/BeautifulSoup.
# Если URL заблокирован Cloudflare/bot-protection, сканер тихо возвращает пустой список (fail-open).

def scan_cursor_changelog(queue):
    """Scan Cursor changelog via HTML (URL paths like /changelog/side-chat)."""
    articles = []
    url = "https://cursor.com/changelog"
    html = fetch_url(url, timeout=15)
    if not html:
        return articles

    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=14)

    # Match href="/changelog/SLUG" + nearby title text
    # Pattern: <a ... href="/changelog/SLUG">Title</a>
    pattern = re.compile(
        r'href="/changelog/([a-z0-9][a-z0-9-]*)"[^>]*>([^<]{10,200})</a>',
        re.IGNORECASE,
    )
    seen = set()
    for m in pattern.finditer(html):
        slug = m.group(1)
        title = m.group(2).strip()
        article_url = f"https://cursor.com/changelog/{slug}"
        if slug in seen or len(title) < 10:
            continue
        seen.add(slug)

        article_id = make_article_id("cursor", article_url)
        articles.append({
            "id": article_id,
            "title": title,
            "url": article_url,
            "date": today.strftime('%Y-%m-%d'),
            "importance": 4,
        })
        if len(articles) >= 10:
            break
    articles = filter_already_seen(articles)
    return articles


def scan_cohere(queue):
    """Scan Cohere blog via HTML (relative /blog/<slug> URLs)."""
    articles = []
    url = "https://cohere.com/blog"
    html = fetch_url(url, timeout=15)
    if not html:
        return articles

    today = datetime.now()
    pattern = re.compile(
        r'href="/blog/([a-z0-9][a-z0-9-]*)"',
        re.IGNORECASE,
    )
    # Get titles via any nearby text inside <h2>/<h3>; fallback to slug
    title_pattern = re.compile(
        r'href="/blog/([a-z0-9][a-z0-9-]*)"[^>]*>\s*([^<]{10,200})',
        re.IGNORECASE,
    )
    seen = set()
    for m in title_pattern.finditer(html):
        slug = m.group(1)
        title = m.group(2).strip()
        if slug in seen or len(title) < 10:
            continue
        # Skip tag pages
        if slug.startswith("tag/") or slug.startswith("category/"):
            continue
        seen.add(slug)

        article_url = f"https://cohere.com/blog/{slug}"
        article_id = make_article_id("cohere", article_url)
        articles.append({
            "id": article_id,
            "title": title,
            "url": article_url,
            "date": today.strftime('%Y-%m-%d'),
            "importance": 4,
        })
        if len(articles) >= 10:
            break
    articles = filter_already_seen(articles)
    return articles


def scan_github_copilot(queue):
    """Scan GitHub Copilot changelog via RSS feed."""
    articles = []
    url = "https://github.blog/changelog/label/copilot/feed/"
    xml = fetch_url(url, timeout=15)
    if not xml:
        return articles

    items = re.findall(r'<item>(.*?)</item>', xml, re.DOTALL)
    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=14)

    for item in items:
        title_match = re.search(r'<title>(?:<!\[CDATA\[)?([^<\]]+)(?:\]\]>)?</title>', item)
        link_match = re.search(r'<link>([^<]+)</link>', item)
        date_match = re.search(r'<pubDate>([^<]+)</pubDate>', item)

        if not title_match or not link_match:
            continue

        title = title_match.group(1).strip()
        article_url = link_match.group(1).strip()
        if len(title) < 10:
            continue

        article_dt = None
        article_date = None
        if date_match:
            try:
                from email.utils import parsedate_to_datetime
                article_dt = parsedate_to_datetime(date_match.group(1))
                article_date = article_dt.strftime('%Y-%m-%d')
            except Exception:
                pass

        if article_dt and article_dt < cutoff:
            continue

        article_id = make_article_id("github-copilot", article_url)
        articles.append({
            "id": article_id,
            "title": title,
            "url": article_url,
            "date": article_date or today.strftime('%Y-%m-%d'),
            "importance": 4,
        })
        if len(articles) >= 10:
            break
    articles = filter_already_seen(articles)
    return articles


def scan_claude_code(queue):
    """Scan Anthropic Claude Code changelog from raw GitHub CHANGELOG.md.

    Source: https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md
    Format: `## VERSION` headings, e.g. `## 2.1.207`.
    """
    articles = []
    url = "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"
    md = fetch_url(url, timeout=15)
    if not md:
        return articles

    today = datetime.now(timezone.utc)
    # Find all `## VERSION` headings, take top 5 most recent
    version_pattern = re.compile(r'^##\s+([0-9][^\n]+)$', re.MULTILINE)
    matches = list(version_pattern.finditer(md))
    # Version headings are typically listed newest first
    seen_versions = set()
    for m in matches[:5]:
        version = m.group(1).strip()
        if version in seen_versions:
            continue
        seen_versions.add(version)

        # Extract first line of body as a summary (skip empty lines)
        body_start = m.end()
        body_end = matches[matches.index(m) + 1].start() if matches.index(m) + 1 < len(matches) else len(md)
        body = md[body_start:body_end].strip()
        first_bullet = re.search(r'-\s+(.{20,200}?)[\.\n]', body)
        summary = first_bullet.group(1).strip() if first_bullet else ""

        article_url = f"https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#{version.replace('.', '')}"
        article_id = make_article_id("claude-code", f"claude-code-{version}")
        articles.append({
            "id": article_id,
            "title": f"Claude Code {version}",
            "url": article_url,
            "date": today.strftime('%Y-%m-%d'),
            "importance": 4,
            "description": summary,
        })
    articles = filter_already_seen(articles)
    return articles


# === Source-specific stubs: Cloudflare-blocked, но оставлены как fallback (fail-open) ===

def scan_xai(queue):
    """Scan xAI (Grok) blog.

    TODO: x.ai блокирует urllib/Cloudflare — fetch_url() возвращает None.
    Сейчас сканер возвращает пустой список. Когда у xAI появится RSS feed
    или будет настроен обход Cloudflare — добавить реальный парсинг.
    Запасной URL: https://x.ai/blog (404 / block).
    """
    articles = []
    html = fetch_url("https://x.ai/blog", timeout=10)
    if not html:
        # TODO: Cloudflare blocks urllib — keep returning empty
        return articles

    # На случай если Cloudflare пропустит: простой regex по /blog/<slug>
    pattern = re.compile(r'href="(https?://x\.ai/blog/[^"]+)"[^>]*>([^<]{10,200})</a>')
    for m in pattern.finditer(html):
        article_url = m.group(1)
        title = m.group(2).strip()
        if len(title) < 10:
            continue
        article_id = make_article_id("xai", article_url)
        articles.append({
            "id": article_id,
            "title": title,
            "url": article_url,
            "date": datetime.now().strftime('%Y-%m-%d'),
            "importance": 4,
        })
        if len(articles) >= 10:
            break
    articles = filter_already_seen(articles)
    return articles


def scan_deepseek(queue):
    """Scan DeepSeek news.

    TODO: deepseek.com/blog — JS-rendered Next.js, нет RSS. urllib получает
    пустую оболочку без постов. Когда появится RSS/atom или официальный API —
    добавить реальный парсинг.
    Запасной URL: https://api-docs.deepseek.com/news/ (Docusaurus, не новости).
    """
    # TODO: DeepSeek blog is JS-rendered, no RSS feed available
    return []


def scan_perplexity(queue):
    """Scan Perplexity AI blog.

    TODO: perplexity.ai/hub/blog — Cloudflare блокирует urllib (HTTP 403).
    RSS feed на /hub/blog/rss.xml тоже за Cloudflare.
    Сейчас сканер возвращает пустой список. Когда будет найден
    рабочий endpoint или настроен обход — добавить парсинг.
    """
    articles = []
    html = fetch_url("https://www.perplexity.ai/hub/blog", timeout=10)
    if not html:
        # TODO: Cloudflare blocks urllib — keep returning empty
        return articles

    pattern = re.compile(r'href="(https?://(?:www\.)?perplexity\.ai/hub/blog/[^"]+)"[^>]*>([^<]{10,200})</a>')
    for m in pattern.finditer(html):
        article_url = m.group(1)
        title = m.group(2).strip()
        if len(title) < 10:
            continue
        article_id = make_article_id("perplexity", article_url)
        articles.append({
            "id": article_id,
            "title": title,
            "url": article_url,
            "date": datetime.now().strftime('%Y-%m-%d'),
            "importance": 4,
        })
        if len(articles) >= 10:
            break
    articles = filter_already_seen(articles)
    return articles


def is_duplicate(article_id, queue, article_url=None):
    """Check if article is already in published, pending, or selection_queue.
    Checks both ID and URL to catch renamed duplicates.
    URL comparison is normalized (trailing slash stripped)."""
    # Normalize URL for comparison
    norm_url = article_url.rstrip('/') if article_url else None
    
    # Check published[] by ID
    published_ids = [p['id'] for p in queue.get('published', [])]
    if article_id in published_ids:
        return True
    
    # Check published[] by normalized URL (catch renamed duplicates)
    if norm_url:
        published_urls = [p['url'].rstrip('/') for p in queue.get('published', [])]
        if norm_url in published_urls:
            return True
    
    # Check pending[] by ID
    pending_ids = [p['id'] for p in queue.get('pending', [])]
    if article_id in pending_ids:
        return True
    
    # Check pending[] by normalized URL
    if norm_url:
        pending_urls = [p['url'].rstrip('/') for p in queue.get('pending', [])]
        if norm_url in pending_urls:
            return True
    
    # Check selection_queue
    try:
        sel = load_selection()
        sel_ids = [a['id'] for a in sel.get('articles', [])]
        if article_id in sel_ids:
            return True
        # Also check by normalized URL in selection
        if norm_url:
            sel_urls = [a['url'].rstrip('/') for a in sel.get('articles', [])]
            if norm_url in sel_urls:
                return True
    except:
        pass
    
    return False

def main():
    run_ts = datetime.now(timezone.utc).isoformat()
    run_id = f"scan:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    log_event(SCRIPT_NAME, "started", {"run_ts": run_ts, "run_id": run_id})
    log_run_event(run_id, "scan", "started", {"run_ts": run_ts})
    
    # Use same lock file as publisher to prevent concurrent access
    lock_path = str(PENDING_QUEUE) + '.lock'
    lock_fd = None
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Scan already running, exiting.")
        log_event(SCRIPT_NAME, "skipped", {"reason": "already_running", "run_ts": run_ts})
        return
    
    try:
        queue = load_queue()
        
        # Collect all published IDs for quick lookup
        published_ids = [p['id'] for p in queue.get('published', [])]
        pending_ids = [p['id'] for p in queue.get('pending', [])]
    
        new_pending = []
        new_selection = []
        skipped_duplicates = []
        
        # Scan all sources
        sources = [
            ('Anthropic', scan_anthropic),
            ('OpenAI', scan_openai),
            ('DeepMind', scan_deepmind),
            ('HuggingFace', scan_huggingface),
            ('Mistral', scan_mistral),
            ('Meta AI', scan_meta_ai),
            ('Microsoft AI', scan_microsoft_ai),
            ('Stanford HAI', scan_stanford_hai),
            ('РБК', scan_rbc),
            ('Google AI', scan_google_ai),
            ('TechCrunch AI', scan_techcrunch_ai),
            ('JustAI', scan_justai),
            ('Neural Digest', scan_neural_digest),
            ('arXiv cs.AI', scan_arxiv_ai),
            # === Tier 1 (primary AI labs) ===
            ('DeepSeek', scan_deepseek),
            ('xAI', scan_xai),
            # === Tier 2 (LLM/agent companies) ===
            ('Cohere', scan_cohere),
            ('Perplexity AI', scan_perplexity),
            ('Claude Code', scan_claude_code),
            ('GitHub Copilot', scan_github_copilot),
            ('Cursor', scan_cursor_changelog),
        ]
        
        source_results = {}
        for name, scanner in sources:
            t0_scan = time.monotonic()
            try:
                articles = scanner(queue)
                scan_ms = int((time.monotonic() - t0_scan) * 1000)
                source_results[name] = {"total": len(articles), "new": 0, "dup": 0}
                log_source_health(name, ok=True, fetch_ms=scan_ms, items_found=len(articles))
                for art in articles:
                    if is_duplicate(art['id'], queue, art.get('url')):
                        source_results[name]["dup"] += 1
                        skipped_duplicates.append({
                            "article_id": art['id'],
                            "source": name,
                            "title": art['title'][:80],
                            "url": art['url']
                        })
                        log_event(SCRIPT_NAME, "duplicate_skipped", {
                            "article_id": art['id'],
                            "source": name,
                            "title": art['title'][:80]
                        })
                        continue
                    source_results[name]["new"] += 1

                    # === AI Impact Scoring (Point 2) ===
                    # Recompute importance using content-aware scoring
                    importance = art['importance']
                    ai_impact = None
                    if compute_impact is not None:
                        try:
                            _r = compute_impact(
                                title=art['title'],
                                summary=art.get('description', ''),
                                source=name,
                            )
                            importance = _r.total
                            ai_impact = _r.to_dict()
                        except Exception as e:
                            log_error(SCRIPT_NAME, f"impact_scoring failed for {art['id']}: {e}")

                    new_pending.append({
                        'id': art['id'],
                        'source': name,
                        'title': art['title'],
                        'url': art['url'],
                        'summary': art.get('description', ''),
                        'importance': importance,
                        'ai_impact': ai_impact,
                        'date': art['date']
                    })
                    if importance == 5:
                        new_selection.append(art)
                    # Funnel: enqueued (scanned + new)
                    funnel_set(art['id'], 'enqueued',
                               source=name, importance=importance,
                               scan_ms=scan_ms)
            except Exception as e:
                scan_ms = int((time.monotonic() - t0_scan) * 1000)
                print(f"Error scanning {name}: {e}", file=sys.stderr)
                log_error(SCRIPT_NAME, f"scanner {name} raised: {e}")
                log_source_health(name, ok=False, fetch_ms=scan_ms, error=str(e))
                source_results[name] = {"total": 0, "new": 0, "dup": 0, "error": str(e)}
        
        # Add new items to pending
        for item in new_pending:
            queue['pending'].append(item)
        
        # Add importance=5 to selection_queue
        if new_selection:
            sel = load_selection()
            for art in new_selection:
                # Check again against selection
                sel_ids = [a['id'] for a in sel.get('articles', [])]
                if art['id'] not in sel_ids:
                    sel['articles'].append({
                        'id': art['id'],
                        'source': 'OpenAI',
                        'title': art['title'],
                        'url': art['url'],
                        'summary': art.get('description', ''),
                        'importance': art['importance'],
                        'date': art['date'],
                        'added_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                        'status': 'new'
                    })
            save_selection(sel)
        
        # Update sources last_checked
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        for src in queue.get('sources', []):
            src['last_checked'] = now
        
        save_queue(queue)
        
        print(f"Scan complete. Added {len(new_pending)} to pending, {len(new_selection)} to selection.")
        print(f"Pending total: {len(queue['pending'])}")
        
        log_event(SCRIPT_NAME, "completed", {
            "run_ts": run_ts,
            "run_id": run_id,
            "new_pending": len(new_pending),
            "new_selection": len(new_selection),
            "pending_total": len(queue['pending']),
            "skipped_dup_count": len(skipped_duplicates),
            "source_results": source_results,
            "skipped_duplicates": skipped_duplicates[:20]  # first 20 for detail
        })
        log_run_event(run_id, "scan", "completed",
                      {"new_pending": len(new_pending),
                       "pending_total": len(queue['pending']),
                       "skipped_dup_count": len(skipped_duplicates),
                       "source_results": source_results})
    
    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            try:
                os.unlink(lock_path)
            except:
                pass

if __name__ == '__main__':
    main()
