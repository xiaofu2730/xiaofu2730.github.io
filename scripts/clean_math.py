#!/usr/bin/env python3
"""Normalize LaTeX formulas in markdown posts.

Replaces misaligned equation tags, removes empty text wrappers, and replaces unicode math symbols with standard LaTeX macros.
"""
from __future__ import annotations

import re
from pathlib import Path

UNICODE_MATH_MAP = {
    "∀": r"\forall ",
    "∃": r"\exists ",
    "∈": r"\in ",
    "⊂": r"\subset ",
    "⊆": r"\subseteq ",
    "∪": r"\cup ",
    "∩": r"\cap ",
    "⟹": r"\implies ",
    "⟺": r"\iff ",
    "→": r"\to ",
    "·": r"\cdot ",
    "×": r"\times ",
    "−": r"-",
    "≤": r"\le ",
    "≥": r"\ge ",
    "≠": r"\ne ",
    "θ": r"\theta ",
    "τ": r"\tau ",
    "π": r"\pi ",
    "β": r"\beta ",
    "α": r"\alpha ",
    "γ": r"\gamma ",
    "λ": r"\lambda ",
    "μ": r"\mu ",
    "σ": r"\sigma ",
    "δ": r"\delta ",
    "ϵ": r"\epsilon ",
    "∇": r"\nabla ",
    "∞": r"\infty ",
}


def clean_latex_string(s: str) -> str:
    # 1. Fix single-line or multi-line aligned with label: \begin{aligned} \text{(X-Y)} & ... \end{aligned}
    def repl_aligned_label(m: re.Match) -> str:
        label = m.group(1).strip("()")
        inner = m.group(2).strip()
        # If inner has its own aligned
        inner = re.sub(r"^\\begin\{aligned\}\s*(.*?)\s*\\end\{aligned\}$", r"\1", inner, flags=re.DOTALL).strip()
        if "\\\\" in inner:
            return f"\\begin{{aligned}}\n  {inner}\n\\end{{aligned}} \\tag{{{label}}}"
        return f"{inner} \\tag{{{label}}}"

    s = re.sub(
        r"\\begin\{aligned\}\s*\\text\{(\([^)]+\))\}\s*&\s*(.*?)\s*\\end\{aligned\}",
        repl_aligned_label,
        s,
        flags=re.DOTALL,
    )

    # 2. Clean if / then with text
    s = re.sub(r"\\text\{\s*\}\s*if(?:\s*\\text\{\s*\})?", lambda _: r"\quad \text{if } ", s)
    s = re.sub(r"\\text\{\s*\}\s*then(?:\s*\\text\{\s*\})?", lambda _: r"\quad \text{then } ", s)
    s = re.sub(r"\bif([a-zA-Z0-9_\\])", lambda m: r"\text{if } " + m.group(1), s)
    s = re.sub(r"\bthen([a-zA-Z0-9_\\])", lambda m: r"\text{then } " + m.group(1), s)

    # 3. Clean empty text blocks
    s = re.sub(r"\\text\{\s*\}\s*\\text\{\s*\}", lambda _: r"\quad ", s)
    s = re.sub(r"\\text\{\s*\}", lambda _: "", s)

    # 4. Replace unicode math
    for u, l in UNICODE_MATH_MAP.items():
        s = s.replace(u, l)

    # 5. Normalize spacing
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def clean_markdown_file(path: Path) -> None:
    content = path.read_text(encoding="utf-8")

    # Stash front matter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", content, re.DOTALL)
    if fm_match:
        fm = f"---\n{fm_match.group(1)}\n---\n\n"
        body = fm_match.group(2)
    else:
        fm = ""
        body = content

    # Replace block math
    def repl_block(m: re.Match) -> str:
        cleaned = clean_latex_string(m.group(1))
        return f"$$\n{cleaned}\n$$"

    body = re.sub(r"\$\$\s*\n?(.*?)\n?\s*\$\$", repl_block, body, flags=re.DOTALL)

    # Replace inline math
    def repl_inline(m: re.Match) -> str:
        cleaned = clean_latex_string(m.group(1))
        return f"${cleaned}$"

    body = re.sub(r"(?<!\\)\$(?!\$)([^\n$]+?)(?<!\\)\$", repl_inline, body)

    path.write_text(fm + body.strip() + "\n", encoding="utf-8")
    print(f"Cleaned formulas in: {path.name}")


def main():
    root = Path(__file__).resolve().parent.parent
    posts_dir = root / "content" / "posts"
    for md_file in posts_dir.rglob("*.md"):
        clean_markdown_file(md_file)


if __name__ == "__main__":
    main()
