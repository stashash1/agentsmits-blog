
import traceback
from agentsblog.editorial import read_source, draft_issues, Draft
import socket
# 1) DNS check
for host in ['techcrunch.com', 'github.com']:
    try:
        a = socket.getaddrinfo(host, 443)
        print(host, '->', a[0][4][0])
    except Exception as e:
        print(host, 'DNS FAIL:', e)
# 2) fetch
try:
    txt = read_source('https://techcrunch.com/2026/09/18/tilly-norwoods-press-tour-is-going-a/')
    print('FETCH OK len:', len(txt))
except Exception as e:
    print('FETCH FAIL:', type(e).__name__, e)
