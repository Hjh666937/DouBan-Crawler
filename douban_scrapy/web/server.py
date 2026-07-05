# -*- coding: utf-8 -*-
"""豆瓣电影爬虫 Web 控制台后端。"""

import csv
import json
import os
import re
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime

from flask import Flask, jsonify, render_template, request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database.db_manager import Database
from douban_crawler.cookie_loader import load_douban_cookie, save_douban_cookie
from douban_crawler.csv_store import load_existing_movies

app = Flask(__name__, static_folder="static", static_url_path="/static")

COOKIE_FILE = os.path.join(PROJECT_ROOT, "douban_crawler", "cookie.txt")
DB_CONFIG_FILE = os.path.join(PROJECT_ROOT, "database", "db_config.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
MOVIES_CSV = os.path.join(OUTPUT_DIR, "movies.csv")
REVIEWS_CSV = os.path.join(OUTPUT_DIR, "reviews.csv")
LOG_FILE = os.path.join(PROJECT_ROOT, "web", "crawl.log")

_crawl_process = None
_crawl_lock = threading.Lock()


def _read_csv_rows(path):
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _split_genres(text):
    if not text:
        return []
    parts = re.split(r"[/;|、]", text)
    return [p.strip() for p in parts if p.strip()]


def _reviews_by_movie():
    grouped = {}
    for row in _read_csv_rows(REVIEWS_CSV):
        mid = str(row.get("movie_id", "")).strip()
        if mid:
            grouped.setdefault(mid, []).append(row)
    return grouped


def _count_csv_rows(path):
    return len(_read_csv_rows(path))


def _read_tail(path, lines=80):
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.readlines()
    return "".join(content[-lines:])


def _stop_crawl_process():
    """停止爬虫子进程（Windows 下使用 taskkill 确保终止）。"""
    global _crawl_process
    if not _is_crawl_running():
        return False

    proc = _crawl_process
    pid = proc.pid
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        else:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

    _crawl_process = None
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 用户手动停止爬取\n")
    return True


def _save_cookie_text(cookie: str) -> None:
    save_douban_cookie(cookie)


def _is_crawl_running():
    global _crawl_process
    if _crawl_process is None:
        return False
    if _crawl_process.poll() is None:
        return True
    _crawl_process = None
    return False


def _movie_card(row, review_ids):
    mid = str(row.get("movie_id", "")).strip()
    rating = row.get("rating", "") or "0"
    try:
        rating_f = float(rating)
    except ValueError:
        rating_f = 0.0
    return {
        "movie_id": mid,
        "name": row.get("name", ""),
        "poster_url": row.get("poster", ""),
        "genre": _split_genres(row.get("genre", "")),
        "douban_rating": rating_f,
        "rating_count": int(float(row.get("rating_count", 0) or 0)),
        "short_comment_count": int(float(row.get("short_review_count", 0) or 0)),
        "country": row.get("country", ""),
        "release_date": row.get("release_date", ""),
        "has_comments": mid in review_ids,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def api_stats():
    movies = _read_csv_rows(MOVIES_CSV)
    review_map = _reviews_by_movie()
    cookie_ok = os.path.isfile(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 10
    genres = set()
    for m in movies:
        genres.update(_split_genres(m.get("genre", "")))

    return jsonify({
        "movies_in_csv": len(movies),
        "review_rows": sum(len(v) for v in review_map.values()),
        "comments_movies_done": len(review_map),
        "genres_count": len(genres),
        "crawl_running": _is_crawl_running(),
        "cookie_configured": cookie_ok,
    })


@app.route("/api/genres")
def api_genres():
    movies = _read_csv_rows(MOVIES_CSV)
    counts = {}
    for movie in movies:
        for g in _split_genres(movie.get("genre", "")):
            counts[g] = counts.get(g, 0) + 1
    return jsonify({
        "genres": [{"name": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]
    })


@app.route("/api/movies")
def api_movies():
    genre = request.args.get("genre", "").strip()
    search = request.args.get("search", "").strip().lower()
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 24)), 1), 100)

    movies = _read_csv_rows(MOVIES_CSV)
    review_map = _reviews_by_movie()
    review_ids = set(review_map.keys())

    filtered = []
    for row in movies:
        genres = _split_genres(row.get("genre", ""))
        if genre and genre not in genres:
            continue
        if search:
            haystack = " ".join([
                row.get("name", ""),
                row.get("director", ""),
                row.get("actors", ""),
                row.get("genre", ""),
            ]).lower()
            if search not in haystack:
                continue
        filtered.append(_movie_card(row, review_ids))

    total = len(filtered)
    start = (page - 1) * page_size
    return jsonify({
        "total": total,
        "page": page,
        "page_size": page_size,
        "movies": filtered[start:start + page_size],
    })


@app.route("/api/movies/<movie_id>")
def api_movie_detail(movie_id):
    movies = _read_csv_rows(MOVIES_CSV)
    row = next((m for m in movies if str(m.get("movie_id", "")).strip() == movie_id), None)
    if not row:
        return jsonify({"error": "电影不存在"}), 404

    reviews = _reviews_by_movie().get(movie_id, [])
    detail = dict(row)
    detail["poster_url"] = row.get("poster", "")
    detail["douban_rating"] = row.get("rating", "")
    detail["short_comment_count"] = row.get("short_review_count", "")
    detail["also_known_as"] = row.get("aka", "")
    detail["plot"] = row.get("summary", "")
    detail["genre"] = _split_genres(row.get("genre", ""))
    detail["comments"] = [{
        "nickname": r.get("reviewer", ""),
        "comment_time": r.get("review_time", ""),
        "content": r.get("content", ""),
        "helpful_votes": int(float(r.get("votes", 0) or 0)),
    } for r in reviews]
    return jsonify(detail)


