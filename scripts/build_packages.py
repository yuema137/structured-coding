#!/usr/bin/env python3
"""Build/check both local skill packages without installing or configuring hosts."""

import argparse
import hashlib
import json
import re
import shutil
import string
from pathlib import Path
from urllib.parse import unquote
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "structured-coding"
DIST = ROOT / "dist"
HOSTS = ("codex", "claude-code")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_prompts():
    manifest = json.loads((SOURCE / "references/prompt-provenance.json").read_text())
    raw = (ROOT / manifest["source_file"]).read_bytes()
    require(sha(raw) == manifest["source_sha256"], "Original source hash changed")
    original = raw.decode("utf-8")
    boundaries = {
        "pr-design-requirements": ("audit relevant code base", "\nExecution阶段："),
        "implementation-working-rules": (
            r"\# Implementation Working Rules", r"\#\# TEST / CI / GATE EXECUTION RULES"
        ),
        "test-ci-gate-rules": (
            r"\#\# TEST / CI / GATE EXECUTION RULES", "\nBackward update plan阶段："
        ),
    }
    for name, (start, end) in boundaries.items():
        body = original[original.index(start):original.index(end)].strip() + "\n"
        body = re.sub(
            r"\\(.)", lambda m: m[1] if m[1] in string.punctuation else m[0], body
        )
        entry = manifest["prompts"][name]
        for change in entry["wording_changes"]:
            require(body.count(change["before"]) == 1, f"Ambiguous approved edit: {name}")
            body = body.replace(change["before"], change["after"])
        if name == "pr-design-requirements":
            body = "# PR Design Doc Requirements\n\n" + body
        elif name == "implementation-working-rules":
            body = body.replace("\nPROJECT / PR:", "\n```text\nPROJECT / PR:", 1)
            body = re.sub(r"^````[ \t]*$", "```", body, count=1, flags=re.M)
        else:
            body = re.sub(
                r"^={10,}[ \t]*\n(\d+\.[^\n]*)\n={10,}[ \t]*$",
                lambda m: "### " + m[1].strip(), body, flags=re.M,
            )
        actual = (SOURCE / "prompts" / f"{name}.md").read_bytes()
        require(actual == body.encode("utf-8"), f"Unexpected prompt edits: {name}")
        require(sha(actual) == entry["sha256"], f"Prompt hash changed: {name}")


def check_markdown():
    for path in [ROOT / "README.md", ROOT / "README.zh-CN.md", *SOURCE.rglob("*.md")]:
        content = path.read_text()
        fence = None
        for line in content.splitlines():
            match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
            if match:
                marker, tail = match.groups()
                if fence is None:
                    fence = marker
                elif marker[0] == fence[0] and len(marker) >= len(fence) and not tail.strip():
                    fence = None
                continue
            if fence:
                continue
            for target in re.findall(r"\[[^\]\n]+\]\(([^)]+)\)", line):
                if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    continue
                local = unquote(target.split("#", 1)[0].strip("<>"))
                if local:
                    resolved = (path.parent / local).resolve()
                    boundary = SOURCE if path.is_relative_to(SOURCE) else ROOT
                    require(resolved.is_relative_to(boundary), f"Nonportable link: {path}: {target}")
                    require(resolved.exists(), f"Broken link: {path}: {target}")
        require(fence is None, f"Unclosed code fence: {path}")
    skill = (SOURCE / "SKILL.md").read_text()
    require(skill.startswith("---\nname: structured-coding\ndescription: "), "Invalid skill header")


def heading_levels(content):
    levels = []
    fence = None
    for line in content.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if match:
            marker, tail = match.groups()
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not tail.strip():
                fence = None
        elif fence is None:
            heading = re.match(r"^(#{1,6}) ", line)
            if heading:
                levels.append(len(heading[1]))
    return levels


