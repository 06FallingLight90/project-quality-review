#!/usr/bin/env python3
"""架构依赖度量：构建模块依赖图，输出依赖环、扇入/扇出、模块级汇总。

用法:
    python dependency_metrics.py [项目根目录]

仅用标准库。支持 Python 与 JS/TS 的 import 解析（其余语言跳过并统计）。
输出 JSON: 文件级依赖环(Tarjan SCC)、扇入扇出 TOP、模块级(顶层目录)依赖环与边数。
"""

import json
import os
import re
import sys

SKIP_DIRS = {
    ".git", ".svn", ".hg", ".idea", ".vscode", ".trae", ".trae-cn",
    "node_modules", "venv", ".venv", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "dist", "build", "target", "out",
    "coverage", ".next", ".nuxt", "vendor", "obj", ".gradle", ".mvn",
}

PY_EXTS = {".py"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"}
RESOLVE_EXTS = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ""]

PY_FROM_RE = re.compile(r"^from\s+([\.\w]+)\s+import\b")
JS_RE = re.compile(
    r"""(?:import\s[^'"]*?from\s*|import\s*|require\s*\(\s*|export\s[^'"]*?from\s*)['"]([^'"]+)['"]""",
)


def norm(rel):
    return rel.replace("\\", "/")


class Graph:
    def __init__(self):
        self.adj = {}

    def add_edge(self, a, b):
        if a == b:
            return
        self.adj.setdefault(a, set())
        self.adj[a].add(b)
        self.adj.setdefault(b, set())

    def nodes(self):
        return list(self.adj.keys())

    def scc(self):
        """Tarjan 迭代版，返回 size>1 或自环的 SCC 列表。"""
        index = {}
        low = {}
        on_stack = set()
        stack = []
        result = []
        counter = [0]

        for start in self.nodes():
            if start in index:
                continue
            work = [(start, iter(sorted(self.adj.get(start, ()))))]
            index[start] = low[start] = counter[0]
            counter[0] += 1
            stack.append(start)
            on_stack.add(start)
            while work:
                node, it = work[-1]
                advanced = False
                for nxt in it:
                    if nxt not in index:
                        index[nxt] = low[nxt] = counter[0]
                        counter[0] += 1
                        stack.append(nxt)
                        on_stack.add(nxt)
                        work.append((nxt, iter(sorted(self.adj.get(nxt, ())))))
                        advanced = True
                        break
                    elif nxt in on_stack:
                        low[node] = min(low[node], index[nxt])
                if advanced:
                    continue
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        comp.append(w)
                        if w == node:
                            break
                    if len(comp) > 1 or node in self.adj.get(node, ()):
                        result.append(sorted(comp))
        return result


def top_degrees(g):
    out_deg = {n: len(g.adj.get(n, ())) for n in g.nodes()}
    in_deg = {n: 0 for n in g.nodes()}
    for n, targets in g.adj.items():
        for t in targets:
            in_deg[t] = in_deg.get(t, 0) + 1
    return in_deg, out_deg


