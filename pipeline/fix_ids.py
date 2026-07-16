#!/usr/bin/env python3
"""Fix article ID truncation - replace with make_article_id() calls."""
import re
from pathlib import Path

SCAN_PATH = Path(__file__).parent / 'scan_sources.py'

with open(SCAN_PATH) as f:
    lines = f.readlines()

new_lines = []
i = 0
count = 0
while i < len(lines):
    line = lines[i]
    # Look for the truncation pattern start
    if 'article_id = article_url.rstrip' in line and i + 3 < len(lines):
        next1 = lines[i+1].strip()
        next2 = lines[i+2].strip()
        next3 = lines[i+3].strip()
        if (next1 == 'if len(article_id) > 60:' and 
            next2.startswith('article_id = article_id[:60]') and 
            next3.startswith('article_id = f"')):
            # Extract prefix from the f-string line
            prefix_match = re.search(r'article_id = f"(\w+)-', next3)
            if prefix_match:
                prefix = prefix_match.group(1)
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f'{indent}article_id = make_article_id("{prefix}", article_url)\n')
                i += 4  # Skip all 4 lines
                count += 1
                print(f'  Fixed block #{count}: prefix={prefix}')
                continue
    new_lines.append(line)
    i += 1

print(f'Fixed {count} truncation blocks')
with open(SCAN_PATH, 'w') as f:
    f.writelines(new_lines)
