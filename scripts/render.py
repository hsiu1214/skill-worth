# -*- coding: utf-8 -*-
"""
skill-worth 报告渲染器
======================
把 scan.py 产出的 JSON 套进 HTML 模板，生成一份可以发给别人看的报告。

用法：
  python render.py scan.json                      -> report.html
  python render.py scan.json out.html
  python render.py scan.json out.html --market market.json   # 附加市集观察

输出前会剥掉本机绝对路径，避免分享报告时暴露目录结构。
"""
import io
import os
import sys
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(os.path.dirname(HERE), "assets", "report-template.html")


def strip_private(payload):
    """移除不需要公开的字段，避免分享报告时暴露本机目录"""
    for s in payload.get("skills", []):
        s.pop("dir", None)        # 绝对路径
        s.pop("namespace", None)  # 内部命名空间
    # 只留路径末两段
    p = payload.get("skillsDir")
    if p:
        parts = [x for x in str(p).replace("\\", "/").split("/") if x]
        payload["skillsDir"] = "…/" + "/".join(parts[-2:]) if len(parts) >= 2 else parts[0]
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scan", help="scan.py 产出的 JSON")
    ap.add_argument("out", nargs="?", default=None, help="输出 HTML")
    ap.add_argument("--market", default=None, help="市集观察 JSON（可选）")
    args = ap.parse_args()

    out = args.out or os.path.join(os.path.dirname(args.scan), "report.html")

    if not os.path.isfile(args.scan):
        print("找不到: %s" % args.scan)
        return 2
    if not os.path.isfile(TPL):
        print("找不到模板: %s" % TPL)
        return 2

    with io.open(args.scan, encoding="utf-8") as f:
        payload = json.load(f)
    strip_private(payload)

    # 市集观察（可选）
    if args.market and os.path.isfile(args.market):
        with io.open(args.market, encoding="utf-8") as f:
            payload["market"] = json.load(f)

    tpl = io.open(TPL, encoding="utf-8").read()
    if "__REPORT_JSON__" not in tpl:
        print("模板缺少 __REPORT_JSON__ 占位符")
        return 3

    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    js = js.replace("</", "<\\/")

    html = tpl.replace("__REPORT_JSON__", js)
    with io.open(out, "w", encoding="utf-8") as f:
        f.write(html)

    kb = len(html.encode("utf-8")) / 1024.0
    extra = "，含市集观察" if payload.get("market") else ""
    print("OK -> %s（%.1f KB，%d 个 skill%s）"
          % (out, kb, len(payload.get("skills", [])), extra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
