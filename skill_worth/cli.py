# -*- coding: utf-8 -*-
"""
skill-worth 命令行入口

  skill-worth check [PATH]     # 评估一个 skill；不给 PATH 就盘点已装的
  skill-worth market           # 抽样市集热门 skill
"""
import io
import os
import sys
import json
import argparse
import tempfile
import webbrowser

from . import __version__
from . import scan as scan_mod
from .render import render as render_report

BANNER = "skill-worth"


def _bar(t):
    """一条紧凑的分布条"""
    parts = []
    if t["worth"]:
        parts.append("%d worth" % t["worth"])
    if t["depends"]:
        parts.append("%d depends" % t["depends"])
    if t["skip"]:
        parts.append("%d skip" % t["skip"])
    return " · ".join(parts)


def cmd_check(args):
    if args.path:
        target = os.path.abspath(os.path.expanduser(args.path))
        if not os.path.isdir(target):
            print("error: not a directory: %s" % target, file=sys.stderr)
            return 2
        # 自己就是一个 skill，还是「装了一堆 skill 的目录」？
        if os.path.isfile(os.path.join(target, "SKILL.md")):
            payload = scan_mod.scan_target(target)
        else:
            has_sub = any(
                os.path.isfile(os.path.join(target, n, "SKILL.md"))
                for n in os.listdir(target)
                if os.path.isdir(os.path.join(target, n))
            )
            if not has_sub:
                print("error: no SKILL.md here, and no sub-folder contains one: %s"
                      % target, file=sys.stderr)
                return 2
            payload, _ = scan_mod.scan_dirs([target])
        if payload is None:
            print("error: no SKILL.md in %s" % target, file=sys.stderr)
            return 2
    else:
        payload, roots = scan_mod.scan_dirs()
        if not roots:
            print("error: no skills directory found. Looked in:", file=sys.stderr)
            for c in scan_mod.CANDIDATE_DIRS:
                print("  " + os.path.expanduser(c), file=sys.stderr)
            print("hint: pass a path directly — skill-worth check ./my-skill", file=sys.stderr)
            return 2

    skills, t = payload["skills"], payload["totals"]

    # 写 JSON
    tmpdir = tempfile.mkdtemp(prefix="skillworth_")
    jpath = os.path.join(tmpdir, "scan.json")
    with io.open(jpath, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=1))

    if args.json:
        jout = os.path.abspath(os.path.expanduser(args.json))
        with io.open(jout, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, indent=1))
        print("json  -> %s" % jout)

    # 渲染 HTML
    out = args.out or os.path.join(os.getcwd(), "skill-worth-report.html")
    out = os.path.abspath(os.path.expanduser(out))
    try:
        p, kb, n = render_report(jpath, out)
    except Exception as e:
        print("error: render failed: %s" % e, file=sys.stderr)
        return 3

    # 终端摘要
    print()
    print("  %s  %d skills  |  %s" % (BANNER, t["count"], _bar(t)))
    print("  " + "-" * 46)
    for s in sorted(skills, key=lambda x: x["score"]):
        mark = {"skip": "x", "depends": "!", "worth": "."}[s["verdict"]]
        name = (s.get("slug") or s["name"])[:34]
        print("  %s %-34s %3d  %s" % (mark, name, s["score"],
                                      (s["reasons"][0] if s["reasons"] else "")[:40]))
    print()
    if t["skip"]:
        print("  -> %d skill(s) look empty: don't install them." % t["skip"])
    elif t["depends"]:
        print("  -> no empty skills; %d need judgment." % t["depends"])
    else:
        print("  -> all clear.")
    print("  report: %s  (%.0f KB)" % (p, kb))

    if args.open:
        try:
            webbrowser.open("file://" + p.replace("\\", "/"))
            print("  opened in browser")
        except Exception:
            pass

    # CI gate
    if args.fail_on == "skip" and t["skip"] > 0:
        print("  gate: %d skill(s) judged 'skip' -> failing" % t["skip"])
        return 1
    if args.fail_on == "depends" and (t["skip"] + t["depends"]) > 0:
        print("  gate: %d skill(s) below 'worth' -> failing" % (t["skip"] + t["depends"]))
        return 1
    return 0


def cmd_market(args):
    from . import market as market_mod
    return market_mod.run(top=args.top, min_installs=args.min_installs,
                          out=args.out)


def build_parser():
    ap = argparse.ArgumentParser(
        prog="skill-worth",
        description="Does this AI agent skill actually do what it claims? "
                    "Static analysis for skills that are safe but empty.",
    )
    ap.add_argument("-V", "--version", action="version", version="skill-worth %s" % __version__)
    sub = ap.add_subparsers(dest="cmd")

    c = sub.add_parser("check", help="evaluate a skill, or audit everything installed")
    c.add_argument("path", nargs="?", default=None,
                   help="path to one skill folder (omit to audit installed skills)")
    c.add_argument("--out", default=None, help="report path (default ./skill-worth-report.html)")
    c.add_argument("--json", default=None, help="also save raw JSON here")
    c.add_argument("--open", action="store_true", help="open the report when done")
    c.add_argument("--fail-on", choices=["never", "skip", "depends"], default="never",
                   help="exit non-zero when this verdict appears (for CI); default never")
    c.set_defaults(func=cmd_check)

    m = sub.add_parser("market", help="sample top marketplace skills")
    m.add_argument("--top", type=int, default=20, help="how many to sample (default 20)")
    m.add_argument("--min-installs", type=int, default=500,
                   help="only skills with at least this many installs (default 500)")
    m.add_argument("--out", default=None, help="save stats JSON here")
    m.set_defaults(func=cmd_market)
    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
