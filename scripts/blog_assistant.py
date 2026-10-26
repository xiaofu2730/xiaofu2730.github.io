#!/usr/bin/env python3
"""Interactive Blog Creation & Publishing Assistant for xiaofu2730.github.io.

Provides an elegant macOS-inspired web dashboard and CLI to:
1. Initialize new markdown posts with custom attributes & front matter.
2. Import and format single or multiple existing markdown files.
3. Build and publish posts to HTML with one-click preview.
"""
from __future__ import annotations

import html
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CONTENT_DIR = ROOT / "content" / "posts"
IMAGES_DIR = ROOT / "images" / "blog"
CATEGORY_COVERS_DIR = IMAGES_DIR / "category_cover"

try:
    import yaml
    from scripts.generate_blog import (
        collect_site_data,
        default_output_path,
        load_posts,
        normalize_date,
        parse_front_matter,
        render_pages,
        slugify,
    )
except ImportError:
    # If dependencies are in .venv, try running via .venv python
    venv_py = ROOT / ".venv" / "bin" / "python3"
    if venv_py.exists() and sys.executable != str(venv_py):
        os.execv(str(venv_py), [str(venv_py)] + sys.argv)
    raise

from scripts.clean_math import clean_latex_string


def get_existing_metadata():
    categories = set()
    series_set = set()
    tags = set()
    posts_list = []

    for path in sorted(CONTENT_DIR.rglob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
            meta, body = parse_front_matter(content)
            cat = meta.get("category", "Notes")
            categories.add(cat)
            if meta.get("series"):
                series_set.add(meta["series"])
            for t in meta.get("tags", []):
                tags.add(t)

            output_p = ROOT / meta["output_path"] if meta.get("output_path") else default_output_path(meta)
            posts_list.append({
                "title": meta.get("title", path.stem),
                "slug": meta.get("slug", path.stem),
                "category": cat,
                "series": meta.get("series"),
                "date": str(meta.get("date", "")),
                "summary": meta.get("summary", ""),
                "tags": meta.get("tags", []),
                "cover_image": meta.get("cover_image", ""),
                "draft": bool(meta.get("draft", False)),
                "source_path": str(path.relative_to(ROOT)),
                "output_path": str(output_p.relative_to(ROOT)),
                "html_exists": output_p.exists(),
                "word_count": len(body),
            })
        except Exception:
            continue

    # Find cover images
    covers = []
    if CATEGORY_COVERS_DIR.exists():
        for f in CATEGORY_COVERS_DIR.glob("*"):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                covers.append(f"images/blog/category_cover/{f.name}")

    return {
        "categories": sorted(categories) or ["ML", "Math", "Notes"],
        "series": sorted(series_set) or ["Information Theory", "Reinforcement Learning"],
        "tags": sorted(tags),
        "covers": covers,
        "posts": posts_list,
    }


def create_post(data: dict) -> dict:
    title = data.get("title", "").strip()
    if not title:
        raise ValueError("文章标题不能为空")

    category = data.get("category", "Notes").strip() or "Notes"
    series = data.get("series", "").strip() or None
    slug = slugify(data.get("slug", "").strip() or title)
    date_str = data.get("date", "").strip() or datetime.now().strftime("%Y-%m-%d")
    summary = data.get("summary", "").strip() or f"{title} 的读书与研究笔记。"
    cover_image = data.get("cover_image", "").strip() or "images/blog/category_cover/ai.jpg"
    tags = data.get("tags", [category])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not tags:
        tags = [category]
    toc = bool(data.get("toc", True))
    draft = bool(data.get("draft", False))
    subtitle = data.get("subtitle", "").strip() or None

    cat_dir = CONTENT_DIR / slugify(category)
    cat_dir.mkdir(parents=True, exist_ok=True)
    post_file = cat_dir / f"{slug}.md"
    assets_dir = cat_dir / f"{slug}.assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    yaml_tags = "\n".join(f"  - {t}" for t in tags)
    subtitle_line = f"subtitle: {subtitle}\n" if subtitle else ""
    series_line = f"series: {series}\n" if series else ""
    draft_line = "draft: true\n" if draft else ""

    front_matter = f"""---
title: {title}
{subtitle_line}date: {date_str}
slug: {slug}
category: {category}
{series_line}summary: {summary}
cover_image: {cover_image}
tags:
{yaml_tags}
{draft_line}toc: {'true' if toc else 'false'}
---
"""
    initial_body = data.get("content", "").strip()
    if not initial_body:
        initial_body = f"""# {title}

在这里开始编写正文内容...

## 1. 简介

## 2. 核心推导与公式

行内公式示例：$E = mc^2$。

块级公式示例：
$$
\\mathcal{{L}}(\\theta) = \\mathbb{{E}}_{{x \\sim p(x)}} \\left[ \\log p_\\theta(x) \\right]
$$

## 3. 代码示例

```python
def main():
    print("Hello from {title}!")
```

## 4. 总结与引用
"""
    full_text = front_matter + "\n" + initial_body + "\n"
    post_file.write_text(full_text, encoding="utf-8")

    return {
        "success": True,
        "slug": slug,
        "source_path": str(post_file.relative_to(ROOT)),
        "assets_path": str(assets_dir.relative_to(ROOT)),
    }


def import_and_format_markdown(filename: str, raw_content: str, meta_override: dict = None) -> dict:
    meta_override = meta_override or {}

    # Extract or infer title
    extracted_title = ""
    # Check if existing front matter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw_content, re.DOTALL)
    existing_meta = {}
    body = raw_content

    if fm_match:
        try:
            existing_meta = yaml.safe_load(fm_match.group(1)) or {}
            body = fm_match.group(2)
        except Exception:
            pass

    # Extract title from first # heading or meta or filename
    if not extracted_title and existing_meta.get("title"):
        extracted_title = str(existing_meta["title"])
    if not extracted_title:
        h1_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if h1_match:
            extracted_title = h1_match.group(1).strip()
    if not extracted_title:
        extracted_title = Path(filename).stem.replace("_", " ").title()

    title = meta_override.get("title") or extracted_title
    category = meta_override.get("category") or existing_meta.get("category") or "Notes"
    series = meta_override.get("series") or existing_meta.get("series") or None
    slug = slugify(meta_override.get("slug") or existing_meta.get("slug") or title)
    date_str = meta_override.get("date") or existing_meta.get("date") or datetime.now().strftime("%Y-%m-%d")
    if hasattr(date_str, "strftime"):
        date_str = date_str.strftime("%Y-%m-%d")
    date_str = str(date_str)[:10]

    summary = meta_override.get("summary") or existing_meta.get("summary") or f"{title} 的读书与研究笔记。"
    cover_image = meta_override.get("cover_image") or existing_meta.get("cover_image") or "images/blog/category_cover/ai.jpg"
    tags = meta_override.get("tags") or existing_meta.get("tags") or [category]
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    # Clean body math formulas
    def repl_block_math(m: re.Match) -> str:
        return f"$$\n{clean_latex_string(m.group(1))}\n$$"

    body = re.sub(r"\$\$\s*\n?(.*?)\n?\s*\$\$", repl_block_math, body, flags=re.DOTALL)

    def repl_inline_math(m: re.Match) -> str:
        return f"${clean_latex_string(m.group(1))}$"

    body = re.sub(r"(?<!\\)\$(?!\$)([^\n$]+?)(?<!\\)\$", repl_inline_math, body)

    # Normalize image paths from *.assets to <slug>.assets/
    body = re.sub(r"!\[(.*?)\]\([^)]*?([^/)]+\.assets/([^)]+))\)", rf"![\1]({slug}.assets/\3)", body)

    # Save to content/posts/<category>/<slug>.md
    cat_dir = CONTENT_DIR / slugify(category)
    cat_dir.mkdir(parents=True, exist_ok=True)
    post_file = cat_dir / f"{slug}.md"
    assets_dir = cat_dir / f"{slug}.assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    yaml_tags = "\n".join(f"  - {t}" for t in tags)
    series_line = f"series: {series}\n" if series else ""
    subtitle = meta_override.get("subtitle") or existing_meta.get("subtitle")
    subtitle_line = f"subtitle: {subtitle}\n" if subtitle else ""

    front_matter = f"""---
title: {title}
{subtitle_line}date: {date_str}
slug: {slug}
category: {category}
{series_line}summary: {summary}
cover_image: {cover_image}
tags:
{yaml_tags}
toc: true
---
"""
    post_file.write_text(front_matter + "\n" + body.strip() + "\n", encoding="utf-8")

    return {
        "success": True,
        "title": title,
        "slug": slug,
        "source_path": str(post_file.relative_to(ROOT)),
        "assets_path": str(assets_dir.relative_to(ROOT)),
    }


HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>XiaoFu Blog Studio | 博客创作与发布助手</title>
  <link rel="shortcut icon" href="/images/profile_photo/logo.jpg" type="image/x-icon">
  <link href="https://fonts.googleapis.com/css?family=Poppins:300,400,500,600,700" rel="stylesheet">
  <style>
    :root {
      --bg: #f5f4ef;
      --card-bg: #ffffff;
      --accent: #ccb78f;
      --accent-hover: #b8a278;
      --accent-light: #f8f5ee;
      --text-main: #2b2b2b;
      --text-muted: #737373;
      --border: #e6e2d8;
      --shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
      --radius: 12px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: var(--bg);
      color: var(--text-main);
      line-height: 1.6;
      padding-bottom: 60px;
    }
    /* macOS App Header */
    .app-header {
      background: rgba(255, 255, 255, 0.88);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 0.8rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .brand img {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      border: 2px solid var(--accent);
    }
    .brand h1 {
      font-size: 1.15rem;
      font-weight: 700;
      color: #1a1a1a;
      letter-spacing: -0.01em;
    }
    .brand span {
      font-size: 0.8rem;
      color: var(--text-muted);
      font-weight: 400;
    }
    .nav-tabs {
      display: flex;
      background: #ece8df;
      padding: 4px;
      border-radius: 10px;
      gap: 4px;
    }
    .nav-btn {
      border: 0;
      background: transparent;
      padding: 0.45rem 1.1rem;
      font-size: 0.88rem;
      font-weight: 600;
      color: #5a554a;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .nav-btn:hover {
      color: #000;
    }
    .nav-btn.active {
      background: #ffffff;
      color: #000000;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    }
    .header-actions {
      display: flex;
      gap: 0.75rem;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.55rem 1.1rem;
      font-size: 0.88rem;
      font-weight: 600;
      border-radius: 8px;
      border: 1px solid transparent;
      cursor: pointer;
      transition: all 0.2s ease;
      text-decoration: none;
    }
    .btn-primary {
      background: var(--accent);
      color: #fff;
    }
    .btn-primary:hover {
      background: var(--accent-hover);
    }
    .btn-secondary {
      background: #fff;
      border-color: var(--border);
      color: var(--text-main);
    }
    .btn-secondary:hover {
      background: #faf8f5;
    }

    /* Container */
    .container {
      max-width: 1080px;
      margin: 2rem auto;
      padding: 0 1.5rem;
    }
    .tab-content {
      display: none;
    }
    .tab-content.active {
      display: block;
      animation: fadeIn 0.25s ease;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Card Panels */
    .panel {
      background: var(--card-bg);
      border-radius: var(--radius);
      border: 1px solid var(--border);
      box-shadow: var(--shadow);
      padding: 2rem;
      margin-bottom: 2rem;
    }
    .panel-header {
      margin-bottom: 1.5rem;
    }
    .panel-header h2 {
      font-size: 1.35rem;
      font-weight: 700;
      margin-bottom: 0.25rem;
    }
    .panel-header p {
      color: var(--text-muted);
      font-size: 0.9rem;
    }

    /* Form Grid */
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.25rem;
    }
    .form-group {
      margin-bottom: 1.25rem;
    }
    .form-group.full-width {
      grid-column: 1 / -1;
    }
    label {
      display: block;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 0.45rem;
      color: #4a4a4a;
    }
    input[type="text"], input[type="date"], select, textarea {
      width: 100%;
      padding: 0.65rem 0.85rem;
      border-radius: 8px;
      border: 1px solid var(--border);
      font-size: 0.95rem;
      background: #fafaf8;
      color: #111;
      transition: border-color 0.2s ease, background 0.2s ease;
    }
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: var(--accent);
      background: #fff;
      box-shadow: 0 0 0 3px rgba(204, 183, 143, 0.25);
    }
    textarea {
      resize: vertical;
      min-height: 85px;
      line-height: 1.5;
    }

    /* Cover Picker */
    .cover-picker {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
      gap: 0.75rem;
      margin-top: 0.5rem;
    }
    .cover-option {
      border: 2px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      cursor: pointer;
      position: relative;
      height: 75px;
      transition: all 0.2s ease;
    }
    .cover-option img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .cover-option.selected {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px var(--accent);
    }
    .cover-option-label {
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      background: rgba(0,0,0,0.65);
      color: #fff;
      font-size: 0.7rem;
      padding: 2px 4px;
      text-align: center;
    }

    /* Drop Zone */
    .drop-zone {
      border: 2px dashed var(--accent);
      border-radius: 12px;
      background: var(--accent-light);
      padding: 2.5rem 1.5rem;
      text-align: center;
      cursor: pointer;
      transition: all 0.2s ease;
      margin-bottom: 1.5rem;
    }
    .drop-zone:hover, .drop-zone.dragover {
      background: #f1ede3;
      border-color: #b8a278;
    }
    .drop-icon {
      font-size: 2.5rem;
      margin-bottom: 0.5rem;
    }

    /* Post Table */
    .posts-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 1rem;
    }
    .posts-table th, .posts-table td {
      padding: 0.85rem 1rem;
      text-align: left;
      border-bottom: 1px solid var(--border);
      font-size: 0.9rem;
    }
    .posts-table th {
      background: #f8f7f4;
      font-weight: 600;
      color: #666;
    }
    .posts-table tr:hover td {
      background: #fcfbf9;
    }
    .badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 600;
      background: #efece5;
      color: #6d5b3d;
    }
    .badge-success {
      background: #d4edda;
      color: #155724;
    }
    .badge-warning {
      background: #fff3cd;
      color: #856404;
    }
    .table-actions {
      display: flex;
      gap: 0.4rem;
    }
    .btn-sm {
      padding: 0.3rem 0.65rem;
      font-size: 0.8rem;
    }

    /* Notification Toast */
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1a1a1a;
      color: #fff;
      padding: 0.85rem 1.5rem;
      border-radius: 10px;
      box-shadow: 0 8px 30px rgba(0,0,0,0.2);
      font-size: 0.9rem;
      display: none;
      z-index: 999;
      animation: slideUp 0.3s ease;
    }
    @keyframes slideUp {
      from { transform: translateY(20px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
  </style>
</head>
<body>

  <header class="app-header">
    <div class="brand">
      <img src="/images/profile_photo/logo.jpg" alt="Logo">
      <div>
        <h1>XiaoFu Blog Studio</h1>
        <span>博客创作与原生发布工作流</span>
      </div>
    </div>
    <div class="nav-tabs">
      <button class="nav-btn active" onclick="switchTab('create')">📝 新建文章</button>
      <button class="nav-btn" onclick="switchTab('import')">📥 导入已有文档</button>
      <button class="nav-btn" onclick="switchTab('manage')">📚 文章管理与发布</button>
    </div>
    <div class="header-actions">
      <button class="btn btn-primary" onclick="buildAllPosts()">🚀 一键编译整站</button>
      <a href="/blog.html" target="_blank" class="btn btn-secondary">🌐 预览主页</a>
    </div>
  </header>

  <main class="container">

    <!-- Tab 1: 新建文章 -->
    <div id="tab-create" class="tab-content active">
      <div class="panel">
        <div class="panel-header">
          <h2>新建博客文章</h2>
          <p>配置文章 Front Matter 属性，自动生成规范化 Markdown 模板及专属配图目录（.assets）</p>
        </div>
        <form id="create-post-form" onsubmit="handleCreatePost(event)">
          <div class="form-grid">
            <div class="form-group full-width">
              <label for="create-title">文章标题 *</label>
              <input type="text" id="create-title" required placeholder="如：深度强化学习：PPO 算法核心原理解析" oninput="autoFillSlug(this.value)">
            </div>
            <div class="form-group">
              <label for="create-slug">URL 标识 (Slug) *</label>
              <input type="text" id="create-slug" required placeholder="如：ppo_algorithm_explained">
            </div>
            <div class="form-group">
              <label for="create-subtitle">副标题 (可选)</label>
              <input type="text" id="create-subtitle" placeholder="如：Policy Optimization in Deep RL">
            </div>
            <div class="form-group">
              <label for="create-category">分类 (Category) *</label>
              <input type="text" id="create-category" list="category-list" required placeholder="选择或输入分类，如 ML / Math">
              <datalist id="category-list"></datalist>
            </div>
            <div class="form-group">
              <label for="create-series">专栏/系列 (Series 可选)</label>
              <input type="text" id="create-series" list="series-list" placeholder="选择或输入系列，如 Reinforcement Learning">
              <datalist id="series-list"></datalist>
            </div>
            <div class="form-group">
              <label for="create-tags">标签 Tags (逗号分隔) *</label>
              <input type="text" id="create-tags" required placeholder="如：ML, RL, PPO">
            </div>
            <div class="form-group">
              <label for="create-date">发布日期 *</label>
              <input type="date" id="create-date" required>
            </div>
            <div class="form-group full-width">
              <label for="create-summary">一句话简介 (Summary 用于列表展示) *</label>
              <textarea id="create-summary" required placeholder="简述本文的核心要点，展示在博客首页和搜索预览中..."></textarea>
            </div>
            <div class="form-group full-width">
              <label>封面图片 (Cover Image)</label>
              <div id="cover-picker-create" class="cover-picker"></div>
              <input type="hidden" id="create-cover" value="images/blog/category_cover/ai.jpg">
            </div>
          </div>
          <div style="margin-top: 1.5rem; display: flex; justify-content: flex-end; gap: 0.75rem;">
            <button type="submit" class="btn btn-primary" style="padding: 0.7rem 1.75rem;">✨ 立即初始化文章并打开</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Tab 2: 导入已有文档 -->
    <div id="tab-import" class="tab-content">
      <div class="panel">
        <div class="panel-header">
          <h2>导入并格式化已有 Markdown 文档</h2>
          <p>支持将外部编辑好的 Markdown（Typora、Obsidian、Notion 导出等）自动规范化 Front Matter、数学公式与同名 assets 资源目录</p>
        </div>

        <div id="drop-zone" class="drop-zone" onclick="document.getElementById('file-input').click()">
          <div class="drop-icon">📄</div>
          <h3 style="font-size: 1.1rem; margin-bottom: 0.35rem;">点击或将一个或多个 Markdown 文件拖放到此处</h3>
          <p style="font-size: 0.85rem; color: var(--text-muted);">自动识别标题、公式符号、配图引用并格式化</p>
          <input type="file" id="file-input" multiple accept=".md,.markdown" style="display: none;" onchange="handleFilesSelected(this.files)">
        </div>

        <div id="import-preview-area" style="display: none;">
          <h3 style="margin-bottom: 1rem; font-size: 1.05rem;">待导入文档清单 (<span id="import-count">0</span>)</h3>
          <div id="import-items-list"></div>
          <div style="margin-top: 1.5rem; display: flex; justify-content: flex-end;">
            <button class="btn btn-primary" onclick="executeBatchImport()">📥 确认并一键导入全部文档</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 3: 文章管理与发布 -->
    <div id="tab-manage" class="tab-content">
      <div class="panel">
        <div class="panel-header" style="display: flex; justify-content: space-between; align-items: flex-end;">
          <div>
            <h2>已发布文章管理</h2>
            <p>查看博客全站文章状态，一键重新编译 HTML，或在默认编辑器与浏览器中快速打开</p>
          </div>
          <button class="btn btn-secondary" onclick="loadSiteMeta()">🔄 刷新列表</button>
        </div>
        <table class="posts-table">
          <thead>
            <tr>
              <th>标题</th>
              <th>分类 / 系列</th>
              <th>发布日期</th>
              <th>字数</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody id="posts-table-body">
            <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">正在加载文章数据...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

  </main>

  <div id="toast" class="toast"></div>

  <script>
    let siteMeta = {};
    let pendingImportFiles = [];

    document.addEventListener("DOMContentLoaded", function() {
      document.getElementById("create-date").valueAsDate = new Date();
      setupDropZone();
      loadSiteMeta();
    });

    function showToast(msg) {
      const t = document.getElementById("toast");
      t.textContent = msg;
      t.style.display = "block";
      setTimeout(() => { t.style.display = "none"; }, 3000);
    }

    function switchTab(tabId) {
      document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      event.target.classList.add("active");
      document.getElementById("tab-" + tabId).classList.add("active");
    }

    function autoFillSlug(title) {
      const slugInput = document.getElementById("create-slug");
      if (!slugInput.dataset.manual) {
        slugInput.value = title.trim().toLowerCase()
          .replace(/[^\w\s-]/g, '')
          .replace(/[-\s]+/g, '_');
      }
    }
    document.getElementById("create-slug").addEventListener("input", function() {
      this.dataset.manual = "true";
    });

    async function loadSiteMeta() {
      try {
        const res = await fetch("/api/meta");
        siteMeta = await res.json();
        
        // Populate Category Datalist
        const catDatalist = document.getElementById("category-list");
        catDatalist.innerHTML = siteMeta.categories.map(c => `<option value="${c}">`).join("");

        // Populate Series Datalist
        const seriesDatalist = document.getElementById("series-list");
        seriesDatalist.innerHTML = siteMeta.series.map(s => `<option value="${s}">`).join("");

        // Populate Cover Pickers
        renderCoverPicker("cover-picker-create", "create-cover");

        // Render Posts Table
        renderPostsTable();
      } catch (err) {
        console.error("Failed to load meta:", err);
      }
    }

    function renderCoverPicker(containerId, inputId) {
      const container = document.getElementById(containerId);
      const input = document.getElementById(inputId);
      container.innerHTML = siteMeta.covers.map((c, i) => {
        const isSel = c === input.value;
        const name = c.split("/").pop();
        return `
          <div class="cover-option ${isSel ? 'selected' : ''}" onclick="selectCover('${containerId}', '${inputId}', '${c}')">
            <img src="/${c}" alt="${name}">
            <div class="cover-option-label">${name}</div>
          </div>
        `;
      }).join("");
    }

    function selectCover(containerId, inputId, coverPath) {
      document.getElementById(inputId).value = coverPath;
      renderCoverPicker(containerId, inputId);
    }

    function renderPostsTable() {
      const tbody = document.getElementById("posts-table-body");
      if (!siteMeta.posts || siteMeta.posts.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center;">暂无文章</td></tr>`;
        return;
      }
      tbody.innerHTML = siteMeta.posts.map(p => `
        <tr>
          <td>
            <strong>${p.title}</strong>
            <div style="font-size: 0.78rem; color: var(--text-muted);">${p.slug}</div>
          </td>
          <td>
            <span class="badge">${p.category}</span>
            ${p.series ? `<div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 2px;">${p.series}</div>` : ''}
          </td>
          <td>${p.date}</td>
          <td>${p.word_count} 字</td>
          <td>
            ${p.html_exists ? '<span class="badge badge-success">已生成 HTML</span>' : '<span class="badge badge-warning">未生成</span>'}
          </td>
          <td>
            <div class="table-actions">
              <button class="btn btn-secondary btn-sm" onclick="openFile('${p.source_path}', 'editor')">✍️ 编辑</button>
              <button class="btn btn-secondary btn-sm" onclick="openFile('${p.output_path}', 'browser')">🌐 预览</button>
            </div>
          </td>
        </tr>
      `).join("");
    }

    async function handleCreatePost(e) {
      e.preventDefault();
      const payload = {
        title: document.getElementById("create-title").value,
        subtitle: document.getElementById("create-subtitle").value,
        slug: document.getElementById("create-slug").value,
        category: document.getElementById("create-category").value,
        series: document.getElementById("create-series").value,
        tags: document.getElementById("create-tags").value,
        date: document.getElementById("create-date").value,
        summary: document.getElementById("create-summary").value,
        cover_image: document.getElementById("create-cover").value,
      };

      try {
        const res = await fetch("/api/posts/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast(`已创建文章: ${data.source_path}`);
          await buildAllPosts();
          await openFile(data.source_path, "editor");
          document.getElementById("create-post-form").reset();
          document.getElementById("create-date").valueAsDate = new Date();
          loadSiteMeta();
        } else {
          alert("创建失败: " + data.error);
        }
      } catch (err) {
        alert("网络请求失败: " + err);
      }
    }

    function setupDropZone() {
      const dz = document.getElementById("drop-zone");
      ["dragenter", "dragover"].forEach(evt => {
        dz.addEventListener(evt, e => { e.preventDefault(); dz.classList.add("dragover"); });
      });
      ["dragleave", "drop"].forEach(evt => {
        dz.addEventListener(evt, e => { e.preventDefault(); dz.classList.remove("dragover"); });
      });
      dz.addEventListener("drop", e => {
        handleFilesSelected(e.dataTransfer.files);
      });
    }

    async function handleFilesSelected(files) {
      if (!files || files.length === 0) return;
      pendingImportFiles = [];

      for (const file of files) {
        if (!file.name.endsWith(".md") && !file.name.endsWith(".markdown")) continue;
        const text = await file.text();
        pendingImportFiles.push({
          name: file.name,
          content: text,
          category: siteMeta.categories[0] || "Notes",
          cover: siteMeta.covers[0] || "images/blog/category_cover/ai.jpg"
        });
      }

      document.getElementById("import-preview-area").style.display = "block";
      document.getElementById("import-count").textContent = pendingImportFiles.length;
      renderImportItems();
    }

    function renderImportItems() {
      const container = document.getElementById("import-items-list");
      container.innerHTML = pendingImportFiles.map((f, i) => `
        <div style="background: #fafaf8; border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: center;">
          <div>
            <strong>${f.name}</strong>
            <div style="font-size: 0.8rem; color: var(--text-muted);">字符数: ${f.content.length} | 包含公式: ${f.content.includes('$') ? '是' : '否'}</div>
          </div>
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <select onchange="pendingImportFiles[${i}].category = this.value" style="padding: 0.4rem; font-size: 0.85rem;">
              ${siteMeta.categories.map(c => `<option value="${c}" ${c === f.category ? 'selected' : ''}>${c}</option>`).join("")}
            </select>
            <button class="btn btn-secondary btn-sm" onclick="pendingImportFiles.splice(${i}, 1); renderImportItems();">移除</button>
          </div>
        </div>
      `).join("");
    }

    async function executeBatchImport() {
      if (pendingImportFiles.length === 0) return;
      let count = 0;
      for (const f of pendingImportFiles) {
        try {
          const res = await fetch("/api/posts/import", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              filename: f.name,
              content: f.content,
              category: f.category,
              cover_image: f.cover
            })
          });
          const ret = await res.json();
          if (ret.success) count++;
        } catch (e) {
          console.error(e);
        }
      }
      showToast(`成功导入并规范化 ${count} 篇文档！`);
      pendingImportFiles = [];
      document.getElementById("import-preview-area").style.display = "none";
      await buildAllPosts();
      loadSiteMeta();
      switchTab("manage");
    }

    async function buildAllPosts() {
      showToast("正在编译整站文章与索引...");
      try {
        const res = await fetch("/api/posts/build", { method: "POST" });
        const data = await res.json();
        if (data.success) {
          showToast(`编译成功！共发布 ${data.published_count} 篇文章。`);
          loadSiteMeta();
        } else {
          alert("编译失败: " + data.error);
        }
      } catch (err) {
        alert("网络异常: " + err);
      }
    }

    async function openFile(filePath, openType) {
      try {
        await fetch("/api/posts/open", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: filePath, type: openType })
        });
      } catch (err) {
        console.error(err);
      }
    }
  </script>
</body>
</html>
"""


class BlogAssistantHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html", "/studio"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode("utf-8"))
            return

        if parsed.path == "/api/meta":
            meta = get_existing_metadata()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(meta, ensure_ascii=False).encode("utf-8"))
            return

        # Fallback to static files in ROOT
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"

        try:
            data = json.loads(post_body.decode("utf-8")) if post_body else {}
        except Exception:
            data = {}

        if parsed.path == "/api/posts/create":
            try:
                res = create_post(data)
                self._send_json(200, res)
            except Exception as e:
                self._send_json(400, {"success": False, "error": str(e)})
            return

        if parsed.path == "/api/posts/import":
            try:
                filename = data.get("filename", "imported_post.md")
                raw_content = data.get("content", "")
                res = import_and_format_markdown(filename, raw_content, data)
                self._send_json(200, res)
            except Exception as e:
                self._send_json(400, {"success": False, "error": str(e)})
            return

        if parsed.path == "/api/posts/build":
            try:
                posts = load_posts()
                render_pages(posts)
                pub_count = len([p for p in posts if not p.draft])
                self._send_json(200, {"success": True, "published_count": pub_count})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        if parsed.path == "/api/posts/open":
            try:
                req_path = data.get("path", "")
                open_type = data.get("type", "browser")
                full_path = ROOT / req_path

                if full_path.exists():
                    if sys.platform == "darwin":
                        subprocess.run(["open", str(full_path)], check=False)
                    elif sys.platform == "win32":
                        os.startfile(str(full_path))
                    else:
                        subprocess.run(["xdg-open", str(full_path)], check=False)
                self._send_json(200, {"success": True})
            except Exception as e:
                self._send_json(400, {"success": False, "error": str(e)})
            return

        self._send_json(404, {"error": "Not found"})

    def _send_json(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def run_assistant(port: int = 5000, auto_open: bool = True):
    os.chdir(str(ROOT))
    handler = BlogAssistantHandler

    # Find free port if 5000 is occupied
    actual_port = port
    for p in range(port, port + 10):
        try:
            httpd = socketserver.TCPServer(("", p), handler)
            actual_port = p
            break
        except OSError:
            continue
    else:
        print(f"Error: Unable to bind to ports {port}-{port+9}")
        sys.exit(1)

    url = f"http://localhost:{actual_port}/studio"
    print("\n" + "=" * 60)
    print("  🎨 XiaoFu Blog Studio (博客创作发布助手) 已启动！")
    print(f"  🔗 访问地址: {url}")
    print("  🖥️ 平台支持: macOS / 本地浏览器")
    print("  按 Ctrl+C 可退出助手")
    print("=" * 60 + "\n")

    if auto_open:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n助手服务已退出。")


if __name__ == "__main__":
    port_arg = 5000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port_arg = int(sys.argv[1])
    run_assistant(port=port_arg, auto_open=True)
