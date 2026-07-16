#!/usr/bin/env python3
"""
AI News Analyzer — analyzes pending articles with LLM.
Stores structured analysis in pending_queue.json for publish_post.py to use.
Все операции логируются в центральную систему метрик.
"""
import json
import os
import sys
import subprocess
import re
import fcntl
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

sys.path.insert(0, os.path.dirname(__file__))
from metrics import (
    log_event, log_error,
    funnel_set, log_run_event, log_alert,
)
from _config import PENDING_QUEUE


SCRIPT_NAME = "analyze"

ANALYSIS_PROMPT_TEMPLATE = """Ты — AI-аналитик, работающий для Telegram-канала "Агенты Смита" (об AI-агентах и автономных системах).

Проанализируй статью и верни ТОЛЬКО валидный JSON (без markdown-обёрток, без пояснений):

{{"translated_title": "Заголовок статьи на русском языке (точный перевод)", "agent_impact": "Влияние на разработку AI-агентов (1-2 предложения)", "business_impact": "Влияние на бизнес и рынок AI (1-2 предложения)", "it_impact": "Влияние на IT-индустрию (1-2 предложения)", "summary": "Краткое содержание статьи (2-3 предложения)", "tags": ["tag1", "tag2", "tag3"]}}

Правила:
- Пиши на русском языке
- agent_impact: как статья влияет на создание, развитие или применение AI-агентов
- business_impact: как статья влияет на бизнес, рынок, конкуренцию, инвестиции
- it_impact: как статья влияет на IT-индустрию, разработку, инфраструктуру
- summary: о чём статья своими словами
- tags: 3 ключевых тега (английские, lowercase, релевантные)
- Будь конкретным, а не общительным

Статья:
Заголовок: {title}
URL: {url}
Описание: {description}
"""

def load_queue():
    with open(PENDING_QUEUE) as f:
        return json.load(f)

def save_queue(d):
    with open(PENDING_QUEUE, 'w') as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

def fetch_url(url, timeout=15):
    """Fetch article page for additional context."""
    try:
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
        })
        with urlopen(req, timeout=timeout) as r:
            html = r.read().decode('utf-8', errors='ignore')
        
        # Extract text content from HTML
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:3000]
    except:
        return None

def call_llm(prompt, timeout=60):
    """Call LLM via openclaw CLI."""
    import time as _t
    cmd = ['openclaw', 'infer', 'model', 'run', '--prompt', prompt, '--json']
    t0 = _t.monotonic()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        duration_ms = int((_t.monotonic() - t0) * 1000)
        if result.returncode == 0:
            try:
                parsed = json.loads(result.stdout)
                log_event(SCRIPT_NAME, "llm_call", {
                    "duration_ms": duration_ms,
                    "ok": True,
                    "out_chars": len(result.stdout),
                })
                return parsed
            except:
                match = re.search(r'\{.*\}', result.stdout, re.DOTALL)
                if match:
                    parsed = json.loads(match.group())
                    log_event(SCRIPT_NAME, "llm_call", {
                        "duration_ms": duration_ms,
                        "ok": True,
                        "out_chars": len(result.stdout),
                        "extracted_json": True,
                    })
                    return parsed
                log_event(SCRIPT_NAME, "llm_call", {
                    "duration_ms": duration_ms,
                    "ok": False,
                    "error": "no_json_in_output",
                    "stdout_tail": result.stdout[-100:],
                })
                return None
        # Non-zero return code
        err_short = (result.stderr or "")[:200]
        log_event(SCRIPT_NAME, "llm_call", {
            "duration_ms": duration_ms,
            "ok": False,
            "error": "rc_nonzero",
            "rc": result.returncode,
            "stderr_tail": err_short,
        })
        # Heuristic: detect "overloaded" patterns
        if 'overload' in err_short.lower() or 'busy' in err_short.lower() or '503' in err_short:
            log_alert("llm_overload", f"LLM overloaded: {err_short}",
                      severity="warn",
                      details={"stderr": err_short})
        return None
    except subprocess.TimeoutExpired:
        duration_ms = int((_t.monotonic() - t0) * 1000)
        print(f"LLM timeout after {duration_ms}ms", file=sys.stderr)
        log_event(SCRIPT_NAME, "llm_call", {
            "duration_ms": duration_ms,
            "ok": False,
            "error": "timeout",
            "timeout_s": timeout,
        })
        return None
    except Exception as e:
        duration_ms = int((_t.monotonic() - t0) * 1000)
        print(f"LLM error: {e}", file=sys.stderr)
        log_event(SCRIPT_NAME, "llm_call", {
            "duration_ms": duration_ms,
            "ok": False,
            "error": str(e)[:200],
        })
        return None

