"""arXiv cs.AI via API (Atom feed).

Returns the 15 most recent papers, then filters by AI-impact keywords
(models, capabilities, architectures). This is the cheap way to cut
through academic noise.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from agentsblog.models import Article, ArticleStatus, SourceKind
from agentsblog.sources import base as _b
from agentsblog.sources.base import Registry, is_within_days, parse_iso_to_date, strip_html
from agentsblog.sources.registry import add_meta


# Cheap academic-impact filter — keep only papers mentioning model/agent/
# capability keywords. Otherwise arxiv dumps 15 unrelated physics/control papers.
_AI_IMPACT_PATTERNS = [
    r"\bGPT\b", r"\bClaude\b", r"\bGemini\b", r"\bLlama\b", r"\bGrok\b",
    r"\bMixtral\b", r"\bMistral\b", r"\bDeepSeek\b", r"\bQwen\b",
    r"\bPhi\b", r"\bSora\b", r"\bDALL-?E\b",
    r"\bagent", r"\btool use", r"\breasoning", r"\bchain[- ]of[- ]thought",
    r"\bmultimodal\b", r"\bvision", r"\bRLHF\b", r"\bRLAIF\b",
    r"\bsafety\b", r"\balignment\b", r"\binterpretability\b",
    r"\bcontext window\b", r"\btoken\b", r"\bretrieval\b", r"\bRAG\b",
    r"\bbenchmark\b", r"\bSOTA\b", r"\bAGI\b", r"\bsuperintelligence\b",
    r"\bMixture of Experts\b", r"\bMoE\b",
    r"\bdiffusion\b", r"\btransformer\b",
    r"\bfine[- ]tune", r"\bpre[- ]train", r"\bin[- ]context learning\b",
]
_AI_IMPACT_RE = re.compile("|".join(_AI_IMPACT_PATTERNS), re.IGNORECASE)


@Registry.register("arxiv")
class ArxivSource:
    def __init__(self, source):
        self.source = source
        self.api_url = (
            "http://export.arxiv.org/api/query"
            "?search_query=cat:cs.AI&start=0&max_results=15"
            "&sortBy=submittedDate&sortOrder=descending"
        )
        self.cutoff_days = 7
        self.per_source_limit = 10

    def scan(self):
        result = _b.fetch(self.api_url, timeout=20)
        self.last_fetch = result
        if not result.body:
            return []
        today = datetime.now(timezone.utc)
        cutoff = today - timedelta(days=self.cutoff_days)
        out = []
        for entry in re.findall(r"<entry>(.*?)</entry>", result.body, re.DOTALL):
            title_m = re.search(r"<title>(?:<!\[CDATA\[)?([^\]<]+)(?:\]\]>)?</title>", entry)
            id_m = re.search(r"<id>([^<]+)</id>", entry)
            updated_m = re.search(r"<updated>([^<]+)</updated>", entry)
            summary_m = re.search(r"<summary>(?:<!\[CDATA\[)?([^\]<]+)(?:\]\]>)?</summary>", entry)
            if not title_m or not id_m:
                continue
            title = re.sub(r"\s+", " ", title_m.group(1).strip())
            if len(title) < 10:
                continue
            abs_m = re.search(r"abs/([^v]+)", id_m.group(1).strip())
            if not abs_m:
                continue
            paper_id = abs_m.group(1)
            url = f"https://arxiv.org/abs/{paper_id}"
            dt, date_str = parse_iso_to_date(updated_m.group(1)) if updated_m else (None, None)
            if dt and not is_within_days(dt, cutoff_days=self.cutoff_days, now=today):
                continue
            summary = strip_html(summary_m.group(1)) if summary_m else ""
            # AI-impact filter
            text = f"{title} {summary}"
            if not _AI_IMPACT_RE.search(text):
                continue
            from agentsblog.sources.base import make_article_id
            out.append(Article(
                id=f"arxiv-{paper_id}",
                source_id=self.source.id,
                title=title, url=url,
                date=date_str or today.strftime("%Y-%m-%d"),
                summary=summary, importance=3, status=ArticleStatus.PENDING,
            ))
            if len(out) >= self.per_source_limit:
                break
        return out


add_meta(id="arxiv", name="arXiv cs.AI",
         url="http://export.arxiv.org/api/query?search_query=cat:cs.AI",
         kind=SourceKind.API, tier=3,
         notes="Atom API; filtered by AI-impact keywords")
