#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每天搜索 GitHub 仓库，命中关键词的新项目追加到 new.txt。
只用标准库，无需安装 requests。
"""

import os
import re
import sys
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ============ 配置区（以后增删关键词只改这里） ============
KEYWORDS = [
    "masque",
    "zerotrust",
    "usque",
    "aether masque",
    "WarpScout",
]

OUTPUT_FILE = "new.txt"
PER_PAGE = 30
MAX_PAGES = 2
SORT = "updated"
ORDER = "desc"
# ==========================================================

API = "https://api.github.com/search/repositories"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "repo-watcher",
}
token = os.environ.get("GITHUB_TOKEN")
if token:
    HEADERS["Authorization"] = f"Bearer {token}"

LINK_RE = re.compile(r"https://github\.com/[^\s|]+")


def load_existing(path):
    existing = set()
    if not os.path.exists(path):
        return existing
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            for m in LINK_RE.findall(line):
                existing.add(m.rstrip("/").lower())
    return existing


def search(keyword, page):
    params = urllib.parse.urlencode({
        "q": keyword,
        "sort": SORT,
        "order": ORDER,
        "per_page": PER_PAGE,
        "page": page,
    })
    url = f"{API}?{params}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("items", [])
    except urllib.error.HTTPError as e:
        print(f"[WARN] HTTP {e.code} on '{keyword}' page {page}: {e.reason}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[ERROR] search '{keyword}' page {page}: {e}", file=sys.stderr)
        return []


def main():
    existing = load_existing(OUTPUT_FILE)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    found = {}
    for kw in KEYWORDS:
        for page in range(1, MAX_PAGES + 1):
            items = search(kw, page)
            if not items:
                break
            for it in items:
                found[it["full_name"]] = it
            time.sleep(2)

    new_items = []
    for full_name, it in found.items():
        url = it["html_url"].rstrip("/").lower()
        if url in existing:
            continue
        new_items.append(it)
        existing.add(url)

    new_items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    if not new_items:
        print("没有发现新项目。")
        if not os.path.exists(OUTPUT_FILE):
            write_header()
        return

    write_new(new_items, now)
    print(f"新增 {len(new_items)} 个项目。")


def write_header():
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# GitHub 仓库监控记录\n")
        f.write("# 关键词: " + " / ".join(KEYWORDS) + "\n")
        f.write("# 排序: Recently updated\n")
        f.write("# 格式: [记录时间] | 项目名 | 项目介绍 | 项目链接\n\n")


def write_new(items, now):
    if not os.path.exists(OUTPUT_FILE):
        write_header()
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        for it in items:
            name = it["full_name"]
            desc = (it.get("description") or "").replace("\n", " ").replace("|", "/").strip()
            if not desc:
                desc = "(无描述)"
            url = it["html_url"]
            f.write(f"[{now}] | {name} | {desc} | {url}\n")


if __name__ == "__main__":
    main()
