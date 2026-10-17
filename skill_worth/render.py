# -*- coding: utf-8 -*-
"""
把 scan 产出的 JSON 套进 HTML 模板，生成一份可以发给别人看的报告。

既可以命令行调用：
    python -m skill_worth.render scan.json out.html
也可以作为函数调用：
    from skill_worth.render import render
    render("scan.json", "out.html", market="market.json")
"""
import io
import os
import sys
import json
import argparse

TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "assets", "report-template.html")


def strip_private(payload):
    """移除不需要公开的字段，避免分享报告时暴露本机目录"""
    for s in payload.get("skills", []):
        s.pop("dir", None)        # 绝对路径
        s.pop("namespace", None)  # 内部命名空间
    p = payload.get("skillsDir")
    if p:
        segs = []
        for one in str(p).split("、"):
            ps = [x for x in one.replace("\\", "/").split("/") if x]
            segs.append("…/" + "/".join(ps[-2:]) if len(ps) >= 2 else (ps[0] if ps else ""))
        payload["skillsDir"] = "、".join(segs)
    return payload


def render(scan_path, out_path, market=None):
    """scan_path / market：JSON 文件路径；out_path：HTML 输出路径。
    返回 (输出路径, 大小KB, skill 数)"""
    if not os.path.isfile(scan_path):
        raise FileNotFoundError("找不到: %s" % scan_path)
    if not os.path.isfile(TPL):
        raise FileNotFoundError("找不到模板: %s" % TPL)

    with io.open(scan_path, encoding="utf-8") as f:
        payload = json.load(f)
    strip_private(payload)

    if market and os.path.isfile(market):
        with io.open(market, encoding="utf-8") as f:
            payload["market"] = json.load(f)

    tpl = io.open(TPL, encoding="utf-8").read()
    if "__REPORT_JSON__" not in tpl:
        raise ValueError("模板缺少 __REPORT_JSON__ 占位符")

    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    js = js.replace("</", "<\\/")
    html = tpl.replace("__REPORT_JSON__", js)

    d = os.path.dirname(os.path.abspath(out_path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with io.open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    kb = len(html.encode("utf-8")) / 1024.0
    return out_path, kb, len(payload.get("skills", []))


def main():
    ap = argparse.ArgumentParser(description="把扫描结果渲染成 HTML 报告")
    ap.add_argument("scan", help="scan 产出的 JSON")
    ap.add_argument("out", nargs="?", default=None, help="输出 HTML")
    ap.add_argument("--market", default=None, help="市集观察 JSON（可选）")
    args = ap.parse_args()

    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.scan)), "report.html")
    try:
        p, kb, n = render(args.scan, out, args.market)
    except Exception as e:
        print("失败：%s" % e)
        return 2
    extra = "，含市集观察" if args.market else ""
    print("OK -> %s（%.1f KB，%d 个 skill%s）" % (p, kb, n, extra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
