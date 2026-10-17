# -*- coding: utf-8 -*-
"""
市集观察：抽样检查 SkillHub 上热门 skill 的「空壳比例」
=====================================================
用途：给报告提供一节有传播力的数据 —— 热度最高的那批 skill 里，
      有多少是装上去其实不干事的。

做法：拉 TOP N → 下载 → 解压 → 用同一套 scan_one 判定 → 统计。
      全程在系统临时目录作业，跑完自动清理。

用法：
  python market.py --top 20              # 试跑，看能不能跑通
  python market.py --top 50 --out m.json # 正式，输出统计 JSON
  python market.py --top 20 --keep       # 保留下载的包（调试用）

注意：市集上部分包的存储端会返回 NoSuchKey（有版本号没文件），
      这类计入 failed，不影响统计。
"""
import os
import io
import sys
import json
import shutil
import zipfile
import tempfile
import argparse
import subprocess
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scan import scan_one  # 复用同一套判定，保证口径一致

API_TOP = "https://lightmake.site/api/skills/top"
API_CAT = "https://lightmake.site/api/skills?category=%s&sortBy=score&order=desc"
API_DL = "https://lightmake.site/api/v1/download?slug=%s"

CATEGORIES = ["office-efficiency", "data-analysis", "dev-programming",
              "content-creation", "business-ops", "knowledge-management",
              "it-ops-security", "professional", "education",
              "design-media", "ai-agent"]


def http_get(url, timeout=40):
    r = subprocess.run(["curl", "-s", "-L", "--max-time", str(timeout), url],
                       capture_output=True, timeout=timeout + 15)
    return r.stdout


def http_to_file(url, path, timeout=90):
    r = subprocess.run(["curl", "-s", "-L", "--max-time", str(timeout),
                        "-o", path, url], capture_output=True, timeout=timeout + 20)
    return os.path.isfile(path) and os.path.getsize(path) > 100


def parse_items(raw):
    try:
        d = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return []
    data = d.get("data") or {}
    return data.get("skills") or []


def fetch_top(limit=50):
    return parse_items(http_get(API_TOP))[:limit]


def fetch_pool(verbose=True):
    """合并总榜 + 各类目榜，按 slug 去重（同 slug 取安装量最高的那条）"""
    pool = {}

    def add(items, tag):
        n = 0
        for it in items:
            slug = it.get("slug") or ""
            if not slug:
                continue
            ins = it.get("installs") or 0
            if slug not in pool or ins > (pool[slug].get("installs") or 0):
                pool[slug] = it
                n += 1
        if verbose:
            print("   %-22s +%d" % (tag, n))

    if verbose:
        print("取数中：")
    add(fetch_top(50), "总榜 TOP50")
    for c in CATEGORIES:
        add(parse_items(http_get(API_CAT % c)), c)
    return list(pool.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20, help="抽样前 N 个（按榜单顺序）")
    ap.add_argument("--min-installs", type=int, default=1000,
                    help="只看安装量不低于此值的（0 表示不过滤）")
    ap.add_argument("--out", default=None, help="统计结果写到文件")
    ap.add_argument("--keep", action="store_true", help="保留下载的包")
    args = ap.parse_args()

    items = fetch_pool()
    if not items:
        print("拿不到市集榜单，可能网络问题")
        return 2

    # 只看真实有人在用的，按安装量降序
    items.sort(key=lambda x: -(x.get("installs") or 0))
    picked = []
    for it in items:
        ins = it.get("installs") or 0
        if args.min_installs and ins < args.min_installs:
            continue
        picked.append(it)
        if len(picked) >= args.top:
            break

    print("池子共 %d 个，按条件筛出 %d 个（安装量 ≥ %s）"
          % (len(items), len(picked), args.min_installs))
    if not picked:
        print("没有符合条件的 skill。试试调低 --min-installs")
        return 2

    work = tempfile.mkdtemp(prefix="skillworth_market_")
    results, failed = [], []

    for i, it in enumerate(picked, 1):
        slug = it.get("slug") or ""
        name = it.get("name") or slug
        ins = it.get("installs") or 0
        zpath = os.path.join(work, "%02d.zip" % i)
        ddir = os.path.join(work, "%02d_%s" % (i, slug[:40]))

        ok = False
        try:
            if http_to_file(API_DL % slug, zpath):
                with zipfile.ZipFile(zpath) as z:
                    names = z.namelist()
                    # 有的包把内容放在顶层子目录里
                    top_dirs = {n.split("/")[0] for n in names if "/" in n}
                    has_root_md = any(n.upper() == "SKILL.MD" for n in names)
                    target = ddir
                    z.extractall(ddir)
                    if not has_root_md and len(top_dirs) == 1:
                        cand = os.path.join(ddir, list(top_dirs)[0])
                        if os.path.isfile(os.path.join(cand, "SKILL.md")):
                            target = cand
                    r = scan_one(target)
                    if r:
                        r["installs"] = ins
                        r["marketName"] = name
                        ns = (it.get("namespace") or {})
                        r["canonicalName"] = ns.get("canonicalName") or ""
                        results.append(r)
                        ok = True
        except Exception as e:
            failed.append({"slug": slug, "why": type(e).__name__})

        if not ok and not any(f["slug"] == slug for f in failed):
            failed.append({"slug": slug, "why": "下载或解压失败"})

        flag = "空壳" if (ok and results[-1]["verdict"] == "skip") else ("OK" if ok else "跳过")
        print("  %2d/%-2d %-30s 安装:%-8s %s" % (i, len(picked), slug[:30], ins, flag))

    # 统计
    skips = [r for r in results if r["verdict"] == "skip"]
    depends = [r for r in results if r["verdict"] == "depends"]
    worth = [r for r in results if r["verdict"] == "worth"]

    stat = {
        "sampledAt": datetime.now().strftime("%Y-%m-%d"),
        "requested": len(picked),
        "scanned": len(results),
        "failed": len(failed),
        "worth": len(worth),
        "depends": len(depends),
        "skip": len(skips),
        "skipInstalls": sum(r.get("installs") or 0 for r in skips),
        "totalInstalls": sum(r.get("installs") or 0 for r in results),
        "skipList": [{
            "name": r.get("marketName") or r["name"],
            "installs": r.get("installs") or 0,
            "score": r["score"],
            "canonicalName": r.get("canonicalName") or "",
            "why": (r["reasons"][0] if r["reasons"] else ""),
        } for r in sorted(skips, key=lambda x: -(x.get("installs") or 0))],
        "failedList": failed[:10],
    }

    print()
    print("=" * 60)
    print("抽样 %d 个（成功扫到 %d 个，%d 个下载失败）"
          % (stat["requested"], stat["scanned"], stat["failed"]))
    print("值得装 %d ／ 看你要什么 %d ／ 别装 %d"
          % (stat["worth"], stat["depends"], stat["skip"]))
    if stat["scanned"]:
        pct = stat["skip"] * 100.0 / stat["scanned"]
        print("空壳比例：%.0f%%（这批合计安装 %s 次，其中空壳占 %s 次）"
              % (pct, f'{stat["totalInstalls"]:,}', f'{stat["skipInstalls"]:,}'))

    if args.out:
        with io.open(args.out, "w", encoding="utf-8") as f:
            f.write(json.dumps(stat, ensure_ascii=False, indent=1))
        print("OK -> %s" % args.out)

    if args.keep:
        print("下载的包保留在: %s" % work)
    else:
        shutil.rmtree(work, ignore_errors=True)
        print("临时目录已清理")

    return 0


if __name__ == "__main__":
    sys.exit(main())
