#!/usr/bin/env python3
"""Проверка орфографии и удаление нечитаемых символов"""

import sys
import re

def check_text(text):
    """Проверяет текст и возвращает исправленную версию"""
    # Удаление иероглифов и нечитаемых символов
    # Китайские и японские символы
    text = re.sub(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', '', text)
    # Корейские
    text = re.sub(r'[\uac00-\ud7af\u1100-\u11ff]', '', text)
    # Разные нечитаемые символы
    text = re.sub(r'[\ufffc-\uffff]', '', text)
    # control characters
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)
 return text

if __name__ == '__main__':
    if len(sys.argv) > 1:
        text = ' '.join(sys.argv[1:])
    else:
        text = sys.stdin.read()
    result = check_text(text)
    print(result)