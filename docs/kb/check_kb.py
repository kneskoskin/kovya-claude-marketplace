#!/usr/bin/env python3
"""Build and verify this repository's knowledge base from Git-visible files.

The checker reads source as text and never imports it. Run with --staged to
verify the Git index. See maintenance.md for the update procedure.
"""
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
from urllib.parse import quote, unquote, urlsplit

ROOT = Path.cwd().resolve()
KB = "docs/kb/"
GENERATED = ("filemap.md", "codemap.md", ".gitattributes")
MAX_READ_BYTES = 2 * 1024 * 1024
SYMBOL_EXTENSIONS = {".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts", ".ps1", ".psm1"}
TEXT_EXTENSIONS = {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts", ".py",
                   ".ps1", ".psm1", ".sql", ".json", ".yml", ".yaml",
                   ".html", ".css", ".toml", ".sh", ".cs", ".rs", ".go",
                   ".c", ".h", ".cpp", ".hpp", ".cc", ".java", ".kt", ".kts",
                   ".swift", ".rb", ".php", ".vue", ".svelte", ".scala", ".r",
                   ".R", ".lua", ".dart", ".ex", ".exs", ".erl", ".clj",
                   ".fs", ".fsx", ".vb", ".pl", ".pm", ".jl", ".zig",
                   ".tf", ".hcl", ".xml", ".gradle", ".cmake", ".bat", ".cmd"}
REVIEW = re.compile(r"<!-- kb-reviewed: ([0-9a-f]{64}) -->")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], creationflags=NO_WINDOW)


def output_path(path, directory=False):
    """Refuse output aliases before reading, creating, writing or chmodding them.

    Checks the current path tree; this is not a lock against concurrent hostile
    filesystem replacement. The explicitly selected repository root is resolved.
    """
    target = ROOT / path
    if not target.is_relative_to(ROOT) or ".." in target.relative_to(ROOT).parts:
        raise ValueError(f"Unsafe output path outside repository: {path}")
    if not target.resolve().is_relative_to(ROOT):
        raise ValueError(f"Unsafe output path leaves repository: {path}")
    current = ROOT
    for part in target.relative_to(ROOT).parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Unsafe output path contains a link/reparse point: {path}")
        if current != target and not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"Unsafe output parent is not a directory: {path}")
        if current == target:
            if directory and not stat.S_ISDIR(info.st_mode):
                raise ValueError(f"Unsafe output target is not a directory: {path}")
            if not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink > 1):
                raise ValueError(f"Unsafe output target is not a single regular file: {path}")
    return target


