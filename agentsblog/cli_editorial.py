"""Local editorial inspection and explicit delivery reconciliation."""
import json
from contextlib import closing

from agentsblog.db import connect, get_article, init_schema, mark_published
from agentsblog.editorial import eligibility, run_analysis
from agentsblog.publishing.delivery import delivery_key
from agentsblog.publishing.editorial_format import format_editorial


def dispatch(args, settings):
    if args.command == 'analyze':
        result = run_analysis(settings, args.limit, article_id=args.id, retry_rejected=args.retry_rejected)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result['failed'] else 0
    with closing(connect(settings.db_path)) as conn:
        init_schema(conn)
        if args.command == 'editorial-status':
            result = {
                'reviews': [dict(r) for r in conn.execute('SELECT state,COUNT(*) AS count FROM editorial_reviews GROUP BY state')],
                'delivery_attention': [dict(r) for r in conn.execute("SELECT article_id,state,started_at,error FROM deliveries WHERE state IN ('unknown','sending','failed') ORDER BY started_at DESC LIMIT 20")],
                'analysis_errors': [dict(r) for r in conn.execute("SELECT article_id,error,attempts,next_attempt_at FROM editorial_reviews WHERE state='failed' ORDER BY updated_at DESC LIMIT 10")],
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        article = get_article(conn, args.id)
        if article is None:
            print('Статья не найдена'); return 2
        if args.command == 'preview-post':
            print('Редакционная проверка:', eligibility(article, settings) or 'пройдена')
            print(format_editorial(article, html=False) or 'Черновик ещё не подготовлен.')
            return 0
        if args.message_id is not None and args.message_id <= 0:
            print('message-id должен быть положительным'); return 2
        key = delivery_key(article, settings)
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute("SELECT state FROM deliveries WHERE delivery_key=?", (key,)).fetchone()
        if not row or row['state'] not in ('unknown', 'sending'):
            conn.execute('ROLLBACK'); print('Нет неоднозначной отправки для этой статьи'); return 2
        if args.message_id:
            conn.execute("UPDATE deliveries SET state='sent',message_id=?,error='' WHERE delivery_key=?", (args.message_id, key))
            mark_published(conn, article.id, args.message_id)
        else:
            conn.execute("UPDATE deliveries SET state='failed',finished_at=NULL,error='operator confirmed not sent' WHERE delivery_key=?", (key,))
        conn.execute('COMMIT')
        print('Состояние отправки уточнено.')
    return 0
