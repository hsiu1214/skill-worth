# The Empty Skill Problem

> I sampled the 30 most-installed agent skills in a marketplace. Three of them do nothing. Those three had been installed 104,762 times.

## The find

There is a skill called `summarize`. 45,959 installs.

Its entire contents: **two files, 3,558 bytes, zero code**. Inside its `SKILL.md`, the author wrote this:

> This skill was auto-generated from a planning spec; implementation details (API, CLI, connection) should be filled in at runtime.

The author said it plainly: **this thing isn't finished.**

What does it claim to do? Summarize web pages, PDFs, Word documents, podcasts, and YouTube videos. I checked the machine it was installed on: no `yt-dlp`, no `ffmpeg`, no `whisper`. Not one of those claims can run.

Forty-five thousand people installed it.

## How I measured

I didn't want to argue from vibes, so I sampled:

| | |
|---|---|
| Sample | Skills with ≥500 installs, top 30 by install count |
| Source | Overall top 50 + 11 category boards → 207 unique skills |
| Method | Download each zip, extract, **static inspection only — never execute** |
| Scoring | Five weighted dimensions (substance 40 / consistency 25 / clarity 15 / safety 10 / maintenance 10) |

**Scope note:** 28 of 30 scanned successfully; 2 had corrupt zips at the storage layer. Verdicts apply to **the package actually downloaded** — the same slug can have multiple publishers and changed contents.

## Results

| Verdict | Count |
|---|---|
| Worth installing | 24 |
| Depends on your needs | 1 |
| **Skip (empty)** | **3** |

Those 28 skills had **551,968** installs between them. The three empty ones accounted for **104,762**.

Eleven percent. Not catastrophic — except the sample was already filtered to skills with **500+ installs**.

## The interesting part: they're stamped from one mold

The three are `summarize` (45,959), `skill-vetter` (37,273), `weather` (21,530).

Completely different purposes. **Identical rejection reason:**

> The author states the implementation is pending

Same score (28). Same failure. Same structure: a block reading "Category: X / Skill type: X / Risk level: low / Gate: L0", followed by filler that would be true of any skill in existence — "confirm the input source", "keep formatting consistent", "validate one sample before batch processing".

And the source: **all three from `@clawhub_*` mirrors**, every one with the same changelog line, `Synced by skillhub pipeline`.

Three authors, three different functions, one identical shape of output. That's not a coincidence — that's one pipeline running in bulk.

## Why security scanners don't catch this

There are good skill security tools now — NVIDIA's SkillSpector (68 vulnerability patterns, YARA, taint tracking), Snyk's agent-scan, Cisco's skill-scanner. **Use them.**

But they answer "is this dangerous?" And for an empty skill, the answer is: **completely safe**.

- No malicious code → not flagged
- No network calls → not flagged
- No reading `~/.ssh` → not flagged
- No hardcoded secrets → not flagged

A skill that does nothing is a model citizen to a security scanner. It really doesn't steal anything. It doesn't take anything, because it doesn't do anything.

Two different failure modes:

- Security: **it can harm you**
- Emptiness: **it wastes your time and trust**

## Four checks you can do without any tool

**1. Is there code at all?**

No code doesn't mean fake — a checklist, a writing rubric, a diagnostic protocol lives in prose. The question is which type it claims to be.

**2. Does it say "here's how to judge" or "here's me doing it"?**

- "Here are the four steps to review a skill" → knowledge artifact, no code needed
- "Crawls 16 engines and merges the results" → execution claim, no code means empty

**3. Search for these phrases**

Grep the `SKILL.md` for "to be implemented", "auto-generated", "fill in at runtime", "待补全". **If the author admits it isn't finished, it usually isn't.**

**4. Do the referenced files exist?**

Many skills say "run `scripts/foo.py`". Go look. In some sampled skills, half the referenced files weren't there.

## Why this actually matters

Empty skills don't make headlines the way malware does, but the cumulative effect is quieter and worse:

Someone installs three empty skills, tries two of them, nothing happens. They conclude "AI skills are vaporware" — and stop installing anything, including the ones that are genuinely excellent.

**Gresham's law, but for skills: the bad drives out the good, not by being worse, but by being louder.**

## Appendix: the tool

I turned the checks above into [skill-worth](https://github.com/hsiu1214/skill-worth) — MIT, zero dependencies.

```bash
pip install git+https://github.com/hsiu1214/skill-worth.git
skill-worth check ./some-skill
```

But it's just those four checks, automated. **If you can do them by hand, you don't need it.**

---

*Data collected 2026-10-18. Sampling method stated above. Verdicts describe the packages actually downloaded, not the authors.*
