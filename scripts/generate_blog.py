#!/usr/bin/env python3
"""Static Site Generator for xiaofu2730.github.io.

Converts Markdown posts with front matter and LaTeX formulas into native HTML pages.
"""
from __future__ import annotations

import argparse
import html
import http.server
import os
import re
import shutil
import socketserver
import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode

# Auto-reexec with local .venv if dependencies are missing in current python
ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python3"

try:
    import jinja2
    import markdown
    import yaml
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError:
    if VENV_PYTHON.exists() and sys.executable != str(VENV_PYTHON):
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)
    else:
        raise

CONTENT_DIR = ROOT / "content" / "posts"
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_ROOT = ROOT

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)
CALLOUT_START_RE = re.compile(r"^>\s*\[!(NOTE|TIP|WARNING|IMPORTANT|CAUTION)\](?:\s+(.*))?$", re.IGNORECASE)


@dataclass
class Post:
    source_path: Path
    output_path: Path
    title: str
    date: datetime
    slug: str
    category: str
    series: str | None
    subtitle: str | None
    summary: str
    cover_image: str
    tags: list[str]
    draft: bool
    toc: bool
    metadata: dict
    body_markdown: str
    content_html: str
    headings: list[dict]
    word_count: int
    reading_time_min: int

    @property
    def permalink(self) -> str:
        return self.output_path.relative_to(ROOT).as_posix()

    @property
    def category_slug(self) -> str:
        return slugify(self.metadata.get("category_slug") or self.category)

    @property
    def series_slug(self) -> str | None:
        if not self.series:
            return None
        return slugify(self.metadata.get("series_slug") or self.series)

    @property
    def display_date(self) -> str:
        return self.date.strftime("%b %d, %Y")

    @property
    def archive_label(self) -> str:
        return self.date.strftime("%B %Y")

    @property
    def archive_slug(self) -> str:
        return self.date.strftime("%Y-%m")

    @property
    def breadcrumb_items(self) -> list[dict]:
        items = [{"label": "Blog", "href": f"{self.root_prefix}blog.html"}]
        items.append({"label": self.category, "href": None})
        if self.series:
            items.append({"label": self.series, "href": None})
        return items

    @property
    def root_prefix(self) -> str:
        return relative_root(self.output_path)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[-\s]+", "-", value)
    return value.replace("-", "_")


def relative_root(path: Path) -> str:
    depth = len(path.relative_to(ROOT).parents) - 1
    return "" if depth <= 0 else "../" * depth


def calculate_stats(text: str) -> tuple[int, int]:
    # Chinese characters count
    zh_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    # English words count
    en_words = len(re.findall(r"\b[a-zA-Z0-9_-]+\b", text))
    total_count = zh_chars + en_words
    reading_time = max(1, round(total_count / 300))
    return total_count, reading_time


def parse_front_matter(raw_text: str) -> tuple[dict, str]:
    match = FRONT_MATTER_RE.match(raw_text)
    if not match:
        raise ValueError("Post is missing YAML front matter")
    data = yaml.safe_load(match.group(1)) or {}
    body = match.group(2)
    return data, body


