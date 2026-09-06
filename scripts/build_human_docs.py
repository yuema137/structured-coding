#!/usr/bin/env python3
"""Build human HTML, README, and diagrams from reviewed bilingual content.

Edit docs/content.en.json first, then synchronize content.zh-CN.json. These
presentation sources are deliberately separate from runtime skill resources.
"""

import argparse
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/yuema137/structured-coding"
CLONE = f"git clone --depth 1 {REPO}.git"
INSTALL = "./structured-coding/scripts/install {} --project /path/to/your-project"
SPEC = "structured-coding/references/hook-contract.md"
ARROWS = "".join(
    f'<path d="{segment}" fill="none" stroke="#91a599" stroke-width="1.8" marker-end="url(#arrow)"/>'
    for segment in (
        "M290 189H320",
        "M585 189H615",
        "M750 276V333",
        "M620 425H585",
        "M325 425H290",
    )
)
LOOP = '<path d="M40 425H20V84H455V103" fill="none" stroke="#91a599" stroke-width="1.5" stroke-dasharray="5 5" marker-end="url(#arrow)"/>'
DEFS = '<defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="none" stroke="#91a599"/></marker></defs>'


def esc(value):
    return html.escape(str(value), quote=True)


def source_link(path):
    return f"{REPO}/blob/main/{path}"


def table_html(rows, headers=None):
    head = (
        ""
        if not headers
        else "<thead><tr>"
        + "".join(f"<th scope='col'>{esc(x)}</th>" for x in headers)
        + "</tr></thead>"
    )
    body = "".join(
        "<tr>" + "".join(f"<td>{esc(x)}</td>" for x in row) + "</tr>" for row in rows
    )
    return f'<div class="table-wrap"><table>{head}<tbody>{body}</tbody></table></div>'


def table_md(rows, headers):
    return (
        "\n".join(
            [
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join("---" for _ in headers) + " |",
            ]
            + ["| " + " | ".join(row) + " |" for row in rows]
        )
        + "\n"
    )


def paragraphs(*values):
    return "".join(f"<p>{esc(value)}</p>" for value in values)


def codebox(command, data):
    return f'<div class="codebox"><pre><code>{esc(command)}</code></pre><button class="copy" type="button">{esc(data["copy"])}</button></div>'


def detail_blocks(data, svg=False):
    compact = (
        '<div class="compact-lanes">'
        + "".join(
            '<div class="compact-lane"><strong>'
            + esc(row[0])
            + "</strong>"
            + "".join(f"<span>{esc(s)}</span>" for s in row[1:])
            + "</div>"
            for row in data["compactLanes"]
        )
        + "</div>"
    )
    if svg:
        suffix = "" if data["lang"] == "en" else ".zh-CN"
        compact = f'<img src="docs/assets/compact{suffix}.svg" alt="{esc(data["compactTitle"])}" width="900">'
    return [
        (
            "records",
            data["recordsTitle"],
            table_html(data["records"]) + paragraphs(data["recordsNote"]),
        ),
        (
            "compact",
            data["compactTitle"],
            paragraphs(data["compactIntro"])
            + compact
            + paragraphs(data["compactNote"]),
        ),
        (
            "hooks",
            data["hooksTitle"],
            f'<p class="status">{esc(data["hooksStatus"])}</p>'
            + paragraphs(data["hooksIntro"])
            + f'<h4>{esc(data["hookInstallTitle"])}</h4><pre><code>{esc(data["hookInstallCommands"])}</code></pre>'
            + paragraphs(data["hookInstallNote"])
            + f'<a href="{source_link("structured-coding/references/continuity.md")}">Continuity preset interface →</a>'
            + table_html(data["hooks"], data["hookColumns"])
            + paragraphs(data["hooksNote"], data["hookExample"])
            + f'<a href="{source_link(SPEC)}">Hook behavior contract →</a>',
        ),
        (
            "prompts",
            data["promptsTitle"],
            paragraphs(data["promptNote"])
            + "".join(
                f"<h4>{esc(label)}</h4><pre><code>{esc(prompt)}</code></pre>"
                for label, prompt in zip(data["promptLabels"], data["prompts"])
            ),
        ),
        ("format", data["formatTitle"], paragraphs(data["format"])),
        ("fit", data["fitTitle"], paragraphs(data["fit"])),
    ]


