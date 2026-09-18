#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每天搜索 GitHub 仓库，命中关键词的新项目写入 README.md。
只用标准库，无需安装 requests。

- type=repositories
- sort=updated (Recently updated)
- 关键词不区分大小写
- 与 README.md 中已有链接去重
- Markdown 表格：序号 | 创建时间 | 项目名 | Star | 项目介绍 | 链接
- 整表按项目创建时间从早到晚排序，序号每次重新编号
"""

import os
import re
import sys
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ============ 配置区（以后增删关键词只改这里） ============
KEYWORDS = [
    "warp masque",
    "zerotrust masque",
    "usque",
    "aether masque",
    "WarpScout",
]

OUTPUT_FILE = "README.md"
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

# 匹配表格行里的链接，用于去重
LINK_RE = re.compile(r"https://github\.com/[^\s\)\|]+")
# 解析已有表格数据行：| # | 创建时间 | 项目名 | Star | 介绍 | [点击查看](url) |
ROW_RE = re.compile(
    r"^\|\s*\d+\s*\|\s*(?P<created>[^|]*?)\s*\|\s*(?P<name>[^|]*?)\s*\|"
    r"\s*(?P<stars>[^|]*?)\s*\|\s*(?P<desc>[^|]*?)\s*\|\s*\[点击查看\]\((?P<url>[^)]+)\)\s*\|\s*$"
)


def load_existing_urls(path):
    """从 README.md 提取已记录的仓库链接（小写）。"""
    existing = set()
    if not os.path.exists(path):
        return existing
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            for m in LINK_RE.findall(line):
                existing.add(m.rstrip("/").lower())
    return existing


def read_existing_rows(path):
    """读取已有数据行，解析出字段。"""
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = ROW_RE.match(line)
            if not m:
                continue
            rows.append({
                "created": m.group("created").strip(),
                "name": m.group("name").strip(),
                "stars": m.group("stars").strip(),
                "desc": m.group("desc").strip(),
                "url": m.group("url").strip(),
            })
    return rows


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


def escape_md(text):
    if not text:
        return "(无描述)"
    text = text.replace("\n", " ").replace("\r", " ").replace("|", "/")
    return text.strip() or "(无描述)"


def write_readme(rows, now):
    """按创建时间从早到晚排序，重新编号，重写 README.md。"""
    # 排序：created 是 YYYY-MM-DD 字符串，可直接字典序比较；空值放最后
    rows_sorted = sorted(rows, key=lambda r: (r["created"] == "", r["created"]))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# GitHub 仓库监控记录\n\n")
        f.write("> 关键词: " + " / ".join(f"`{k}`" for k in KEYWORDS) + "  \n")
        f.write("> 排序: 按项目创建时间（从早到晚）  \n")
        f.write(f"> 最后更新: {now} UTC  \n")
        f.write(f"> 共 {len(rows_sorted)} 个项目\n\n")
        f.write("| # | 创建时间 | 项目名 | Star | 项目介绍 | 链接 |\n")
        f.write("| ---: | --- | --- | ---: | --- | --- |\n")
        for i, r in enumerate(rows_sorted, start=1):
            f.write(
                f"| {i} | {r['created']} | {r['name']} | {r['stars']} | "
                f"{r['desc']} | [点击查看]({r['url']}) |\n"
            )


def main():
    existing_urls = load_existing_urls(OUTPUT_FILE)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # 抓取所有关键词，按 full_name 去重
    found = {}
    for kw in KEYWORDS:
        for page in range(1, MAX_PAGES + 1):
            items = search(kw, page)
            if not items:
                break
            for it in items:
                found[it["full_name"]] = it
            time.sleep(2)

    # 读已有行
    rows = read_existing_rows(OUTPUT_FILE)

    # 把新发现的追加进 rows
    added = 0
    for full_name, it in found.items():
        url = it["html_url"].rstrip("/").lower()
        if url in existing_urls:
            continue
        existing_urls.add(url)
        rows.append({
            "created": (it.get("created_at") or "")[:10],   # YYYY-MM-DD
            "name": it["full_name"],
            "stars": str(it.get("stargazers_count", 0)),
            "desc": escape_md(it.get("description")),
            "url": it["html_url"],
        })
        added += 1

    write_readme(rows, now)

    if added:
        print(f"新增 {added} 个项目。")
    else:
        print("没有发现新项目。")


if __name__ == "__main__":
    main()
