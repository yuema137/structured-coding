#!/usr/bin/env python3
"""Build/check both local skill packages without installing or configuring hosts."""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from urllib.parse import unquote
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "structured-coding"
DIST = ROOT / "dist"
HOSTS = ("codex", "claude-code")

# Only runtime instructions, user guides, and platform metadata belong in a skill.
# Adding a new source file requires an explicit publication decision here.
PUBLISHED_FILES = {
    "SKILL.md",
    "VERSION",
    "README.md",
    "README.zh-CN.md",
    "agents/openai.yaml",
    "prompts/pr-design-requirements.md",
    "prompts/implementation-working-rules.md",
    "prompts/test-ci-gate-rules.md",
    "references/agent-workflow.md",
    "references/agent-workflow.zh-CN.md",
    "references/adaptation.md",
    "references/adaptation.zh-CN.md",
    "references/platforms.md",
    "references/platforms.zh-CN.md",
    "references/hook-contract.md",
    "references/language-policy.md",
    "references/continuity.md",
    "scripts/continuity.py",
    "scripts/checkpoints.py",
    "scripts/standards.py",
    "references/checkpoints.md",
    "references/standards.md",
    "standards-template.md",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_markdown():
    repository_docs = [f"{name}{suffix}.md" for name in ("README", "TUTORIAL")
                       for suffix in ("", ".zh-CN")]
    for path in [*(ROOT / name for name in repository_docs), *SOURCE.rglob("*.md")]:
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
    # Deliberate baseline change: TUTORIAL.md joined the mirrored set when the
    # walkthrough moved out of the README. See references/language-policy.md.
    expected_sources = {
        "README.md", "TUTORIAL.md", "structured-coding/README.md",
        "structured-coding/references/agent-workflow.md",
        "structured-coding/references/adaptation.md",
        "structured-coding/references/platforms.md",
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
    english_docs = [ROOT / "README.md", ROOT / "TUTORIAL.md"] + [
        p for p in SOURCE.rglob("*.md") if p not in mirrors
    ]
    for path in english_docs:
        require(not re.search(r"[\u3400-\u4dbf\u4e00-\u9fff]", path.read_text()),
                f"Non-English prose in authoritative document: {path}")
    for relative, expected in manifest["specification_sha256"].items():
        require(sha((ROOT / relative).read_bytes()) == expected,
                f"Established specification changed: {relative}")
    presentation = manifest["presentation_source_pair"]
    for language, relative in (("english", "docs/content.en.json"),
                               ("chinese", "docs/content.zh-CN.json")):
        require(presentation[language] == relative, "Unexpected presentation source path")
        require(sha((ROOT / relative).read_bytes()) == presentation[f"{language}_sha256"],
                f"Human presentation source changed; review mirror synchronization: {relative}")
    print(f"PASS {len(mirrors)} translation pairs and unchanged specification baseline")


def source_files(host):
    require(host in HOSTS, f"Unknown host: {host}")
    require(not SOURCE.is_symlink(), "Skill source must not be a symlink")
    actual = set()
    for path in SOURCE.rglob("*"):
        # A local bytecode cache is not a publication question, and letting one
        # fail this check breaks every test that installs the skill.
        if "__pycache__" in path.parts:
            continue
        require(not path.is_symlink(), f"Unexpected source symlink: {path}")
        if path.is_file() and path.name != ".DS_Store":
            actual.add(path.relative_to(SOURCE).as_posix())
    require(actual == PUBLISHED_FILES,
            f"Publishable source file set differs: missing={sorted(PUBLISHED_FILES - actual)}, "
            f"unexpected={sorted(actual - PUBLISHED_FILES)}")
    return {
        relative: SOURCE / relative
        for relative in sorted(PUBLISHED_FILES)
        if not (host == "claude-code" and relative == "agents/openai.yaml")
    }


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
    from build_human_docs import check as check_human_docs

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify existing packages without writing")
    args = parser.parse_args()
    for host in HOSTS:
        source_files(host)
    check_languages()
    check_markdown()
    check_human_docs()
    print("PASS publishable source files, local links, and fences")
    if not args.check:
        build()
    check_packages()


if __name__ == "__main__":
    main()
