#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每天搜索 GitHub 仓库，命中关键词的新项目追加到 new.txt。
- type=repositories
- sort=updated (Recently updated)
- 关键词不区分大小写
- 与 new.txt 中已有链接去重
"""

import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

# ============ 配置区（以后增删关键词只改这里） ============
KEYWORDS = [
    "masque",
    "zerotrust",
    "usque",
    "aether masque",
    "WarpScout",
]

OUTPUT_FILE = "new.txt"
PER_PAGE = 30          # 每个关键词抓取数量
MAX_PAGES = 2          # 每个关键词最多翻几页
SORT = "updated"       # Recently updated
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
    """读取已记录的项目链接集合。"""
    existing = set()
    if not os.path.exists(path):
        return existing
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            for m in LINK_RE.findall(line):
                existing.add(m.rstrip("/").lower())
    return existing


def search(keyword, page):
    params = {
        "q": keyword,          # 关键词（GitHub 搜索不区分大小写）
        "sort": SORT,
        "order": ORDER,
        "per_page": PER_PAGE,
        "page": page,
    }
    r = requests.get(API, headers=HEADERS, params=params, timeout=30)
    if r.status_code == 403:
        print(f"[WARN] rate limited on '{keyword}' page {page}", file=sys.stderr)
        return []
    r.raise_for_status()
    return r.json().get("items", [])


def main():
    existing = load_existing(OUTPUT_FILE)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # 合并所有关键词的结果，按 full_name 去重
    found = {}   # full_name -> repo dict
    for kw in KEYWORDS:
        for page in range(1, MAX_PAGES + 1):
            try:
                items = search(kw, page)
            except Exception as e:
                print(f"[ERROR] search '{kw}' page {page}: {e}", file=sys.stderr)
                break
            if not items:
                break
            for it in items:
                found[it["full_name"]] = it
            time.sleep(2)  # 避免触发搜索 API 速率限制（未认证 10 req/min）

    # 过滤已存在的
    new_items = []
    for full_name, it in found.items():
        url = it["html_url"].rstrip("/").lower()
        if url in existing:
            continue
        new_items.append(it)
        existing.add(url)

    # 按更新时间排序，保证输出稳定
    new_items.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    if not new_items:
        print("没有发现新项目。")
        # 若文件不存在，仍然创建带表头的文件
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