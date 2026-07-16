#!/usr/bin/env python3
"""
Валидатор синхронизации Telegram-блог.
Сверяет published-посты в Telegram pending_queue с blog pending_queue.
"""
from _config import PENDING_QUEUE, SYNC_STATUS

import json
import sys
from pathlib import Path



def load_json(path):
    with open(path) as f:
        return json.load(f)


def main():
    tg_q = load_json(PENDING_QUEUE)
    bl_q = load_json(PENDING_QUEUE)

    tg_pub = {p["id"] for p in tg_q.get("published", [])}
    bl_pub = {p["id"] for p in bl_q.get("published", [])}

    only_tg   = tg_pub - bl_pub
    only_blog = bl_pub - tg_pub
    common    = tg_pub & bl_pub

    status = "OK" if not only_tg and not only_blog else "MISMATCH"

    result = {
        "status": status,
        "telegram_published": len(tg_pub),
        "blog_published": len(bl_pub),
        "in_common": len(common),
        "only_telegram": sorted(only_tg),
        "only_blog": sorted(only_blog),
    }

    # Save status
    with open(SYNC_STATUS, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Print report
    print(f"🔍 Валидация синхронизации Telegram ↔ Blog")
    print(f"   Telegram: {len(tg_pub)} опубликовано")
    print(f"   Blog:     {len(bl_pub)} опубликовано")
    print(f"   Общее:    {len(common)}")
    print()

    if not only_tg and not only_blog:
        print(f"✅ Синхронизированы. Расхождений нет.")
        return 0

    print(f"⚠️  Расхождения обнаружены ({status}):")

    if only_tg:
        print(f"\n📱 Только в Telegram ({len(only_tg)}):")
        for pid in sorted(only_tg):
            pub = next((p for p in tg_q["published"] if p["id"] == pid), {})
            title = pub.get("title", "")[:60]
            print(f"   - {pid[:40]}... | {title}")

    if only_blog:
        print(f"\n🌐 Только на Blog ({len(only_blog)}):")
        for pid in sorted(only_blog):
            pub = next((p for p in bl_q["published"] if p["id"] == pid), {})
            title = pub.get("title", "")[:60]
            print(f"   - {pid[:40]}... | {title}")

    return 1 if status == "MISMATCH" else 0


if __name__ == "__main__":
    sys.exit(main())
