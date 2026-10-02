#!/usr/bin/env python3
"""项目质量机械检查：输出 JSON 指标供审查流程使用。

用法:
    python mechanical_checks.py [项目根目录]

仅用标准库，结果输出到 stdout。检查项:
- 源码文件分布
- 超大文件（按行数）
- 碎片化指标（过小文件占比与行数分布，仅作定位信号）
- TODO/FIXME/HACK/XXX 统计
- 根目录文档缺失
- 深嵌套目录 / 过宽目录 / 空目录
"""

import json
import os
import sys

SKIP_DIRS = {
    ".git", ".svn", ".hg", ".idea", ".vscode", ".trae", ".trae-cn",
    "node_modules", "venv", ".venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "dist", "build", "target", "out",
    "coverage", ".next", ".nuxt", "vendor", "obj", ".gradle", ".mvn",
}

SOURCE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".go", ".rs",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".m",
    ".mm", ".scala", ".sh", ".ps1", ".vue", ".svelte",
}

TODO_PATTERNS = ("TODO", "FIXME", "HACK", "XXX")

WARN_LINES = 500    # 单文件行数警告阈值
ERROR_LINES = 1000  # 单文件行数严重阈值
MAX_DEPTH = 6       # 目录嵌套深度阈值
MAX_WIDTH = 30      # 单目录直接源码文件数阈值
TINY_LINES = 20     # 单文件行数过小阈值（碎片化信号）
FRAG_RATIO = 0.30   # 过小文件占比阈值（碎片化信号）


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        yield dirpath, dirnames, filenames


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
    if not os.path.isdir(root):
        print(json.dumps({"error": "not a directory: " + root}, ensure_ascii=False))
        sys.exit(1)

    ext_count = {}
    large_files = []
    todo_files = []
    total_todos = 0
    empty_dirs = []
    dir_src_count = {}
    all_dirs = []
    file_lines = []  # (相对路径, 行数)

    for dirpath, dirnames, filenames in walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        all_dirs.append(rel_dir)
        src_names = [f for f in filenames if os.path.splitext(f)[1].lower() in SOURCE_EXTS]
        dir_src_count[rel_dir] = len(src_names)
        if not dirnames and not filenames:
            empty_dirs.append(rel_dir)

        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext not in SOURCE_EXTS:
                continue
            path = os.path.join(dirpath, name)
            ext_count[ext] = ext_count.get(ext, 0) + 1
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()
            except OSError:
                continue
            n = len(lines)
            file_lines.append((os.path.relpath(path, root), n))
            if n >= WARN_LINES:
                large_files.append({
                    "path": os.path.relpath(path, root),
                    "lines": n,
                    "level": "error" if n >= ERROR_LINES else "warn",
                })
            detail = {}
            for line in lines:
                for p in TODO_PATTERNS:
                    if p in line:
                        detail[p] = detail.get(p, 0) + 1
            c = sum(detail.values())
            if c:
                total_todos += c
                todo_files.append({"path": os.path.relpath(path, root), "count": c, "detail": detail})

    deep_dirs = []
    for d in all_dirs:
        if d == ".":
            continue
        depth = d.count(os.sep) + 1
        if depth > MAX_DEPTH:
            deep_dirs.append({"path": d, "depth": depth})
    deep_dirs.sort(key=lambda x: -x["depth"])

    wide_dirs = [
        {"path": d, "files": c}
        for d, c in sorted(dir_src_count.items(), key=lambda x: -x[1])
        if c > MAX_WIDTH and d != "."
    ][:20]

    large_files.sort(key=lambda x: -x["lines"])
    todo_files.sort(key=lambda x: -x["count"])

    # 碎片化指标：仅作定位信号，是否构成过度拆分需人工打开确认
    fragmentation = None
    if file_lines:
        sizes = sorted(n for _, n in file_lines)
        total = len(sizes)
        median = sizes[total // 2] if total % 2 else (sizes[total // 2 - 1] + sizes[total // 2]) / 2
        tiny = [(p, n) for p, n in file_lines if n < TINY_LINES]
        ratio = len(tiny) / total
        frag_flag = ratio > FRAG_RATIO
        tiny.sort(key=lambda x: x[1])
        fragmentation = {
            "median_lines": median,
            "tiny_files_count": len(tiny),
            "tiny_files_ratio": round(ratio, 3),
            "tiny_ratio_threshold": FRAG_RATIO,
            "flag": frag_flag,
            "smallest_files": [{"path": p, "lines": n} for p, n in tiny[:20]] if frag_flag else [],
        }

    entries = os.listdir(root)
    lowered = {e.lower() for e in entries}
    docs = {
        "readme": any(e.startswith("readme") for e in lowered),
        "changelog": any(e.startswith("changelog") for e in lowered),
        "license": any(e.startswith("license") for e in lowered),
        "contributing": any(e.startswith("contributing") for e in lowered),
        "docs_dir": os.path.isdir(os.path.join(root, "docs")),
        "architecture_doc": any(e.startswith("architecture") for e in lowered),
    }

    result = {
        "root": root,
        "total_source_files": sum(ext_count.values()),
        "source_files_by_ext": dict(sorted(ext_count.items(), key=lambda x: -x[1])),
        "large_files": large_files[:20],
        "fragmentation": fragmentation,
        "todos": {"total": total_todos, "top_files": todo_files[:10]},
        "deep_dirs": deep_dirs[:15],
        "wide_dirs": wide_dirs,
        "empty_dirs": [d for d in empty_dirs if d != "."][:20],
        "root_docs": docs,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