def write_output(path, content):
    target = output_path(path)
    output_path(target.parent, directory=True).mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
    descriptor, temporary = tempfile.mkstemp(prefix=".project-kb-", dir=target.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content.encode("utf-8") if isinstance(content, str) else content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        # Recheck after writing the temporary file, immediately before replacement.
        os.replace(temporary, output_path(path))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def append_output(path, content):
    target = output_path(path)
    old = b""
    if target.exists():
        with target.open("rb") as handle:
            old = handle.read(MAX_READ_BYTES + 1)
        if len(old) > MAX_READ_BYTES:
            raise ValueError(f"Output append input too large: {path}")
    write_output(path, old + content)


def control_bytes(path):
    """Bound required local control-file reads; never silently replace bad input."""
    with output_path(path).open("rb") as handle:
        data = handle.read(MAX_READ_BYTES + 1)
    if len(data) > MAX_READ_BYTES:
        raise ValueError(f"Required control file too large: {path}")
    return data


def init_outputs():
    return [KB + name for name in ("_inventory.json", "00-overview.md", "decisions.md",
            "README.md", "maintenance.md", "check_kb.py", "pre-commit")] + [".gitignore", "AGENTS.md"]


class Repository:
    def __init__(self, staged=False):
        self.staged = staged
        self.index = {}
        for row in git("ls-files", "--stage", "-z").split(b"\0"):
            if not row:
                continue
            metadata, name = row.split(b"\t", 1)
            mode, oid, stage = metadata.decode("ascii").split()
            path = name.decode("utf-8")
            if stage != "0":
                raise ValueError(f"Resolve unmerged index entry before mapping: {path}")
            self.index[path] = (mode, oid)
        self.paths = set(self.index)
        if not staged:
            self.paths.update(git("ls-files", "-z", "--others", "--exclude-standard").decode().split("\0"))
        self.paths.discard("")
        self.cache = {}
        self.symbol_cache = {}

    def worktree_info(self, path):
        """Inspect ancestors with lstat; never dereference an input alias."""
        parts = PurePosixPath(path).parts
        if not parts or PurePosixPath(path).is_absolute() or ".." in parts:
            return "unsafe path; not read", None
        current = ROOT
        try:
            for part in parts:
                current = current / part
                info = current.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    return "filesystem link/reparse point; not followed", info
            if not stat.S_ISREG(info.st_mode):
                return "non-regular file; not read", info
            return "regular", info
        except FileNotFoundError:
            return "missing; not read", None
        except OSError:
            return "unreadable; not read", None

    def read(self, path):
        if path in self.cache:
            return self.cache[path]
        item = {"text": None, "status": "", "fingerprint": "", "error": False}
        mode, oid = self.index.get(path, ("", ""))
        raw = None
        if mode in {"120000", "160000"}:
            item["status"] = ("symlink" if mode == "120000" else "submodule") + f"; not followed (Git mode {mode})"
            item["fingerprint"] = mode + ":" + oid
        else:
            try:
                if self.staged:
                    size = int(git("cat-file", "-s", oid).strip())
                    if size > MAX_READ_BYTES:
                        item["status"] = "too large; not read"
                    else:
                        # Git objects are immutable; the size check bounds this read.
                        raw = git("cat-file", "blob", oid)
                else:
                    kind, info = self.worktree_info(path)
                    if kind != "regular":
                        item["status"] = kind
                        item["error"] = "link/reparse" not in kind
                        # A tracked regular file replaced by an alias cannot verify.
                        item["error"] |= bool(mode and "link/reparse" in kind)
                    elif info.st_size > MAX_READ_BYTES:
                        item["status"] = "too large; not read"
                    else:
                        with (ROOT / path).open("rb") as handle:
                            raw = handle.read(MAX_READ_BYTES + 1)
                        if len(raw) > MAX_READ_BYTES:
                            raw = None
                            item["status"] = "too large; not read"
                if raw is not None:
                    # One checkout-policy-independent fallback for every bounded
                    # byte input. This is a map fingerprint, not a raw checksum.
                    item["fingerprint"] = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
                    try:
                        if b"\0" in raw:
                            raise UnicodeError("binary")
                        item["text"] = raw.decode("utf-8-sig").replace("\r\n", "\n")
                        item["fingerprint"] = digest(item["text"])
                        item["status"] = "text"
                    except UnicodeError:
                        item["status"] = "binary/undecodable"
            except (OSError, subprocess.SubprocessError, ValueError):
                item["status"] = "unreadable; not read"
                item["error"] = True
        if not item["fingerprint"]:
            item["fingerprint"] = "unverified:" + item["status"]
        self.cache[path] = item
        return item

    def text(self, path):
        item = self.read(path)
        if item["text"] is None:
            raise ValueError(f"Cannot read required KB text {path}: {item['status']}")
        return item["text"]

    def declarations(self, path):
        if path not in self.symbol_cache:
            item = self.read(path)
            reason, found = item["status"], []
            if item["text"] is not None:
                if path.startswith(KB):
                    reason = "knowledge-base support file; not symbol-indexed"
                elif PurePosixPath(path).suffix not in SYMBOL_EXTENSIONS:
                    reason = "unsupported file type; not symbol-indexed"
                else:
                    try:
                        found = symbols(path, item["text"])
                        reason = "indexed"
                    except (SyntaxError, ValueError, RecursionError):
                        reason = "parse failed; not symbol-indexed"
            self.symbol_cache[path] = (reason, found)
        return self.symbol_cache[path]

    def exists(self, path):
        return path in self.paths or any(p.startswith(path.rstrip("/") + "/") for p in self.paths)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_anchor(path):
    return "file-" + digest(path)[:20]


def symbol_anchor(path, name, occurrence=1):
    return "symbol-" + digest(path + "\0" + name + "\0" + str(occurrence))[:20]


def symbols(path, source):
    """Static declaration index, not a full parser or an execution/call graph."""
    found = []
    suffix = PurePosixPath(path).suffix
    if suffix == ".py":
        tree = ast.parse(source, filename=path)
        found = [(n.lineno, n.name) for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    elif suffix in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx", ".mts", ".cts"}:
        patterns = [r"(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(\w+)\s*\(",
                    r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*\w+)?\s*=>",
                    r"(?:export\s+(?:default\s+)?)?class\s+(\w+)"]
        for pattern in patterns:
            found.extend((source[:m.start()].count("\n") + 1, m.group(1))
                         for m in re.finditer(pattern, source))
    elif suffix in {".ps1", ".psm1"}:
        found = [(source[:m.start()].count("\n") + 1, m.group(1)) for m in
                 re.finditer(r"(?im)^\s*function\s+([A-Za-z_][\w-]*)", source)]
    seen = Counter()
    result = []
    for line, name in sorted(set(found)):
        seen[name] += 1
        result.append((line, name, symbol_anchor(path, name, seen[name])))
    return result


def source_paths(repo, inventory):
    excluded = set(inventory["excluded_roots"])
    files = []
    for path in sorted(repo.paths):
        parts = PurePosixPath(path).parts
        if parts[0] in excluded or any(p in {"node_modules", "__pycache__", ".obsidian", "dist", "build"} for p in parts):
            continue
        if path.startswith(KB) or path in inventory.get("excluded_files", []):
            continue
        if PurePosixPath(path).name.startswith(".env") or any(part.lower() in {"secrets", ".secrets"} for part in parts):
            continue
        extensions = set(inventory.get("source_extensions", TEXT_EXTENSIONS))
        if PurePosixPath(path).suffix in extensions or path in inventory["root_files"]:
            files.append(path)
    return files


def source_inventory(repo, inventory):
    grouped = {c["id"]: [] for c in inventory["components"]}
    for path in source_paths(repo, inventory):
        owners = [c["id"] for c in inventory["components"] if any(
            path == p or (p.endswith("/") and path.startswith(p)) for p in c["paths"])]
        if len(owners) != 1:
            raise ValueError(f"Source needs exactly one component owner: {path} ({owners})")
        grouped[owners[0]].append(path)
    return grouped


def component_digest(repo, paths):
    return digest("".join(p + "\0" + repo.read(p)["fingerprint"] + "\n" for p in paths))


def mapped_paths(repo):
    """Full Git-visible inventory. Generated output never becomes its own input."""
    return sorted(p for p in repo.paths if not p.startswith(KB + "_generated/"))


def render(repo, inventory, grouped):
    filemap = ["GENERATED, do not edit", "", "# Filemap", "",
               "Every Git-visible path except docs/kb/_generated; source ownership is a separate gate.",
               "Text hashes normalize UTF-8 BOM and CRLF to UTF-8/LF; undecodable/binary byte fingerprints also normalize CRLF to LF (not raw checksums).",
               "Reads are bounded to 2 MiB. Unread content has no content hash. See [maintenance](../maintenance.md).", ""]
    codemap = ["GENERATED, do not edit", "", "# Codemap", "",
               "Extractors: Python AST (.py); approximate JS/TS declaration patterns (.js .mjs .cjs .jsx .ts .tsx .mts .cts); PowerShell declarations (.ps1 .psm1).",
               "Static declarations, not a semantic or call graph. File coverage does not imply symbol coverage.", ""]
    mapped = mapped_paths(repo)
    owned = set()

    def file_row(path):
        item = repo.read(path)
        target = "../../../" + quote(path, safe="/.-_")
        anchor = file_anchor(path)
        row = [f'<a id="{anchor}"></a>', f"### `{path}`", "",
               f"[Source]({target}) Ã‚Â· [Index status](codemap.md#{anchor})", ""]
        if item["text"] is not None:
            source = item["text"]
            row += [f"Lines: {len(source.splitlines())}; UTF-8 bytes: {len(source.encode('utf-8'))}; SHA-256: `{item['fingerprint']}`", ""]
        else:
            row += [f"({item['status']})", ""]
            if item["status"] == "binary/undecodable":
                row += [f"CRLF-normalized byte SHA-256: `{item['fingerprint']}`", ""]
            elif repo.index.get(path, ("", ""))[0] in {"120000", "160000"}:
                row += [f"Git identity: `{item['fingerprint']}`", ""]
        return row

    for component in inventory["components"]:
        cid = component["id"]
        title = component["title"]
        filemap.extend([f'<a id="component-{cid}"></a>', f"## {title}", "",
                        f"[Explanation](../components/{cid}.md)", ""])
        for path in grouped[cid]:
            owned.add(path)
            filemap.extend(file_row(path))
    filemap.extend(["## Other Git-visible files", "", "These rows are outside configured source-component ownership, not omitted from the file inventory.", ""])
    for path in mapped:
        if path not in owned:
            filemap.extend(file_row(path))
    indexed = [p for p in mapped if repo.declarations(p)[0] == "indexed"]
    unindexed = [p for p in mapped if repo.declarations(p)[0] != "indexed"]
    for title, paths in [(f"Symbol-indexed ({len(indexed)} files)", indexed),
                         (f"Not symbol-indexed ({len(unindexed)} files)", unindexed)]:
        codemap.extend(["## " + title, ""])
        for path in paths:
            anchor = file_anchor(path)
            reason, declarations = repo.declarations(path)
            codemap.extend([f'<a id="{anchor}"></a>', f"### `{path}`", "",
                            f"[Source](../../../{quote(path, safe='/.-_')}) Ã‚Â· [Filemap](filemap.md#{anchor})", ""])
            for line, name, symbol in declarations:
                codemap.extend([f'<a id="{symbol}"></a>', f"#### {name}", "", f"Declaration at line {line}.", ""])
            codemap.extend(["No named declarations detected." if reason == "indexed" and not declarations else
                            ("(" + reason + ")" if reason != "indexed" else ""), ""])
    return {"filemap.md": "\n".join(filemap), "codemap.md": "\n".join(codemap), ".gitattributes": "* -text\n"}


def prose(text):
    text = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text)
    return re.sub(r"`[^`\n]*`", "", text)