def render_html(data):
    other = "index.zh-CN.html" if data["lang"] == "en" else "index.html"
    guide = (
        "structured-coding/README.md"
        if data["lang"] == "en"
        else "structured-coding/README.zh-CN.md"
    )
    benefits = "".join(
        f"<article><h3>{esc(title)}</h3><p>{esc(body)}</p></article>"
        for title, body in data["benefits"]
    )
    nodes = "".join(
        f'<li class="flow-node"><div class="node-meta"><span>0{i + 1}</span><span>{esc(role)}</span></div><h3>{esc(title)}</h3><p>{esc(body)}</p></li>'
        for i, (role, title, body) in enumerate(data["steps"])
    )
    cards = "".join(
        f'<article class="kit-card"><span class="tag">{esc(num)}</span><h3>{esc(title)}</h3><p>{esc(body)}</p><a href="{source_link(path)}">{esc(label)} ↗</a></article>'
        for num, title, body, path, label in data["kit"]
    )
    installs = "".join(
        f'<article class="install-card"><h3>{title}</h3>{codebox(INSTALL.format(host), data)}</article>'
        for host, title in [("codex", "Codex"), ("claude-code", "Claude Code")]
    )
    people = "".join(
        f'<li><span class="tag">{esc(num)}</span><h3>{esc(title)}</h3><p>{esc(body)}</p></li>'
        for num, title, body in data["people"]
    )
    details = "\n".join(
        f'<details id="{key}"><summary>{esc(title)}</summary><div class="detail-body">{body}</div></details>'
        for key, title, body in detail_blocks(data)
    )

    def heading(num, key):
        return f'<div class="section-head"><span class="section-no">{num}</span><h2>{esc(data[key])}</h2></div>'

    return f'''<!doctype html>
<html lang="{data["lang"]}" data-copy="{esc(data["copy"])}" data-copied="{esc(data["copied"])}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="{esc(data["subtitle"])}">
<title>Structured Coding — {esc(data["title"])}</title>
<link rel="stylesheet" href="style.css"><script src="ui.js" defer></script>
</head>
<body>
<a class="skip" href="#main">{esc(data["skip"])}</a>
<div class="wrap">
<header class="topbar"><a class="brand" href="#main"><span aria-hidden="true"></span>Structured Coding</a><nav aria-label="{esc(data["navigation"])}"><a class="nav-section" href="#workflow">Workflow</a><a class="nav-section" href="#kit">{esc(data["navKit"])}</a><a class="nav-section" href="#start">{esc(data["navInstall"])}</a><a href="{REPO}">GitHub ↗</a><a class="language" href="{other}">{esc(data["switch"])}</a></nav></header>
<main id="main">
<section class="hero" id="why"><p class="eyebrow">{esc(data["label"])}</p><h1>{esc(data["title"])}</h1><p class="subtitle">{esc(data["subtitle"])}</p><div class="why"><h2>{esc(data["whyTitle"])}</h2><p>{esc(data["why"])}</p></div><div class="benefits">{benefits}</div></section>
<section class="block" id="workflow">{heading("01", "workflowTitle")}<p class="lead">{esc(data["workflowCaption"])}</p>
<div class="flow"><div class="flow-caption">{esc(data["workflowLabel"])}</div><svg class="flow-arrows" viewBox="0 0 900 600" aria-hidden="true">{DEFS}{ARROWS}{LOOP}</svg><ol class="flow-grid">{nodes}</ol><p class="flow-note">{esc(data["workflowNote"])}</p><div class="flow-loop">{esc(data["loopLabel"])}</div></div></section>
<section class="block" id="kit">{heading("02", "kitTitle")}<p class="lead">{esc(data["kitLead"])}</p><div class="kit-grid">{cards}</div></section>
<section class="block" id="start">{heading("03", "startTitle")}<p class="lead">{esc(data["startLead"])}</p><p class="code-label">{esc(data["cloneLabel"])}</p>{codebox(CLONE, data)}<p class="code-label">{esc(data["installLabel"])}</p><div class="install-grid">{installs}</div><p class="small">{esc(data["projectNote"])}</p><div class="callout"><strong>{esc(data["invokeLabel"])}</strong><p>{esc(data["invoke"])}</p></div><p class="small">{esc(data["installNote"])}</p><p class="small"><a href="#hooks">{esc(data["optionalHookNote"])}</a></p></section>
<section class="block" id="people">{heading("04", "peopleTitle")}<p class="lead">{esc(data["peopleLead"])}</p><ol class="people">{people}</ol><div class="autonomy">{esc(data["autonomy"])}</div><p class="small">{esc(data["escalation"])}</p></section>
<section class="block technical" id="technical">{heading("05", "technicalTitle")}<p class="lead">{esc(data["technicalLead"])}</p>{details}</section>
</main>
<footer><p>{esc(data["footer"])}</p><nav><a href="{source_link(guide)}">{esc(data["guideLabel"])} ↗</a><a href="{other}">{esc(data["switch"])}</a></nav></footer>
</div>
</body></html>
'''


