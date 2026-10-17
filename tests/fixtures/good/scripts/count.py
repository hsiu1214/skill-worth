#!/usr/bin/env python3
"""Count lines of code by extension."""
import os
import sys
from collections import Counter

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def count(root):
    table = Counter()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower() or "(none)"
            try:
                with open(os.path.join(dirpath, name), encoding="utf-8", errors="ignore") as f:
                    table[ext] += sum(1 for _ in f)
            except OSError:
                continue
    return table


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    table = count(root)
    for ext, n in table.most_common():
        print("%-8s %6d" % (ext, n))
    print("%-8s %6d" % ("total", sum(table.values())))


if __name__ == "__main__":
    main()