def anchors(text):
    text = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text)
    text = re.sub(r"`([^`\n]*)`", r"\1", text)
    ids = set(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)["\']', text))
    seen = Counter()
    for heading in re.findall(r"(?m)^#{1,6}\s+(.+?)(?:\s+#+)?$", text):
        heading = re.sub(r"<[^>]+>", "", heading).lower()
        slug = re.sub(r"[^\w\- ]", "", heading).replace(" ", "-")
        ids.add(slug if not seen[slug] else f"{slug}-{seen[slug]}")
        seen[slug] += 1
    return ids


def links(text):
    """KB dialect: inline links, reference links, Markdown autolinks, HTML href/src."""
    text = prose(text)
    definitions = {m.group(1).strip().lower(): m.group(2).strip("<>") for m in
                   re.finditer(r"(?m)^\s*\[([^\]]+)\]:\s*(<[^>]+>|\S+)", text)}
    body = re.sub(r"(?m)^\s*\[[^\]]+\]:.*$", "", text)
    targets = re.findall(r"!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[\"'][^\n]*?[\"'])?\s*\)", body)
    for label, ref in re.findall(r"!?\[([^\]\n]+)\]\[([^\]\n]*)\]", body):
        key = (ref or label).strip().lower()
        if key not in definitions:
            raise ValueError(f"Undefined reference link: {key}")
        targets.append(definitions[key])
    targets.extend(definitions.values())
    targets.extend(re.findall(r"<(https?://[^>]+|mailto:[^>]+)>", body))
    targets.extend(re.findall(r"(?:href|src)=[\"']([^\"']+)[\"']", body))
    # Shortcut references are supported when a corresponding definition exists.
    targets.extend(definitions[label.lower()] for label in re.findall(r"(?<!!)\[([^\]\n]+)\](?![\[(])", body)
                   if label.lower() in definitions)
    if "[[" in body:
        raise ValueError("Use relative Markdown links, not wiki-links")
    return [t.strip("<>") for t in targets]


def resolve_link(page, target):
    parsed = urlsplit(target)
    if parsed.scheme in {"https", "http", "mailto"}:
        return None
    if parsed.scheme or parsed.netloc or parsed.path.startswith(("/", "\\")):
        raise ValueError(f"Link must be relative: {target}")
    parts = list(PurePosixPath(page).parent.parts) if parsed.path else list(PurePosixPath(page).parts)
    for part in unquote(parsed.path).split("/") if parsed.path else []:
        if part == "..":
            if not parts:
                raise ValueError(f"Link leaves repository: {target}")
            parts.pop()
        elif part not in {"", "."}:
            parts.append(part)
    return "/".join(parts), unquote(parsed.fragment)


def check(repo, inventory, grouped, generated):
    failures = []
    owned = {path for paths in grouped.values() for path in paths}
    for path in mapped_paths(repo):
        item = repo.read(path)
        if item["error"] or (path in owned and item["status"] == "too large; not read"):
            failures.append(f"UNVERIFIED INPUT {path}: {item['status']}")
    # Regenerate into an isolated temp directory; never use the shared map DB.
    with tempfile.TemporaryDirectory(prefix="project-kb-") as folder:
        for name, content in generated.items():
            candidate = Path(folder) / name
            candidate.write_text(content, encoding="utf-8", newline="\n")
            path = KB + "_generated/" + name
            if path not in repo.paths or repo.text(path) != candidate.read_text(encoding="utf-8"):
                failures.append(f"STALE {path}: run --refresh and stage the result")
    pages = sorted(p for p in repo.paths if p.startswith(KB) and p.endswith(".md"))
    page_links = {}
    checked = 0
    anchor_cache = {}
    for page in pages:
        page_links[page] = []
        try:
            targets = links(repo.text(page))
        except ValueError as error:
            failures.append(f"{page}: {error}")
            continue
        for target in targets:
            checked += 1
            try:
                resolved = resolve_link(page, target)
                if resolved is None:
                    continue  # Network access is deliberately excluded.
                dest, anchor = resolved
                page_links[page].append((dest, anchor))
                if not repo.exists(dest):
                    raise ValueError(f"BROKEN FILE {target}")
                if anchor:
                    if dest not in anchor_cache:
                        anchor_cache[dest] = anchors(repo.text(dest))
                    if anchor not in anchor_cache[dest]:
                        raise ValueError(f"BROKEN ANCHOR {target}")
            except (ValueError, OSError) as error:
                failures.append(f"{page}: {error}")
    expected_pages = {KB + "components/" + c["id"] + ".md" for c in inventory["components"]}
    actual_pages = {p for p in pages if p.startswith(KB + "components/")}
    if expected_pages != actual_pages:
        failures.append(f"COMPONENT COVERAGE missing={sorted(expected_pages - actual_pages)} extra={sorted(actual_pages - expected_pages)}")
    for component in inventory["components"]:
        cid = component["id"]
        page = KB + f"components/{cid}.md"
        if page not in repo.paths:
            continue
        destinations = page_links.get(page, [])
        if (KB + "_generated/filemap.md", "component-" + cid) not in destinations:
            failures.append(f"{page}: missing owning filemap heading link")
        owned_symbols = {anchor for path in grouped[cid] for _, _, anchor in repo.declarations(path)[1]}
        valid_anchors = owned_symbols or {file_anchor(path) for path in grouped[cid]}
        if not any(dest == KB + "_generated/codemap.md" and anchor in valid_anchors for dest, anchor in destinations):
            failures.append(f"{page}: missing owning codemap symbol (or file anchor when no symbols are supported)")
        if "KB_DRAFT" in repo.text(page):
            failures.append(f"DRAFT {cid}: replace scaffold prose before acknowledging review")
        match = REVIEW.search(repo.text(page))
        if not match or match.group(1) != component_digest(repo, grouped[cid]):
            failures.append(f"REVIEW {cid}: review its explanation/concepts/decisions, then --review {cid}")
    linked = {dest for page, entries in page_links.items()
              if page == KB + "00-overview.md" or page.startswith(KB + "components/") for dest, _ in entries}
    for page in pages:
        if page.startswith(KB + "concepts/") and page not in linked:
            failures.append(f"ORPHAN CONCEPT {page}")
    print("folder | pages")
    for folder, count in sorted(Counter(str(PurePosixPath(p[len(KB):]).parent) for p in pages).items()):
        print(f"{folder} | {count}")
    print(f"components inventoried | {len(expected_pages)}")
    print(f"component pages | {len(actual_pages)}")
    print(f"source files | {sum(map(len, grouped.values()))}")
    print(f"Git-visible mapped files | {len(mapped_paths(repo))}")
    print(f"links checked | {checked}")
    print(f"failures | {len(failures)}")
    for failure in failures:
        print(failure)
    print("FAIL" if failures else "PASS")
    return 1 if failures else 0


HOOK = '''#!/bin/sh
# project-kb managed hook; maps are updated but never staged automatically.
set -eu
if command -v python3 >/dev/null 2>&1; then
  python3 docs/kb/check_kb.py --refresh
  python3 docs/kb/check_kb.py --staged
elif command -v py >/dev/null 2>&1; then
  py -3 docs/kb/check_kb.py --refresh
  py -3 docs/kb/check_kb.py --staged
else
  echo "Project KB requires Python 3.10+" >&2
  exit 1
fi
'''



def initialize(extra_exclusions=(), extra_extensions=(), subproject=False):
    target = ROOT / KB
    if (target / "_inventory.json").exists():
        raise ValueError("KB already initialized; use --refresh (initialization never overwrites a wiki)")
    repo = Repository()
    excluded = ["docs", "node_modules", "temp", "tmp", "dist", "build", "vendor", ".git",
                ".venv", "venv", ".obsidian", "coverage", ".next", "target"]
    excluded.extend(extra_exclusions)
    extensions = TEXT_EXTENSIONS | set(extra_extensions)
    root_files = sorted(p for p in repo.paths if "/" not in p and
                        (PurePosixPath(p).suffix in extensions or p.startswith("Dockerfile") or p in {"Makefile", "CMakeLists.txt", "Gemfile", "Cargo.lock"})
                        and not p.startswith(".env"))
    candidate = {"excluded_roots": excluded, "root_files": root_files, "components": [], "source_extensions": sorted(extensions)}
    # Group immediate package/app/service directories; other source roots stay together.
    groups = {}
    for path in source_paths(repo, candidate):
        parts = PurePosixPath(path).parts
        if len(parts) == 1:
            groups.setdefault("project-config", []).append(path)
        else:
            depth = 2 if parts[0] in {"apps", "packages", "services"} and len(parts) > 2 else 1
            prefix = "/".join(parts[:depth]) + "/"
            cid = re.sub(r"[^a-z0-9]+", "-", prefix.lower()).strip("-")
            if cid in groups and groups[cid] != [prefix]:
                raise ValueError(f"Component name collision: {cid}; initialize with unambiguous directory names")
            groups[cid] = [prefix]
    candidate["components"] = [{"id": cid, "title": cid.replace("-", " ").title(), "paths": paths}
                               for cid, paths in sorted(groups.items())]
    if not groups:
        raise ValueError("No source found in configured scope; extend source_extensions for this project")
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "HEAD"], capture_output=True, text=True, creationflags=NO_WINDOW)
    candidate.update({"schema_version": 1, "project": ROOT.name,
                      "git_scope_root": "." if subproject else None,
                      "generated_at": datetime.now(timezone.utc).isoformat(),
                      "derived_from_commit": head.stdout.strip() if head.returncode == 0 else None,
                      "basis": "working tree including nonignored untracked source; not a clean-commit claim",
                      "source_extensions": sorted(extensions),
                      "inventory_method": "git ls-files --cached --others --exclude-standard, filtered by declared extensions, root files and exclusions"})
    grouped = source_inventory(repo, candidate)
    candidate["initial_source_files"] = {cid: {p: repo.read(p)["fingerprint"] for p in paths} for cid, paths in grouped.items()}
    planned = init_outputs() + [KB + "components/" + c["id"] + ".md" for c in candidate["components"]]
    for path in planned:
        output_path(path)
    output_path(KB + "concepts", directory=True).mkdir(parents=True, exist_ok=True)
    write_output(KB + "_inventory.json", json.dumps(candidate, indent=2) + "\n")
    for component in candidate["components"]:
        cid = component["id"]
        declarations = [(p, anchor, name) for p in grouped[cid] for _, name, anchor in repo.declarations(p)[1]]
        if declarations:
            path, anchor, name = declarations[0]
        else:
            path = grouped[cid][0]
            anchor, name = file_anchor(path), path
        content = (f"# {component['title']}\n\nKB_DRAFT: Explain purpose, public entry points, dependencies, dependents and known limitations from source.\n\n"
                   f"[Owning files](../_generated/filemap.md#component-{cid}) Ã‚Â· "
                   f"[Entry: {name}](../_generated/codemap.md#{anchor})\n")
        write_output(KB + "components/" + cid + ".md", content)
    overview = f"# {ROOT.name} knowledge base\n\nGit is the source of truth; Obsidian is an optional viewer.\n\n"
    overview += "\n".join(f"- [{c['title']}](components/{c['id']}.md)" for c in candidate["components"])
    overview += "\n\n[Filemap](_generated/filemap.md) Ã‚Â· [Codemap](_generated/codemap.md) Ã‚Â· [Decisions](decisions.md) Ã‚Â· [Maintenance](maintenance.md)\n"
    write_output(KB + "00-overview.md", overview)
    write_output(KB + "decisions.md", "# Decisions\n\nStarted " + datetime.now(timezone.utc).date().isoformat() + ". Seed from this repository's approved plans; do not invent attribution.\n\n| Date | Decision | Why | Who decided |\n|---|---|---|---|\n")
    write_output(KB + "README.md", "Regenerate: `python docs/kb/check_kb.py --refresh` from the repository root.\nCheck: `python docs/kb/check_kb.py` (Python 3.10+).\nOpen this repository as an Obsidian vault; start at [the overview](00-overview.md).\n")
    write_output(KB + "maintenance.md", MAINTENANCE)
    installed = target / "check_kb.py"
    if Path(__file__).resolve() != installed.resolve():
        write_output(KB + "check_kb.py", Path(__file__).read_bytes())
    write_output(KB + "pre-commit", HOOK)
    output_path(KB + "pre-commit").chmod(0o755)
    ignore = output_path(".gitignore")
    old = control_bytes(".gitignore") if ignore.exists() else b""
    if b".obsidian/" not in old.splitlines():
        eol = b"\r\n" if b"\r\n" in old else b"\n"
        separator = eol if old and not old.endswith((b"\r", b"\n")) else b""
        append_output(".gitignore", separator + b".obsidian/" + eol)
    agent_rules = output_path("AGENTS.md")
    current_rules = control_bytes("AGENTS.md").decode("utf-8-sig") if agent_rules.exists() else ""
    if "<!-- project-kb -->" not in current_rules:
        append_output("AGENTS.md", AGENT_RULES.encode("utf-8"))
    print(f"Initialized {len(groups)} component drafts in {target}")


