#!/usr/bin/env python3
"""Fix CSS escaping: replace single { with {{ and } with }}."""
from pathlib import Path

target = Path("/home/stas/dev/project/agentsmits-blog/generate_site.py")
src = target.read_text()

# Найдём вставленный CSS-блок и экранируем { } для .format()
import re
# Pattern: от /* ── Breakthrough badge ── */ до /* ── Posts ── */
pattern = r"(/\* ── Breakthrough badge ── \*/.*?/\* ── Posts ── \*/)"
m = re.search(pattern, src, flags=re.DOTALL)
if not m:
    print("Pattern not found")
    raise SystemExit(1)

css_block = m.group(1)
escaped = css_block.replace("{", "{{").replace("}", "}}")
src = src.replace(css_block, escaped, 1)

target.write_text(src)
print(f"OK: CSS escaped ({len(src)} bytes)")