def wrap_svg(text, width):
    chinese = bool(re.search(r"[\u4e00-\u9fff]", text))
    # Preserve English terms inside Chinese sentences instead of splitting words.
    words = re.findall(r"[A-Za-z0-9_./$-]+|.", text) if chinese else text.split(" ")
    joiner = "" if chinese else " "

    def size(value):
        return sum(1.75 if ord(c) > 127 else 1 for c in value)

    lines, line = [], ""
    for word in words:
        candidate = line + (joiner if line else "") + word
        if line and size(candidate) > width:
            lines.append(line.strip())
            line = word.lstrip()
        else:
            line = candidate
    return lines + [line.strip()]


def svg_text(x, y, text, size=16, color="#20332e", width=26, weight=400):
    lines = wrap_svg(text, width)
    return "".join(
        f'<text x="{x}" y="{y + i * size * 1.35:g}" font-size="{size}" font-weight="{weight}" fill="{color}">{esc(line)}</text>'
        for i, line in enumerate(lines)
    )


def svg_frame(body, width, height, title):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title"><title id="title">{esc(title)}</title><g font-family="Arial, PingFang SC, Microsoft YaHei, sans-serif">{body}</g></svg>\n'


def workflow_svg(data):
    body = (
        '<rect width="900" height="600" rx="18" fill="#f0f2eb"/>' + DEFS + ARROWS + LOOP
    )
    body += svg_text(40, 49, data["workflowLabel"], 12, "#5a6a63", 80)
    positions = [(40, 112), (335, 112), (630, 112), (630, 348), (335, 348), (40, 348)]
    for i, ((role, title, desc), (x, y)) in enumerate(zip(data["steps"], positions)):
        dark = i == 3
        background = "#285c4e" if dark else "#f2ede1" if i in (2, 4) else "#ffffff"
        ink, muted = ("#ffffff", "#d0e4d6") if dark else ("#20332e", "#5a6a63")
        body += f'<rect x="{x}" y="{y}" width="240" height="154" rx="12" fill="{background}" stroke="#d7ded3"/>'
        body += svg_text(x + 20, y + 29, f"0{i + 1}   {role}", 11, muted, 60)
        body += svg_text(x + 20, y + 65, title, 19, ink, 23, 550)
        body += svg_text(x + 20, y + 116, desc, 12, muted, 33)
    body += f'<text x="450" y="310" text-anchor="middle" font-size="13" fill="#285c4e">{esc(data["workflowNote"])}</text>'
    body += f'<text x="450" y="560" text-anchor="middle" font-size="11" letter-spacing="1" fill="#5a6a63">{esc(data["loopLabel"])}</text>'
    return svg_frame(body, 900, 600, data["workflowTitle"])


def people_svg(data):
    body = '<rect width="900" height="190" rx="12" fill="#f7f7f2"/>'
    for i, (num, title, desc) in enumerate(data["people"]):
        x = 10 + i * 305
        body += (
            f'<rect x="{x}" y="12" width="270" height="165" rx="10" fill="#f2ede1"/>'
        )
        body += (
            svg_text(x + 20, 44, num, 11, "#5a6a63", 60)
            + svg_text(x + 20, 82, title, 21, width=25, weight=550)
            + svg_text(x + 20, 121, desc, 14, "#5a6a63", 28)
        )
        if i < 2:
            body += svg_text(x + 280, 101, "→", 20, "#5a6a63")
    return svg_frame(body, 900, 190, data["peopleTitle"])


def compact_svg(data):
    body = '<rect width="900" height="240" rx="12" fill="#f0f2eb"/>'
    for i, row in enumerate(data["compactLanes"]):
        y = 16 + i * 112
        body += svg_text(20, y + 48, row[0], 13, "#285c4e", 22, 550)
        for j, label in enumerate(row[1:]):
            x = 205 + j * 230
            body += (
                f'<rect x="{x}" y="{y}" width="205" height="94" rx="8" fill="#ffffff"/>'
            )
            body += svg_text(x + 15, y + 42, label, 15, width=24)
            if j < 2:
                body += svg_text(x + 210, y + 49, "→", 17, "#5a6a63")
    return svg_frame(body, 900, 240, data["compactTitle"])