@app.route("/api/logs")
def api_logs():
    return jsonify({"logs": _read_tail(LOG_FILE, 100)})


@app.route("/api/crawl", methods=["POST"])
def api_crawl():
    global _crawl_process
    if _is_crawl_running():
        return jsonify({
            "ok": False,
            "message": "爬虫正在运行中，请先点击「停止爬取」再更换 Cookie 后重新开始",
        }), 400

    data = request.get_json(silent=True) or {}
    try:
        target_count = int(data.get("target_count", 10))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "采集数量无效"}), 400

    if target_count < 1 or target_count > 50000:
        return jsonify({"ok": False, "message": "采集数量需在 1~50000 之间"}), 400

    existing_count = len(load_existing_movies(OUTPUT_DIR))
    need_count = max(target_count - existing_count, 0)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as log:
        log.write(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "
            f"开始爬取，目标总数 {target_count} 部（已有 {existing_count} 部，本次新增 {need_count} 部）\n"
        )

    cmd = [
        sys.executable, "-m", "scrapy", "crawl", "douban_movie",
        "-a", f"target_count={target_count}",
    ]
    with _crawl_lock:
        _crawl_process = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=open(LOG_FILE, "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
        )

    if existing_count >= target_count:
        msg = f"CSV 中已有 {existing_count} 部电影，已达到目标 {target_count} 部，无需继续爬取"
    else:
        msg = (
            f"已启动爬虫，目标总数 {target_count} 部"
            f"（已有 {existing_count} 部，本次新增 {need_count} 部）"
        )
    return jsonify({"ok": True, "message": msg})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    data = request.get_json(silent=True) or {}
    cookie = data.get("cookie")
    running = _is_crawl_running()

    if not running:
        if cookie is not None:
            _save_cookie_text(cookie.strip())
            return jsonify({"ok": True, "message": "Cookie 已保存（当前无运行中的爬虫）"})
        return jsonify({"ok": False, "message": "当前没有运行中的爬虫"}), 400

    _stop_crawl_process()
    parts = ["爬取已停止，已保存 CSV 中的数据"]
    if cookie is not None:
        _save_cookie_text(cookie.strip())
        parts.append("新 Cookie 已保存，可点击「开始爬取」继续")
    else:
        parts.append("可在下方更新 Cookie 后重新开始")
    return jsonify({"ok": True, "message": "。".join(parts)})


@app.route("/api/config/cookie", methods=["GET", "POST"])
def api_cookie():
    if request.method == "GET":
        return jsonify({"cookie": load_douban_cookie()})

    data = request.get_json(silent=True) or {}
    cookie = (data.get("cookie") or "").strip()
    _save_cookie_text(cookie)
    msg = "Cookie 已保存"
    if _is_crawl_running():
        msg += "（当前爬虫仍在运行，需停止后重新开始才会生效）"
    return jsonify({"ok": True, "message": msg})


@app.route("/api/config/db", methods=["GET", "POST"])
def api_db_config():
    default = {
        "server": "localhost",
        "port": 1433,
        "database": "DoubanMovies",
        "user": "sa",
        "password": "",
        "use_windows_auth": False,
    }
    if request.method == "GET":
        if os.path.isfile(DB_CONFIG_FILE):
            with open(DB_CONFIG_FILE, "r", encoding="utf-8") as f:
                return jsonify({**default, **json.load(f)})
        return jsonify(default)

    data = request.get_json(silent=True) or {}
    config = {**default, **data}
    config["port"] = int(config.get("port", 1433))
    os.makedirs(os.path.dirname(DB_CONFIG_FILE), exist_ok=True)
    with open(DB_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "message": "数据库配置已保存"})


@app.route("/api/db/init", methods=["POST"])
def api_db_init():
    db = Database(config_path=DB_CONFIG_FILE)
    if not db.connect():
        return jsonify({"ok": False, "message": "数据库连接失败，请检查配置"}), 500
    if not db.ensure_tables():
        return jsonify({"ok": False, "message": "建表失败"}), 500
    db.disconnect()
    return jsonify({"ok": True, "message": "数据库与数据表创建成功"})


@app.route("/api/db/import", methods=["POST"])
def api_db_import():
    if not os.path.isfile(MOVIES_CSV):
        return jsonify({"ok": False, "message": "未找到 movies.csv，请先运行爬虫"}), 400

    db = Database(config_path=DB_CONFIG_FILE)
    if not db.connect():
        return jsonify({"ok": False, "message": "数据库连接失败"}), 500
    if not db.ensure_tables():
        db.disconnect()
        return jsonify({"ok": False, "message": "建表失败"}), 500

    movie_result = db.import_movies_csv(MOVIES_CSV)
    review_result = {"total": 0, "success": 0, "failed": 0}
    if os.path.isfile(REVIEWS_CSV):
        review_result = db.import_reviews_csv(REVIEWS_CSV)
    db.disconnect()

    return jsonify({
        "ok": True,
        "message": "导入完成",
        "movies": movie_result,
        "reviews": review_result,
    })


WEB_PORT = 5001
WEB_URL = f"http://127.0.0.1:{WEB_PORT}"


def main():
    print()
    print("=" * 56)
    print("       豆瓣电影爬虫 Web 控制台 已启动")
    print("=" * 56)
    print()
    print("  请在浏览器中打开以下地址：")
    print()
    print(f"       >>>  {WEB_URL}  <<<")
    print()
    print("  按 Ctrl+C 可停止服务")
    print()
    print("=" * 56)
    print()

    threading.Timer(1.0, lambda: webbrowser.open(WEB_URL)).start()
    app.run(host="127.0.0.1", port=WEB_PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
