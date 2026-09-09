import io
with io.open('memory/2026-09-08.md', 'r', encoding='utf-8') as f:
    cur = f.read()
with io.open('memory/_append_0928.md', 'r', encoding='utf-8') as f:
    add = f.read()
if '## 09:28 MSK' not in cur:
    with io.open('memory/2026-09-08.md', 'a', encoding='utf-8') as f:
        f.write(add)
    print('appended')
else:
    print('already present')
import os
os.remove('memory/_append_0928.md')