def check_languages():
    manifest = json.loads((ROOT / "translations.json").read_text())
    expected_sources = {
        "README.md", "structured-coding/README.md",
        "structured-coding/references/agent-workflow.md",
        "structured-coding/references/adaptation.md",
        "structured-coding/references/platforms.md",
        "structured-coding/references/prompt-provenance.md",
    }
    require({p["english"] for p in manifest["pairs"]} == expected_sources,
            "Translation source set differs from the language policy")
    require(len(manifest["pairs"]) == len(expected_sources), "Duplicate translation pair")
    mirrors = set()
    for pair in manifest["pairs"]:
        english_path, chinese_path = ROOT / pair["english"], ROOT / pair["chinese"]
        require(chinese_path == english_path.with_suffix(".zh-CN.md"), "Unexpected mirror path")
        english, chinese = english_path.read_bytes(), chinese_path.read_bytes()
        require(sha(english) == pair["english_sha256"], f"English changed; sync mirror: {pair['english']}")
        require(sha(chinese) == pair["chinese_sha256"], f"Mirror changed; review synchronization: {pair['chinese']}")
        require(heading_levels(english.decode()) == heading_levels(chinese.decode()),
                f"Mirror heading structure differs: {pair['chinese']}")
        require(f"[English source]({english_path.name})" in chinese.decode(),
                f"Missing authoritative-source link: {pair['chinese']}")
        mirrors.add(chinese_path)
    actual_mirrors = set(SOURCE.rglob("*.zh-CN.md")) | set(ROOT.glob("*.zh-CN.md"))
    require(actual_mirrors == mirrors, "Unregistered or missing Chinese mirror")
    english_docs = [ROOT / "README.md"] + [p for p in SOURCE.rglob("*.md") if p not in mirrors]
    for path in english_docs:
        require(not re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", path.read_text()),
                f"Non-English prose in authoritative document: {path}")
    for relative, expected in manifest["specification_sha256"].items():
        require(sha((ROOT / relative).read_bytes()) == expected,
                f"Established specification changed: {relative}")
    print(f"PASS {len(mirrors)} translation pairs and unchanged specification baseline")


def source_files(host):
    files = {}
    for path in sorted(SOURCE.rglob("*")):
        require(not path.is_symlink(), f"Unexpected source symlink: {path}")
        if path.is_file():
            relative = path.relative_to(SOURCE).as_posix()
            if host == "claude-code" and relative == "agents/openai.yaml":
                continue
            files[relative] = path
    return files


def check_output_paths():
    require(not DIST.is_symlink(), "dist must not be a symlink")
    for host in HOSTS:
        for path in (DIST / host, DIST / host / "structured-coding", DIST / f"structured-coding-{host}.zip"):
            require(not path.is_symlink(), f"Refusing generated-output symlink: {path}")
        target = DIST / host / "structured-coding"
        expected = set(source_files(host))
        if target.exists():
            for path in target.rglob("*"):
                require(not path.is_symlink(), f"Refusing generated-output symlink: {path}")
                if path.is_file():
                    require(path.relative_to(target).as_posix() in expected, f"Unknown output file: {path}")


def build():
    check_output_paths()
    for host in HOSTS:
        files = source_files(host)
        target = DIST / host / "structured-coding"
        for relative, source in files.items():
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        archive = DIST / f"structured-coding-{host}.zip"
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
            for relative, source in files.items():
                info = ZipInfo(f"structured-coding/{relative}", date_time=(2026, 9, 5, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, source.read_bytes())


def check_packages():
    check_output_paths()
    for host in HOSTS:
        files = source_files(host)
        target = DIST / host / "structured-coding"
        actual = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
        require(actual == set(files), f"Package file set differs: {host}")
        archive = DIST / f"structured-coding-{host}.zip"
        with ZipFile(archive) as bundle:
            require(bundle.testzip() is None, f"Archive CRC failed: {host}")
            require(set(bundle.namelist()) == {f"structured-coding/{p}" for p in files}, f"Archive file set differs: {host}")
            require(len(bundle.namelist()) == len(files), f"Duplicate archive entries: {host}")
            for relative, source in files.items():
                expected = source.read_bytes()
                require((target / relative).read_bytes() == expected, f"Package content differs: {host}/{relative}")
                require(bundle.read(f"structured-coding/{relative}") == expected, f"Archive content differs: {host}/{relative}")
        print(f"PASS {host}: {len(files)} files; directory and zip match shared source")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify existing packages without writing")
    args = parser.parse_args()
    check_prompts()
    check_languages()
    check_markdown()
    print("PASS original source, complete prompt preservation, approved edits, local links, and fences")
    if not args.check:
        build()
    check_packages()


if __name__ == "__main__":
    main()