def normalize_date(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if hasattr(value, "isoformat"):
        return datetime.fromisoformat(value.isoformat())
    if not isinstance(value, str):
        raise ValueError("Invalid date value")
    return datetime.fromisoformat(value)


def default_output_path(meta: dict) -> Path:
    category_part = slugify(meta["category"])
    series = meta.get("series")
    slug = meta["slug"]
    if series:
        return ROOT / "blog" / category_part / slugify(series) / f"{slug}.html"
    return ROOT / "blog" / category_part / f"{slug}.html"


def protect_math_and_callouts(markdown_text: str) -> tuple[str, dict[str, str]]:
    """Protect LaTeX math formulas and convert GitHub callouts so markdown doesn't corrupt math symbols."""
    placeholders: dict[str, str] = {}
    counter = 0

    def stash_block(raw: str) -> str:
        nonlocal counter
        token = f"\n\n@@@BLOCK_MATH_{counter}@@@\n\n"
        placeholders[token.strip()] = raw
        counter += 1
        return token

    def stash_inline(raw: str) -> str:
        nonlocal counter
        token = f"@@@INLINE_MATH_{counter}@@@"
        placeholders[token] = raw
        counter += 1
        return token

    # 1. Stash code blocks first so math inside code is untouched
    code_blocks: dict[str, str] = {}
    code_counter = 0

    def stash_code(m: re.Match) -> str:
        nonlocal code_counter
        token = f"@@@CODE_BLOCK_{code_counter}@@@"
        code_blocks[token] = m.group(0)
        code_counter += 1
        return token

    text = re.sub(r"```[^\n]*\n.*?```", stash_code, markdown_text, flags=re.DOTALL)
    text = re.sub(r"`[^`\n]+`", stash_code, text)

    # 2. Stash display math: $$ ... $$ or \[ ... \]
    def repl_display_math(m: re.Match) -> str:
        inner = html.escape(m.group(1).strip(), quote=False)
        return stash_block(f'<div class="katex-display-block">$$\n{inner}\n$$</div>')

    text = re.sub(r"\$\$\s*\n?(.*?)\n?\s*\$\$", repl_display_math, text, flags=re.DOTALL)
    text = re.sub(r"\\\[\s*\n?(.*?)\n?\s*\\\]", repl_display_math, text, flags=re.DOTALL)

    # 3. Stash inline math: $...$ (avoid escaped \$ or empty $$)
    def repl_inline_math(m: re.Match) -> str:
        inner = html.escape(m.group(1).strip(), quote=False)
        return stash_inline(f'<span class="katex-inline">${inner}$</span>')

    text = re.sub(r"(?<!\\)\$(?!\$)([^\n$]+?)(?<!\\)\$", repl_inline_math, text)

    # 4. Convert GitHub callouts: > [!NOTE] etc.
    lines = text.splitlines()
    new_lines: list[str] = []
    i = 0
    callout_icons = {
        "note": "ℹ️",
        "tip": "💡",
        "warning": "⚠️",
        "important": "❗",
        "caution": "🛑",
    }
    while i < len(lines):
        line = lines[i]
        m = CALLOUT_START_RE.match(line.strip())
        if m:
            kind = m.group(1).lower()
            title = m.group(2).strip() if m.group(2) else kind.title()
            icon = callout_icons.get(kind, "📌")
            body_lines: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip().startswith(">"):
                body_lines.append(lines[i].strip()[1:].lstrip())
                i += 1
            inner_md = "\n".join(body_lines)
            callout_html = (
                f'<div class="md-callout md-callout-{kind}">'
                f'<div class="md-callout-title"><span class="md-callout-icon">{icon}</span> {html.escape(title)}</div>'
                f"{inner_md}"
                f"</div>"
            )
            new_lines.append(stash_block(callout_html))
            continue
        new_lines.append(line)
        i += 1

    text = "\n".join(new_lines)

    # 5. Restore code blocks
    for token, raw_code in code_blocks.items():
        text = text.replace(token, raw_code)

    return text, placeholders


def render_markdown(markdown_text: str, root_prefix: str) -> tuple[str, list[dict]]:
    """Render markdown to HTML with KaTeX math protection, TOC generation, and table wrappers."""
    # Handle {{ root }} helper
    text = markdown_text.replace("{{ root }}", root_prefix)

    # Protect math
    protected_text, placeholders = protect_math_and_callouts(text)

    # Configure Python-Markdown extensions
    md = markdown.Markdown(
        extensions=[
            "extra",
            "tables",
            "fenced_code",
            "sane_lists",
            "toc",
        ],
        extension_configs={
            "toc": {
                "permalink": False,
                "toc_depth": "1-4",
            }
        },
    )

    content_html = md.convert(protected_text)

    # Extract headings from toc_tokens
    headings: list[dict] = []
    if hasattr(md, "toc_tokens"):
        def extract_tokens(tokens: list[dict]):
            for t in tokens:
                text_name = t["name"]
                for tok, val in placeholders.items():
                    if tok in text_name:
                        clean_val = re.sub(r"<[^>]+>", "", val).strip()
                        text_name = text_name.replace(tok, clean_val)
                headings.append({
                    "level": t["level"],
                    "id": t["id"],
                    "text": text_name,
                })
                if t.get("children"):
                    extract_tokens(t["children"])

        extract_tokens(md.toc_tokens)

    # Wrap tables in responsive container
    content_html = re.sub(
        r"(<table>.*?</table>)",
        r'<div class="table-wrapper">\1</div>',
        content_html,
        flags=re.DOTALL,
    )

    # Restore math and callouts
    for token, raw in placeholders.items():
        content_html = content_html.replace(f"<p>{token}</p>", raw)
        content_html = content_html.replace(token, raw)

    return content_html, headings


def sync_post_assets(source_path: Path, output_path: Path) -> None:
    """Copy any sibling *.assets directories from content to generated output dir."""
    source_dir = source_path.parent
    target_dir = output_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    for item in source_dir.iterdir():
        if item.is_dir() and (item.name.endswith(".assets") or item.name == "assets"):
            dest = target_dir / item.name
            if not dest.exists() or any(
                f.stat().st_mtime > dest.stat().st_mtime for f in item.rglob("*") if f.is_file()
            ):
                shutil.copytree(item, dest, dirs_exist_ok=True)


def load_posts() -> list[Post]:
    posts: list[Post] = []
    for source_path in sorted(CONTENT_DIR.rglob("*.md")):
        raw_text = source_path.read_text(encoding="utf-8")
        meta, body = parse_front_matter(raw_text)
        required = ["title", "date", "slug", "category", "tags", "summary", "cover_image"]
        missing = [name for name in required if name not in meta]
        if missing:
            raise ValueError(f"{source_path}: missing front matter fields: {', '.join(missing)}")

        output_path = ROOT / meta["output_path"] if meta.get("output_path") else default_output_path(meta)
        content_html, headings = render_markdown(body, relative_root(output_path))
        word_count, reading_time = calculate_stats(body)

        # Sync sibling assets if any
        sync_post_assets(source_path, output_path)

        posts.append(
            Post(
                source_path=source_path,
                output_path=output_path,
                title=str(meta["title"]),
                date=normalize_date(meta["date"]),
                slug=str(meta["slug"]),
                category=str(meta["category"]),
                series=str(meta["series"]) if meta.get("series") else None,
                subtitle=str(meta["subtitle"]) if meta.get("subtitle") else None,
                summary=str(meta["summary"]),
                cover_image=str(meta["cover_image"]),
                tags=[str(tag) for tag in meta["tags"]],
                draft=bool(meta.get("draft", False)),
                toc=bool(meta.get("toc", True)),
                metadata=meta,
                body_markdown=body,
                content_html=content_html,
                headings=headings,
                word_count=word_count,
                reading_time_min=reading_time,
            )
        )
    return sorted(posts, key=lambda post: post.date, reverse=True)


def collect_site_data(posts: Iterable[Post]) -> dict:
    published = [post for post in posts if not post.draft]
    category_counts = Counter(post.category for post in published)
    archive_counts = Counter(post.archive_label for post in published)
    tag_counts = Counter(tag for post in published for tag in post.tags)

    categories = [
        {"name": name, "count": count, "slug": slugify(name)}
        for name, count in sorted(category_counts.items())
    ]
    archives = [
        {
            "label": label,
            "count": archive_counts[label],
            "slug": datetime.strptime(label, "%B %Y").strftime("%Y-%m"),
        }
        for label in sorted(
            archive_counts,
            key=lambda label: datetime.strptime(label, "%B %Y"),
            reverse=True,
        )
    ]
    tags = [{"name": name, "count": count, "slug": slugify(name)} for name, count in sorted(tag_counts.items())]

    return {
        "published_posts": published,
        "categories": categories,
        "archives": archives,
        "tags": tags,
        "recent_posts": published[:3],
    }


def render_pages(posts: list[Post]) -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["blog_filter_link"] = blog_filter_link
    env.globals["slugify"] = slugify

    site_data = collect_site_data(posts)

    for post in site_data["published_posts"]:
        template = env.get_template("post.html")
        html_text = template.render(
            page_title=f"{post.title} | XiaoFu's HomePage",
            root_prefix=post.root_prefix,
            post=post,
            site=site_data,
            page_type="post",
        )
        post.output_path.parent.mkdir(parents=True, exist_ok=True)
        post.output_path.write_text(html_text, encoding="utf-8")

    index_template = env.get_template("blog_index.html")
    blog_html = index_template.render(
        page_title="Blog | XiaoFu's HomePage",
        root_prefix="",
        site=site_data,
        page_type="blog",
    )
    (ROOT / "blog.html").write_text(blog_html, encoding="utf-8")


def blog_filter_link(root_prefix: str, **params: str) -> str:
    clean_params = {key: value for key, value in params.items() if value not in (None, "", False)}
    query = urlencode(clean_params)
    return f"{root_prefix}blog.html?{query}" if query else f"{root_prefix}blog.html"


def create_new_post(title: str, category: str = "Notes", series: str | None = None, tags: list[str] | None = None) -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(title)
    cat_dir = CONTENT_DIR / slugify(category)
    cat_dir.mkdir(parents=True, exist_ok=True)
    post_file = cat_dir / f"{slug}.md"

    if post_file.exists():
        print(f"Error: Post file already exists at {post_file}")
        sys.exit(1)

    assets_dir = cat_dir / f"{slug}.assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    tag_list = tags or [category]
    yaml_tags = "\n".join(f"  - {t}" for t in tag_list)
    series_line = f"series: {series}\n" if series else ""

    template = f"""---
title: {title}
subtitle: 
date: {date_str}
slug: {slug}
category: {category}
{series_line}summary: Summary of {title}
cover_image: images/blog/category_cover/ai.jpg
tags:
{yaml_tags}
toc: true
---

# {title}

在这里开始编写正文...

## 支持的特性演示

### 1. 数学公式 (KaTeX)
行内公式示例：$E = mc^2$，以及 $\\nabla_\\theta J(\\theta)$。

块级公式：
$$
\\mathcal{{L}}(\\theta) = \\mathbb{{E}}_{{x \\sim p(x)}} \\left[ \\log p_\\theta(x) \\right]
$$

### 2. 代码高亮
```python
def hello_world():
    print("Hello from XiaoFu's Blog!")
```

### 3. 图片引用
配图存放于同级 `{slug}.assets/` 目录：
`![示例图片]({slug}.assets/example.png)`

> [!NOTE]
> 这是一个 GitHub 风格的提示块。
"""
    post_file.write_text(template, encoding="utf-8")
    print(f"Created new post template at: {post_file}")
    print(f"Created assets folder at: {assets_dir}")
    return post_file


def watch_and_serve(port: int = 8000) -> None:
    # First build
    posts = load_posts()
    render_pages(posts)
    print(f"Initial build completed ({len([p for p in posts if not p.draft])} posts).")

    # File watcher in background thread
    def watch_files():
        last_mtimes: dict[Path, float] = {}

        def check_mtimes():
            watch_dirs = [CONTENT_DIR, TEMPLATE_DIR, ROOT / "css"]
            for d in watch_dirs:
                if not d.exists():
                    continue
                for f in d.rglob("*"):
                    if f.is_file() and not f.name.startswith("."):
                        mtime = f.stat().st_mtime
                        if f in last_mtimes and last_mtimes[f] < mtime:
                            last_mtimes[f] = mtime
                            return True
                        last_mtimes[f] = mtime
            return False

        # initialize
        check_mtimes()

        while True:
            time.sleep(1.0)
            if check_mtimes():
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Detected changes, rebuilding blog...")
                try:
                    p = load_posts()
                    render_pages(p)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Rebuild completed.")
                except Exception as err:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Rebuild error: {err}")

    t = threading.Thread(target=watch_files, daemon=True)
    t.start()

    # Serve files
    os.chdir(str(ROOT))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving local blog at http://localhost:{port}/blog.html (Press Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Blog Generator for xiaofu2730.github.io")
    parser.add_argument("--new", type=str, help="Create a new article template with given title")
    parser.add_argument("-c", "--category", type=str, default="Notes", help="Category for new article")
    parser.add_argument("-s", "--series", type=str, default=None, help="Series name for new article")
    parser.add_argument("-t", "--tags", type=str, default=None, help="Comma-separated tags for new article")
    parser.add_argument("--serve", action="store_true", help="Start local server with file watching and auto-rebuild")
    parser.add_argument("--port", type=int, default=8000, help="Port for local server (default: 8000)")

    args = parser.parse_args()

    if args.new:
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
        create_new_post(args.new, category=args.category, series=args.series, tags=tags)
        return

    if args.serve:
        watch_and_serve(port=args.port)
        return

    # Default build
    posts = load_posts()
    render_pages(posts)
    published_count = len([p for p in posts if not p.draft])
    print(f"Successfully generated {published_count} published posts and blog index.")


if __name__ == "__main__":
    main()
