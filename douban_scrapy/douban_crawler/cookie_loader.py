# -*- coding: utf-8 -*-
"""从 cookie.txt 读取豆瓣 Cookie。"""

import os

_COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookie.txt")


def load_douban_cookie() -> str:
    if not os.path.isfile(_COOKIE_FILE):
        return ""
    with open(_COOKIE_FILE, "r", encoding="utf-8") as f:
        lines = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]
    return "".join(lines).strip()


def save_douban_cookie(cookie: str) -> None:
    os.makedirs(os.path.dirname(_COOKIE_FILE), exist_ok=True)
    with open(_COOKIE_FILE, "w", encoding="utf-8") as f:
        f.write(cookie.strip() + "\n")