AGENT_RULES = '''

<!-- project-kb -->
## Project knowledge base

Read `docs/kb/00-overview.md` and the affected component page before changing code. After a code change, run `python docs/kb/check_kb.py --refresh`, update affected explanations/concepts/decisions, and acknowledge reviewed components with `--review COMPONENT`. Do not acknowledge prose review without reading it. Keep the maps and wiki in the same change as the code. Use `--staged` to verify the exact proposed commit. Never hand-edit `_generated/` or silently widen inventory exclusions to make a check pass. See `docs/kb/maintenance.md` for setup and language coverage.
<!-- /project-kb -->
'''


MAINTENANCE = """# Maintaining the package knowledge base

Start with [the overview](00-overview.md), then read the component page affected by a source change. The checked-in `check_kb.py` regenerates the filemap and codemap, reports source changes that need explanation review, validates local documentation links and checks ownership. Python 3.10 or newer and Git are required. Map generation works offline.

## Update and review

From the repository root:

1. Run `py -3 docs/kb/check_kb.py --refresh` to regenerate both maps.
2. Update the affected explanation, concepts or decisions from the current source and caller behavior. If the existing explanation remains accurate, read it and acknowledge that component with `py -3 docs/kb/check_kb.py --review COMPONENT`. Multiple component IDs may be supplied after `--review`.
3. Run `py -3 docs/kb/check_kb.py` for a working-tree check. Before a proposed change is accepted, run `py -3 docs/kb/check_kb.py --staged` against the exact index. This includes partially staged files.

Review records that the author compared the explanation with current behavior. The checker cannot determine whether the prose is semantically true. Draft pages, stale generated maps, missing source and unreviewed source changes fail. Do not acknowledge a component without inspecting its page and owning source.

## Inventory and maps

`_inventory.json` records source ownership, source-language coverage and initialization evidence. Add a component only when a distinct source boundary needs its own explanation. A new source path must have one clear owner. Update the inventory and component page together. Do not exclude an authored file to make review pass.

The filemap and codemap summarize repository files and supported source declarations. They provide navigation for text and binary package contents. Regenerate them with the checker and do not edit generated files by hand.

The `docs/kb/.gitattributes` rule preserves generated file bytes across Windows checkouts.

## Local hook

The included `docs/kb/pre-commit` runs the staged check when Git uses `docs/kb` as its hook directory. A clone may use this hook through its local Git configuration. The hook does not stage files or commit changes. Keep any project-specific hook behavior in the existing hook setup and verify the exact staged content before accepting a change.

## Links

Use relative Markdown links to files and headings in this repository. Link from a component explanation to an owning generated-map symbol when one is available. Use the file anchor for other inputs. Maps do not fetch remote links, and source links must stay within the repository.
"""


