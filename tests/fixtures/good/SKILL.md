---
name: good-example
description: "Counts lines of code in a directory and prints a per-extension breakdown. Useful when estimating the size of an unfamiliar repo."
version: "1.0.0"
---

# good-example

Counts lines of code, grouped by file extension.

## Usage

```bash
python scripts/count.py <directory>
```

## What it does

Walks the directory, skips `.git` and `node_modules`, and prints a table like:

```
.py    1240
.md     310
total  1550
```
