# skill-worth

**Does this AI agent skill actually do what it claims?**

[中文说明](README.zh-CN.md) · [Report sample](examples/report-sample.html)

---

Security scanners tell you whether a skill is *dangerous*. None of them tell you whether it's *empty*.

There are already excellent tools for the first question — [NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector) (68 vulnerability patterns, YARA, taint tracking), [Snyk agent-scan](https://github.com/snyk/agent-scan), [Cisco skill-scanner](https://github.com/cisco-ai-defense/skill-scanner). Use them. This tool answers a different question, and they all pass it with flying colors:

> A skill can be perfectly safe, contain no malicious code, no network calls, no secrets — and still do absolutely nothing.

`skill-worth` finds those.

## The problem

In a sample of 30 popular marketplace skills (≥500 installs each), **3 were empty** — and those 3 had been installed **104,762 times** combined. All three had the same tell: the author had written, in their own SKILL.md, that the implementation "would be filled in later."

An empty skill isn't a security incident. It's just wasted context, wasted installs, and a user quietly concluding that "AI skills don't really work."

## What it checks

Five weighted dimensions, 100 points:

| Dimension | Weight | Question |
|---|---|---|
| **Substance** | 40 | Is there runnable code? If it's a document, are the steps/checklists/examples complete? |
| **Consistency** | 25 | Do the claims match reality? Do the referenced files actually exist? |
| **Clarity** | 15 | Can it state its purpose in one sentence? Are triggers too broad? |
| **Safety** | 10 | Deletions, dynamic execution, hardcoded secrets |
| **Maintenance** | 10 | Structure, template filler, dead references |

**Four instant disqualifiers** (regardless of score):

1. The author admits it's unimplemented (`"details to be filled in at runtime"`)
2. It teaches you to call a tool that doesn't exist (`web_fetch(...)` when the real one is `WebFetch`)
3. It claims to *do* something (crawl, batch, call an API) with zero code files
4. It has code files, but they're all `pass` / `TODO` / empty stubs

## The hard part: no code ≠ useless

This is where every naive linter gets it wrong. A checklist, a writing methodology, a diagnostic protocol — these live entirely in prose. They need no code and they work fine.

So the scanner separates:

- **Execution claims** — "crawls 16 engines", "downloads and merges", "calls the API". No code → empty.
- **Knowledge artifacts** — "here's how to review a skill", "here's the writing rubric". Complete steps + examples → legitimate.

Getting this wrong in either direction makes the tool useless. The scanner was tested against both.

## Install

```bash
pip install git+https://github.com/hsiu1214/skill-worth.git
```

> Not on PyPI yet — install straight from the repo.

No dependencies. Python 3.8+.

## Use

**Evaluate one skill before installing:**

```bash
skill-worth check /path/to/some-skill
```

**Audit everything you have installed** (auto-detects WorkBuddy, Claude Code, Codex, Cursor, Windsurf):

```bash
skill-worth check
```

**Sample the marketplace** (downloads and inspects top skills, ~40s for 30):

```bash
skill-worth market --top 30
```

Each run writes `skill-worth-report.html` to the current directory. `--open` opens it when done; `--json out.json` also saves the raw data.

Output is a single self-contained HTML file — no CDN, no JS framework, opens offline, prints cleanly, readable on a phone.

Or run from source without installing:

```bash
python -m skill_worth check ./some-skill
```

## Use as a GitHub Action

Gate a skill repo in CI — the build fails when a skill does nothing:

```yaml
- uses: hsiu1214/skill-worth@v1
  with:
    path: ./skills
    fail-on: skip        # never | skip | depends
```

It writes a summary table straight into the job summary, so the failure explains itself without opening logs.

Outputs: `total`, `worth`, `skip`, `report`, `json`.

Keep the HTML report as an artifact if you want it:

```yaml
- uses: hsiu1214/skill-worth@v1
  with:
    path: ./skills
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: skill-worth-report
    path: skill-worth-report.html
```

## What the output looks like

Three verdicts, each with human-readable reasons and expandable evidence:

```
worth     97   Real code (775 lines across 3 files), references all resolve
depends   61   No code, but steps/checklists/examples are complete — a document, not a tool
skip      28   Author states implementation is pending; 3 template phrases; 0 code files
```

Absolute paths and namespaces are stripped before the report is written. Verified zero leaks — reports are meant to be shared.

## Tested against known cases

| Skill | Installs | Verdict |
|---|---|---|
| `multi-search-engine` | 2.04M | **skip** — claims 16 engines, zero scripts, teaches a nonexistent tool |
| `summarize` | 46K | **skip** — 3.5KB, author admits it's auto-generated scaffolding |
| `skill-vetter` | 307K (real version) | **worth** — 140 lines of prose, but a complete 4-step protocol |
| `self-improving-agent` | 86K | **worth** — 5 real code files, hook is memory-only, zero network |

Two of the highest-install skills in the market are empty. Install count and quality are essentially unrelated — it tracks how well the name communicates a need, nothing more.

## Caveats

- **Static analysis only.** Never executes scanned code.
- **Presence, not correctness.** It checks whether implementations exist, not whether they're any good.
- **Short-but-excellent skills get underscored.** Conciseness looks like thinness to a text-density heuristic.
- **Same name ≠ same package.** The marketplace can serve different content under an identical slug and version. Verdicts apply to the package actually scanned, which the report states explicitly.

## License

MIT — see [LICENSE](LICENSE).
