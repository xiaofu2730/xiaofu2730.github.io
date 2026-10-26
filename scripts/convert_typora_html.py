#!/usr/bin/env python3
"""Convert Typora-exported HTML files into pure Markdown with standard LaTeX math using BeautifulSoup."""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag


def clean_tag(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def mml_to_latex(node: ET.Element) -> str:
    tag = clean_tag(node.tag)
    text = (node.text or "").strip()

    if tag == "mi":
        variant = node.attrib.get("{http://www.w3.org/1998/Math/MathML}mathvariant") or node.attrib.get("mathvariant") or node.attrib.get("data-mjx-variant")
        if variant == "-tex-calligraphic" or variant == "script":
            return f"\\mathcal{{{text}}}"
        if variant == "double-struck":
            return f"\\mathbb{{{text}}}"
        if len(text) > 1 and not text.startswith("\\"):
            return f"\\mathrm{{{text}}}"
        return text

    if tag == "mn":
        return text

    if tag == "mo":
        ops = {
            "\u2212": "-",
            "\u22c5": "\\cdot ",
            "\u2248": "\\approx ",
            "\u2264": "\\le ",
            "\u2265": "\\ge ",
            "\u2260": "\\ne ",
            "\u2211": "\\sum ",
            "\u220f": "\\prod ",
            "\u222b": "\\int ",
            "\u223c": "\\sim ",
            "\u2192": "\\to ",
            "\u2208": "\\in ",
            "\u2200": "\\forall ",
            "\u2203": "\\exists ",
            "\u221e": "\\infty ",
            "\u226a": "\\ll ",
            "\u226b": "\\gg ",
            "\u2261": "\\equiv ",
            "\u2207": "\\nabla ",
            "\u2223": "\\mid ",
            ":=": ":= ",
            "=": " = ",
        }
        val = ops.get(text, text)
        if node.attrib.get("data-mjx-texclass") == "OP" and val.strip() in ["max", "min", "lim", "log", "exp"]:
            return f"\\{val.strip()} "
        return val

    if tag == "mtext":
        return f"\\text{{{text}}}"

    if tag == "mspace":
        return " "

    if tag in ("mrow", "math", "TeXAtom", "mstyle"):
        return "".join(mml_to_latex(c) for c in node)

    if tag == "mfrac":
        children = list(node)
        if len(children) == 2:
            return f"\\frac{{{mml_to_latex(children[0])}}}{{{mml_to_latex(children[1])}}}"
        return ""

    if tag == "msub":
        children = list(node)
        if len(children) == 2:
            base = mml_to_latex(children[0])
            sub = mml_to_latex(children[1])
            return f"{base}_{{{sub}}}"
        return ""

    if tag == "msup":
        children = list(node)
        if len(children) == 2:
            base = mml_to_latex(children[0])
            sup = mml_to_latex(children[1])
            return f"{base}^{{{sup}}}"
        return ""

    if tag == "msubsup":
        children = list(node)
        if len(children) == 3:
            base = mml_to_latex(children[0])
            sub = mml_to_latex(children[1])
            sup = mml_to_latex(children[2])
            return f"{base}_{{{sub}}}^{{{sup}}}"
        return ""

    if tag == "msqrt":
        return f"\\sqrt{{{ ''.join(mml_to_latex(c) for c in node) }}}"

    if tag == "munder":
        children = list(node)
        if len(children) == 2:
            base = mml_to_latex(children[0])
            under = mml_to_latex(children[1])
            return f"{base}_{{{under}}}"
        return ""

    if tag == "mover":
        children = list(node)
        if len(children) == 2:
            base = mml_to_latex(children[0])
            accent = mml_to_latex(children[1])
            if accent in ("―", "-", "\\text{―}"):
                return f"\\overline{{{base}}}"
            if accent in ("^", "\\text{^}"):
                return f"\\hat{{{base}}}"
            return f"\\bar{{{base}}}"
        return ""

    if tag == "munderover":
        children = list(node)
        if len(children) == 3:
            base = mml_to_latex(children[0])
            under = mml_to_latex(children[1])
            over = mml_to_latex(children[2])
            return f"{base}_{{{under}}}^{{{over}}}"
        return ""

    if tag == "mtable":
        rows = []
        for r in node:
            r_tag = clean_tag(r.tag)
            if r_tag in ("mtr", "mlabeledtr"):
                cols = []
                label = None
                for d in r:
                    d_tag = clean_tag(d.tag)
                    if d_tag == "mtd":
                        cols.append(mml_to_latex(d))
                    elif d_tag == "mtext":
                        label = d.text.strip("()")
                row_str = " & ".join(cols)
                if label:
                    row_str += f" \\tag{{{label}}}"
                rows.append(row_str)
        if len(rows) == 1 and " & " not in rows[0]:
            return rows[0]
        return "\\begin{aligned}\n  " + " \\\\\n  ".join(rows) + "\n\\end{aligned}"

    return "".join(mml_to_latex(c) for c in node)


def parse_math_ml(raw_mml: str) -> str:
    try:
        if not raw_mml.strip().startswith("<math"):
            raw_mml = f'<math xmlns="http://www.w3.org/1998/Math/MathML">{raw_mml}</math>'
        clean_xml = re.sub(r'\s+xmlns="[^"]+"', "", raw_mml)
        root = ET.fromstring(clean_xml)
        tex = mml_to_latex(root).strip()
        tex = re.sub(r"\s+", " ", tex)
        return tex
    except Exception:
        return ""


def typora_html_to_markdown(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    write_div = soup.find("div", id="write")
    if not write_div:
        write_div = soup.body or soup

    # 1. Remove table of contents
    for toc in write_div.find_all("div", class_="md-toc"):
        toc.decompose()

    # 2. Process block math: <div class="...mathjax-block...">
    for block in write_div.find_all("div", class_=lambda c: c and "mathjax-block" in c):
        script = block.find("script", type=lambda t: t and "math/tex" in t)
        if script and script.string:
            tex = script.string.strip()
        else:
            mml = block.find("math")
            tex = parse_math_ml(str(mml)) if mml else ""
        if tex:
            block.replace_with(soup.new_string(f"\n\n$$\n{tex}\n$$\n\n"))
        else:
            block.decompose()

    # 3. Process mjx-container
    for mjx in write_div.find_all("mjx-container"):
        # Check next sibling for script
        next_sib = mjx.next_sibling
        while next_sib and isinstance(next_sib, NavigableString) and not next_sib.strip():
            next_sib = next_sib.next_sibling

        if next_sib and isinstance(next_sib, Tag) and next_sib.name == "script" and "math/tex" in next_sib.get("type", ""):
            tex = next_sib.string.strip() if next_sib.string else ""
            next_sib.decompose()
        else:
            mml = mjx.find("math")
            tex = parse_math_ml(str(mml)) if mml else ""

        is_display = mjx.get("display") in ("true", "block") or mjx.find("math", display="block")
        if tex:
            if is_display:
                mjx.replace_with(soup.new_string(f"\n\n$$\n{tex}\n$$\n\n"))
            else:
                mjx.replace_with(soup.new_string(f"${tex}$"))
        else:
            mjx.decompose()

    # 4. Process leftover script tags
    for script in write_div.find_all("script", type=lambda t: t and "math/tex" in t):
        tex = script.string.strip() if script.string else ""
        if tex:
            script.replace_with(soup.new_string(f"${tex}$"))
        else:
            script.decompose()

    # 5. Process code fences
    for pre in write_div.find_all("pre", class_=lambda c: c and "md-fences" in c):
        lang = pre.get("lang") or ""
        if not lang:
            for cls in pre.get("class", []):
                if cls.startswith("lang-") or cls.startswith("language-"):
                    lang = cls.split("-", 1)[1]
                    break
        code = pre.get_text().strip()
        pre.replace_with(soup.new_string(f"\n\n```{lang}\n{code}\n```\n\n"))

    # 6. Process images
    for img in write_div.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", "")
        # Clean up path
        src = src.replace("./markdown-img/Self_information.assets/", "Self_information.assets/")
        img.replace_with(soup.new_string(f"![{alt}]({src})"))

    # 7. Process links
    for a in write_div.find_all("a"):
        href = a.get("href", "")
        text = a.get_text().strip()
        if href and text:
            a.replace_with(soup.new_string(f"[{text}]({href})"))

    # 8. Process bold, italic, inline code
    for tag in write_div.find_all(["strong", "b"]):
        tag.replace_with(soup.new_string(f"**{tag.get_text()}**"))
    for tag in write_div.find_all(["em", "i"]):
        tag.replace_with(soup.new_string(f"*{tag.get_text()}*"))
    for tag in write_div.find_all("code"):
        tag.replace_with(soup.new_string(f"`{tag.get_text()}`"))

    # 9. Process headings
    for lvl in range(6, 0, -1):
        for h in write_div.find_all(f"h{lvl}"):
            h_text = h.get_text().strip()
            h.replace_with(soup.new_string(f"\n\n{'#' * lvl} {h_text}\n\n"))

    # 10. Process blockquotes
    for bq in write_div.find_all("blockquote"):
        bq_text = bq.get_text().strip()
        lines = [f"> {line}" for line in bq_text.splitlines() if line.strip()]
        bq.replace_with(soup.new_string("\n\n" + "\n".join(lines) + "\n\n"))

    # 11. Process lists
    for ul in write_div.find_all("ul"):
        items = [f"- {li.get_text().strip()}" for li in ul.find_all("li", recursive=False) if li.get_text().strip()]
        if items:
            ul.replace_with(soup.new_string("\n\n" + "\n".join(items) + "\n\n"))
    for ol in write_div.find_all("ol"):
        items = [f"{i+1}. {li.get_text().strip()}" for i, li in enumerate(ol.find_all("li", recursive=False)) if li.get_text().strip()]
        if items:
            ol.replace_with(soup.new_string("\n\n" + "\n".join(items) + "\n\n"))

    # 12. Process paragraphs
    for p in write_div.find_all("p"):
        p_text = p.get_text().strip()
        if p_text and p_text != "&nbsp;":
            p.replace_with(soup.new_string(f"\n\n{p_text}\n\n"))
        else:
            p.decompose()

    # Get remaining text
    text = write_div.get_text()
    text = html.unescape(text)

    # Clean multiple blank lines
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text + "\n"


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    lib_html = root / "lib" / "html"

    targets = [
        lib_html / "ml" / "reinforcement_learning" / "importance_sampling.html",
        lib_html / "math" / "information_theory" / "Divergence_Variational_Distance.html",
        lib_html / "math" / "information_theory" / "Self_information_final.html",
    ]

    for target in targets:
        if not target.exists():
            continue
        md = typora_html_to_markdown(target.read_text(encoding="utf-8"))
        print(f"=== {target.name} ===")
        print(f"Length: {len(md)} chars")
        # Print headings
        headings = [line for line in md.splitlines() if line.startswith("#")]
        print(f"Headings ({len(headings)}):", headings[:5])
        # Print display math count
        maths = [line for line in md.splitlines() if "$$" in line]
        print(f"Display math count: {len(maths) // 2}")
        print("...\n")