def parse_llm_response(raw_output):
    """Parse LLM response to extract analysis fields."""
    try:
        if isinstance(raw_output, dict) and 'outputs' in raw_output:
            text = raw_output['outputs'][0]['text'] if raw_output['outputs'] else ''
        elif isinstance(raw_output, dict):
            text = raw_output.get('text', str(raw_output))
        else:
            text = str(raw_output)
        
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return {
                'translated_title': data.get('translated_title', ''),
                'agent_impact': data.get('agent_impact', 'Анализ недоступен'),
                'business_impact': data.get('business_impact', 'Анализ недоступен'),
                'it_impact': data.get('it_impact', 'Анализ недоступен'),
                'summary': data.get('summary', ''),
                'tags': data.get('tags', [])
            }
    except:
        pass
    return None

def needs_analysis(post):
    """Check if post needs analysis."""
    return not post.get('analysis') or not post['analysis'].get('agent_impact')

def analyze_article(post):
    """Analyze a single article with LLM."""
    title = post.get('title', '')
    url = post.get('url', '')

    description = post.get('summary', '')
    if not description:
        page_text = fetch_url(url)
        if page_text:
            description = page_text[:500]

    prompt = ANALYSIS_PROMPT_TEMPLATE.format(
        title=title,
        url=url,
        description=description or 'Нет описания'
    )

    import time as _t
    t0 = _t.monotonic()
    raw = call_llm(prompt)
    duration_ms = int((_t.monotonic() - t0) * 1000)

    if raw:
        analysis = parse_llm_response(raw)
        if analysis:
            # Set funnel: analyzed stage (only first time)
            return analysis
    return None

def main():
    run_ts = datetime.now(timezone.utc).isoformat()
    run_id = f"analyze:{run_ts}"
    log_event(SCRIPT_NAME, "started", {"run_ts": run_ts, "run_id": run_id})
    log_run_event(run_id, "analyze", "started", {"run_ts": run_ts})
    
    lock_path = PENDING_QUEUE + '.lock'
    lock_fd = None
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Analyze already running, exiting.")
        log_event(SCRIPT_NAME, "skipped", {"reason": "already_running", "run_ts": run_ts})
        return
    
    try:
        queue = load_queue()
        pending = queue.get('pending', [])
        
        # Find articles needing analysis
        to_analyze = [p for p in pending if needs_analysis(p)]
        
        if not to_analyze:
            print(f"No articles need analysis. {len(pending)} pending.")
            log_event(SCRIPT_NAME, "completed", {
                "run_ts": run_ts,
                "analyzed": 0,
                "failed": 0,
                "pending_total": len(pending),
                "status": "nothing_to_analyze"
            })
            return
        
        print(f"Analyzing {len(to_analyze)} article(s)...")
        analyzed = 0
        failed = 0
        analyzed_details = []
        
        for post in to_analyze:
            print(f"  Analyzing: {post['title'][:60]}...", file=sys.stderr)
            analysis = analyze_article(post)

            if analysis:
                for p in pending:
                    if p['id'] == post['id']:
                        p['analysis'] = analysis
                        p['analyzed_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                        break
                analyzed += 1
                analyzed_details.append({
                    "article_id": post['id'],
                    "source": post.get('source', ''),
                    "title": post['title'][:80]
                })
                # funnel: enqueued (if not already) + analyzed
                funnel_set(post['id'], 'enqueued',
                           source=post.get('source', ''),
                           title=post['title'][:80])
                funnel_set(post['id'], 'analyzed',
                           model="openclaw-infer")
                log_run_event(run_id, "analyze", "article_analyzed",
                              {"article_id": post['id']})
                log_event(SCRIPT_NAME, "article_analyzed", {
                    "article_id": post['id'],
                    "source": post.get('source', ''),
                    "title": post['title'][:80],
                    "run_id": run_id,
                })
                print(f"  ✓ {post['id']}", file=sys.stderr)
            else:
                failed += 1
                log_error(SCRIPT_NAME, f"LLM analysis failed for {post['id']}", {
                    "article_id": post['id'],
                    "source": post.get('source', ''),
                    "title": post['title'][:80],
                    "run_id": run_id,
                })
                log_run_event(run_id, "analyze", "article_failed",
                              {"article_id": post['id']})
                print(f"  ✗ {post['id']} — failed", file=sys.stderr)

        queue['pending'] = pending
        save_queue(queue)

        log_event(SCRIPT_NAME, "completed", {
            "run_ts": run_ts,
            "run_id": run_id,
            "analyzed": analyzed,
            "failed": failed,
            "pending_total": len(pending),
            "analyzed_details": analyzed_details,
            "status": "success"
        })
        log_run_event(run_id, "analyze", "completed", {
            "analyzed": analyzed,
            "failed": failed,
            "pending_total": len(pending),
        })
        
        print(f"Analysis complete: {analyzed} analyzed, {failed} failed, {len(pending)} total pending.")
    
    except Exception as e:
        log_error(SCRIPT_NAME, str(e), {"run_ts": run_ts})
        print(f"FATAL ERROR: {e}")
        raise
    
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