def main():
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
    if not os.path.isdir(root):
        print(json.dumps({"error": "not a directory: " + root}, ensure_ascii=False))
        sys.exit(1)

    files = {}  # rel_key -> lang
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            rel = norm(os.path.relpath(os.path.join(dirpath, name), root))
            if ext in PY_EXTS:
                files[rel] = "py"
            elif ext in JS_EXTS:
                files[rel] = "js"

    g = Graph()          # 文件级
    external = {"py": 0, "js": 0}   # 标准库/三方包等外部依赖（正常）
    unresolved = {"py": 0, "js": 0} # 相对导入失败等可疑情况

    def resolve_py(spec, cur_rel, cur_dir):
        if spec.startswith("."):
            parts = spec.split(".")
            up = len([p for p in parts if p == ""])
            base = parts[up:]
            target_dir = cur_dir
            for _ in range(up - 1):
                target_dir = os.path.dirname(target_dir)
            rel = norm(os.path.join(target_dir, *base))
            for cand in (rel + ".py", rel + "/__init__.py"):
                if cand in files:
                    return cand
            unresolved["py"] += 1
            return None
        # 绝对导入：按 root 与当前文件各级祖先目录（sys.path 语义）依次尝试
        rel_base = norm(spec.replace(".", "/"))
        candidates_bases = [""]
        parts = cur_dir.split("/") if cur_dir else []
        for i in range(1, len(parts) + 1):
            candidates_bases.append("/".join(parts[:i]))
        for base_dir in candidates_bases:
            joined = norm(os.path.join(base_dir, rel_base)) if base_dir else rel_base
            for cand in (joined + ".py", joined + "/__init__.py"):
                if cand in files:
                    return cand
        external["py"] += 1
        return None

    def resolve_js(spec, cur_rel, cur_dir):
        if not spec.startswith("."):
            return None  # npm 包忽略
        target = norm(os.path.normpath(os.path.join(cur_dir, spec)))
        base = os.path.splitext(target)[0] if os.path.splitext(target)[1] else target
        for cand in [base + e for e in RESOLVE_EXTS] + [base + "/index" + e for e in RESOLVE_EXTS if e]:
            if cand in files:
                return cand
        unresolved["js"] += 1
        return None

    for rel, lang in files.items():
        path = os.path.join(root, rel)
        cur_dir = os.path.dirname(rel)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
                src = fh.read()
        except OSError:
            continue
        if lang == "py":
            for line in src.splitlines():
                s = line.strip()
                if s.startswith("from "):
                    m = PY_FROM_RE.match(s)
                    if m:
                        r = resolve_py(m.group(1), rel, cur_dir)
                        if r:
                            g.add_edge(rel, r)
                elif s.startswith("import "):
                    names = s[7:].split("#")[0]
                    for name in names.split(","):
                        name = name.strip().split(" as ")[0].strip()
                        if not name:
                            continue
                        r = resolve_py(name, rel, cur_dir)
                        if r:
                            g.add_edge(rel, r)
        else:
            for m in JS_RE.finditer(src):
                r = resolve_js(m.group(1), rel, cur_dir)
                if r:
                    g.add_edge(rel, r)

    in_deg, out_deg = top_degrees(g)

    # 模块级聚合图：默认取顶层目录；全部文件同层时下沉到第二层
    tops = {rel.split("/")[0] for rel in files}
    single_top = len(tops) <= 1

    def module_of(rel_key):
        parts = rel_key.split("/")
        if not single_top or len(parts) < 2:
            return parts[0]
        return "/".join(parts[:2]) if len(parts) > 2 else rel_key

    mg = Graph()
    for n, targets in g.adj.items():
        for t in targets:
            mg.add_edge(module_of(n), module_of(t))
    m_in, m_out = top_degrees(mg)

    result = {
        "root": root,
        "files_analyzed": len(files),
        "by_lang": {
            "py": sum(1 for v in files.values() if v == "py"),
            "js": sum(1 for v in files.values() if v == "js"),
        },
        "total_edges": sum(len(v) for v in g.adj.values()),
        "external_imports": external,
        "unresolved_imports": unresolved,
        "file_cycles": [c for c in g.scc()][:15],
        "file_cycle_count": len(g.scc()),
        "top_fan_out": sorted(out_deg.items(), key=lambda x: -x[1])[:15],
        "top_fan_in": sorted(in_deg.items(), key=lambda x: -x[1])[:15],
        "module_cycles": [c for c in mg.scc()][:10],
        "module_cycle_count": len(mg.scc()),
        "module_summary": sorted(
            (
                {"module": m, "fan_in": m_in.get(m, 0), "fan_out": m_out.get(m, 0)}
                for m in mg.nodes()
            ),
            key=lambda x: -(x["fan_in"] + x["fan_out"]),
        )[:20],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
