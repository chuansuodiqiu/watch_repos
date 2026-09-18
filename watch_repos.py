#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每天搜索 GitHub 仓库，命中关键词的新项目追加到 README.md。
只用标准库，无需安装 requests。
- type=repositories
- sort=updated (Recently updated)
- 关键词不区分大小写
- 与 README.md 中已有链接去重
- Markdown 表格排版，含 star 数，链接显示为「点击查看」
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


def load_existing(path):
    """从 README.md 中提取已记录的仓库链接（小写）。"""
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


def escape_md(text):
    """转义 Markdown 表格里的特殊字符。"""
    if not text:
        return "(无描述)"
    text = text.replace("\n", " ").replace("\r", " ").replace("|", "/")
    return text.strip() or "(无描述)"


def read_existing_rows(path):
    """读取已有表格的数据行（保留原顺序）。"""
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            # 只保留表格数据行（以 | 开头，且不是表头/分隔行）
            if line.startswith("|") and "---" not in line and "记录时间" not in line:
                rows.append(line)
    return rows


def write_readme(rows, now):
    """重写 README.md。"""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# GitHub 仓库监控记录\n\n")
        f.write("> 关键词: " + " / ".join(f"`{k}`" for k in KEYWORDS) + "  \n")
        f.write("> 排序: Recently updated  \n")
        f.write(f"> 最后更新: {now} UTC\n\n")
        f.write("| 记录时间 | 项目名 | Star | 项目介绍 | 链接 |\n")
        f.write("| --- | --- | ---: | --- | --- |\n")
        for row in rows:
            f.write(row + "\n")


def main():
    existing = load_existing(OUTPUT_FILE)
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

    # 过滤掉已记录的
    new_items = []
    for full_name, it in found.items():
        url = it["html_url"].rstrip("/").lower()
        if url in existing:
            continue
        new_items.append(it)
        existing.add(url)

    # 已存在的行（保持原顺序）
    old_rows = read_existing_rows(OUTPUT_FILE)

    # 新行按更新时间倒序，追加在老行后面
    new_rows = []
    for it in sorted(new_items, key=lambda x: x.get("updated_at", ""), reverse=True):
        name = it["full_name"]
        stars = it.get("stargazers_count", 0)
        desc = escape_md(it.get("description"))
        url = it["html_url"]
        new_rows.append(f"| {now} | {name} | {stars} | {desc} | [点击查看]({url}) |")

    all_rows = old_rows + new_rows
    write_readme(all_rows, now)

    if new_rows:
        print(f"新增 {len(new_rows)} 个项目。")
    else:
        print("没有发现新项目。")


if __name__ == "__main__":
    main()
