#!/usr/bin/env python3
"""
Dry-run wrapper для publish_post.py — показывает что БУДЕТ опубликовано
без реальной отправки в Telegram.

QW-3 (2026-08-25): для отладки release-grouping.
"""
import sys
import os

# Run from pipeline/ dir for correct imports
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PIPELINE_DIR)

# Import publish_post but patch send_telegram to a no-op
import publish_post as pp

real_send = pp.send_telegram

_counter = [999000]

def fake_send(text, retries=3, delay=8):
    _counter[0] += 1
    fake_id = _counter[0]
    print(f"\n{'='*80}\n[FAKE TELEGRAM #{fake_id}] Would send (text len={len(text)}):")
    print("-" * 80)
    print(text)
    print("=" * 80 + "\n")
    return fake_id

pp.send_telegram = fake_send

if __name__ == "__main__":
    print("Running publish_post.main() in dry-run mode (no real Telegram)...\n")
    # Save original save_queue and patch to no-op (dry-run: don't touch pending_queue.json)
    real_save = pp.save_queue
    pp.save_queue = lambda d: print(f"[DRY-RUN] (skip save_queue: would persist {len(d.get('pending', []))} pending, {len(d.get('published', []))} published)")
    try:
        pp.main()
    finally:
        pp.save_queue = real_save