def install_hook():
    managed_hook = output_path(KB + "pre-commit")
    if not managed_hook.exists() or control_bytes(KB + "pre-commit").decode("utf-8-sig").replace("\r\n", "\n") != HOOK:
        raise ValueError("Expected managed docs/kb/pre-commit is missing or modified; no hook configuration changed")
    managed_hook.chmod(0o755)
    configured = subprocess.run(["git", "-C", str(ROOT), "config", "--get", "core.hooksPath"], capture_output=True, text=True, creationflags=NO_WINDOW)
    current = configured.stdout.strip()
    if current == "docs/kb":
        print("Project KB hook already installed")
        return
    existing = Path(git("rev-parse", "--git-path", "hooks/pre-commit").decode().strip())
    if not existing.is_absolute():
        existing = ROOT / existing
    if current or existing.exists():
        raise ValueError("Existing hooks preserved. Add 'sh docs/kb/pre-commit' to your current pre-commit path; no hook configuration changed.")
    git("config", "--local", "core.hooksPath", "docs/kb")
    print("Installed local hook: core.hooksPath=docs/kb")


def main():
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Git project root; defaults to installed script's repository or cwd")
    parser.add_argument("--scope", action="store_true", help="explicitly enroll a subproject inside a larger Git repository")
    parser.add_argument("--init", action="store_true", help="scaffold a new project KB without overwriting existing pages")
    parser.add_argument("--exclude-root", action="append", default=[], help="additional top-level output/dependency directory to exclude during initialization")
    parser.add_argument("--source-extension", action="append", default=[], help="additional textual code/config extension during initialization, including the dot")
    parser.add_argument("--install-hook", action="store_true", help="activate local hook if there is no existing hook setup")
    parser.add_argument("--refresh", action="store_true", help="update generated maps, then check")
    parser.add_argument("--review", nargs="+", default=[], metavar="COMPONENT", help="record human/agent review of named component pages")
    parser.add_argument("--staged", action="store_true", help="check Git index content, including partial staging")
    args = parser.parse_args()
    ROOT = (args.root or (Path(__file__).resolve().parents[2] if Path(__file__).parent.name == "kb" else Path.cwd())).resolve()
    actual = Path(git("rev-parse", "--show-toplevel").decode().strip()).resolve()
    if actual != ROOT:
        manifest = output_path(KB + "_inventory.json")
        registered = json.loads(control_bytes(KB + "_inventory.json").decode("utf-8-sig")).get("git_scope_root") == "." if manifest.exists() else False
        if not ROOT.is_relative_to(actual) or not (args.scope or registered):
            parser.error("A subproject requires --scope on initialization")
        if args.install_hook:
            parser.error("Subprojects use the workspace gate; hook/CI installation belongs to the containing repository")
    if args.staged and (args.refresh or args.review or args.init or args.install_hook):
        parser.error("--staged is read-only")
    # Preflight every statically known target before any requested mutation.
    planned = init_outputs() if args.init else []
    if args.init or args.refresh or args.review:
        planned += [KB + "_generated/" + name for name in GENERATED]
    planned += [KB + "components/" + cid + ".md" for cid in args.review]
    if args.install_hook:
        planned.append(KB + "pre-commit")
    for path in planned:
        output_path(path)
    if args.init:
        output_path(KB + "concepts", directory=True)
        output_path(KB + "components", directory=True)
    if args.init:
        initialize(args.exclude_root, args.source_extension, subproject=actual != ROOT)
        args.refresh = True
    if args.install_hook:
        install_hook()
    repo = Repository(args.staged)
    inventory = json.loads(repo.text(KB + "_inventory.json"))
    grouped = source_inventory(repo, inventory)
    unknown = set(args.review) - set(grouped)
    if unknown:
        parser.error(f"unknown components: {sorted(unknown)}")
    for cid in args.review:
        page = output_path(KB + "components/" + cid + ".md")
        content = control_bytes(page).decode("utf-8-sig").replace("\r\n", "\n")
        marker = f"<!-- kb-reviewed: {component_digest(repo, grouped[cid])} -->"
        content = REVIEW.sub("", content).rstrip() + "\n\n" + marker + "\n"
        write_output(page, content)
    if args.refresh or args.review:
        repo = Repository()
    generated = render(repo, inventory, grouped)
    if args.refresh or args.review:
        for name, content in generated.items():
            write_output(KB + "_generated/" + name, content)
        repo = Repository()
    return check(repo, inventory, grouped, generated)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, SyntaxError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