def render_readme(data):
    zh = data["lang"] != "en"
    suffix = ".zh-CN" if zh else ""
    language = (
        "[English source](README.md)" if zh else "[Chinese mirror](README.zh-CN.md)"
    )
    guide = f"structured-coding/README{suffix}.md"
    chunks = [
        f"# Structured Coding\n\n{language} · [{data['htmlLabel']}](docs/index{suffix}.html)\n\n{data['subtitle']}\n",
        f"## {data['whyTitle']}\n\n{data['why']}\n",
    ]
    chunks += [
        "\n".join(f"- **{title}**: {body}" for title, body in data["benefits"]) + "\n"
    ]
    chunks += [
        f"## {data['workflowTitle']}\n\n![{data['workflowTitle']}](docs/assets/workflow{suffix}.svg)\n\n{data['workflowCaption']}\n\n{data['workflowNote']}\n"
    ]
    chunks += [
        f"## {data['kitTitle']}\n\n{data['kitLead']}\n",
        table_md(
            [[f"[{row[1]}]({row[3]})", row[2]] for row in data["kit"]],
            ["Resource", "What it provides"] if not zh else ["资源", "提供什么"],
        ),
    ]
    chunks += [
        f"## {data['startTitle']}\n\n{data['startLead']}\n\n```sh\n{CLONE}\n```\n\n{data['projectNote']}\n\nCodex:\n\n```sh\n{INSTALL.format('codex')}\n```\n\nClaude Code:\n\n```sh\n{INSTALL.format('claude-code')}\n```\n\n{data['invoke']}\n\n{data['installNote']}\n\n[{data['optionalHookNote']}](#hooks)\n"
    ]
    chunks += [
        f"## {data['peopleTitle']}\n\n{data['peopleLead']}\n\n![{data['peopleTitle']}](docs/assets/people{suffix}.svg)\n\n{data['autonomy']}\n\n{data['escalation']}\n"
    ]
    chunks += [f"## {data['technicalTitle']}\n\n{data['technicalLead']}\n"]
    for key, title, body in detail_blocks(data, svg=True):
        chunks += [
            f'<details id="{key}">\n<summary>{esc(title)}</summary>\n\n{body}\n\n</details>\n'
        ]
    chunks += [
        f"---\n\n[{data['guideLabel']}]({guide}) · [{data['htmlLabel']}](docs/index{suffix}.html)\n\n{data['htmlNote']}\n\n{data['footer']}\n"
    ]
    return "\n".join(chunks)


def expected_outputs():
    sources = [
        json.loads((ROOT / f"docs/content.{lang}.json").read_text())
        for lang in ("en", "zh-CN")
    ]
    if set(sources[0]) != set(sources[1]):
        raise ValueError("Human-page translation keys differ")
    for key in (
        "benefits",
        "steps",
        "kit",
        "people",
        "records",
        "compactLanes",
        "hooks",
        "promptLabels",
        "prompts",
    ):
        if len(sources[0][key]) != len(sources[1][key]):
            raise ValueError(f"Human-page mirror structure differs: {key}")
    if sources[0]["prompts"] != sources[1]["prompts"]:
        raise ValueError(
            "Reusable entry prompts must remain identical across languages"
        )
    outputs = {}
    for data in sources:
        suffix = "" if data["lang"] == "en" else ".zh-CN"
        outputs[f"README{suffix}.md"] = render_readme(data)
        outputs[f"docs/index{suffix}.html"] = render_html(data)
        for name, renderer in [
            ("workflow", workflow_svg),
            ("people", people_svg),
            ("compact", compact_svg),
        ]:
            outputs[f"docs/assets/{name}{suffix}.svg"] = renderer(data)
    return outputs


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            if attrs["id"] in self.ids:
                raise ValueError(f"Duplicate HTML id: {attrs['id']}")
            self.ids.add(attrs["id"])
        for name in ("href", "src"):
            if name in attrs:
                self.targets.append(attrs[name])


def check_links(relative, markup):
    page = PageLinks()
    page.feed(markup)
    for target in page.targets:
        url = urlsplit(target)
        if target.startswith(f"{REPO}/blob/main/"):
            resolved = ROOT / unquote(url.path.split("/blob/main/", 1)[1])
        elif url.scheme or url.netloc:
            continue
        elif not url.path:
            if url.fragment and unquote(url.fragment) not in page.ids:
                raise ValueError(f"Broken page anchor: {relative}: {target}")
            continue
        else:
            resolved = (ROOT / relative).parent / unquote(url.path)
        if not resolved.resolve().is_relative_to(ROOT) or not resolved.is_file():
            raise ValueError(
                f"Broken or nonportable presentation link: {relative}: {target}"
            )


def check():
    for relative, expected in expected_outputs().items():
        path = ROOT / relative
        if not path.is_file() or path.read_text() != expected:
            raise ValueError(
                f"Human presentation is stale: {relative}; run scripts/build_human_docs.py"
            )
        if path.suffix in (".md", ".html"):
            check_links(relative, expected)
    print(
        "PASS human-page sources, mirrored content structure, HTML, README, and diagrams"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        for relative, content in expected_outputs().items():
            path = ROOT / relative
            if path.is_symlink():
                raise ValueError(f"Refusing generated-output symlink: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    check()


if __name__ == "__main__":
    main()
