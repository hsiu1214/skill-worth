# -*- coding: utf-8 -*-
"""
skill-worth 扫描器
==================
回答一个问题：这个 skill 值不值得装？

两种模式：
  python scan.py --target <目录>     装之前，评估一个 skill
  python scan.py --all               装之后，盘点全部已安装的

输出：JSON（stdout）。交给 render.py 变成 HTML 报告。

设计原则：
  1. 只读，不修改任何被扫描的文件
  2. 每个结论都必须有证据（文件数、行数、具体行号）
  3. 区分「知识型」与「动手型」——知识型没有代码是正常的
"""
import os
import re
import io
import sys
import json
import argparse
from datetime import datetime

CODE_EXT = {".py", ".js", ".ts", ".mjs", ".cjs", ".sh", ".ps1", ".bat",
            ".cmd", ".go", ".rb", ".pl", ".lua", ".php", ".java", ".rs"}

# ---------- 空壳特征 ----------
TPL_WORDS = ["風險等級", "风险等级", "門禁檔位", "门禁档位", "技能類型", "技能类型",
             "Risk level", "risk_level"]
SELF_ADMIT_RE = re.compile(
    r"(本|此)\s*(技\s*能)[^。\n]{0,20}(自動|自动)落地生成"
    r"|操作(細|细)節[^。\n]{0,25}(接入|補全)"
    r"|(should|to)\s+be\s+(completed|filled)\s+(in|at)\s+runtime", re.I)

FAKE_TOOLS = ["web_fetch(", "read_image(", "write_file(",
              "run_command(", "browser_search(", "search_web("]
# 出现在这些词后面，说明是在「讨论」这个工具名，不是在用它
DISCUSS_RE = re.compile(r"例如|比如|如写|像是|不存在|实际|教你|所谓|这类|这种|写成|改成|或")


def fake_tool_hits(md):
    """找出真的在教调用不存在工具的写法，排除「举例说明」语境"""
    hits = []
    for w in FAKE_TOOLS:
        for m in re.finditer(re.escape(w), md):
            pre = md[max(0, m.start() - 22):m.start()]
            if DISCUSS_RE.search(pre):
                continue
            hits.append(w)
            break
    return hits


def tpl_hits(md):
    """只认「字段式」模板话：词后面紧跟冒号，如「风险等级：低」
    正文里讨论「风险等级」这几个字不算。"""
    return [w for w in TPL_WORDS if re.search(re.escape(w) + r"\s*[:：]", md)]

# 宣称要「动手做事」的词（配合无代码 = 空壳）
ACTION_WORDS = ["爬取", "抓取網頁", "抓取网页", "批量下載", "批量下载",
                "批次下載", "批次下载", "執行命令", "执行命令", "運行腳本",
                "运行脚本", "啟動服務", "启动服务", "定時抓", "定时抓",
                "自動抓取", "自动抓取", "調用API", "调用API", "發送請求", "发送请求",
                "run the script", "execute the script", "crawl", "scrape"]
ACTION_RES = [r"\d+\s*[個个]\s*引擎", r"\d+\s*engines?", r"\d+\s*(?:search\s+)?engines"]

# 知识型信号（有这些说明本来就不靠代码）
KNOWLEDGE_HINT = ["檢查清單", "检查清单", "checklist", "方法論", "方法论",
                  "評分標準", "评分标准", "rubric", "流程", "協議", "protocol",
                  "指南", "guide", "規範", "规范", "原則", "原则"]

NEG_RE = re.compile(r"不|勿|禁止|避免|不能|無法|无法|不要|防止|無需|无需|毋須|never|do not|don't")

RISK_PATTERNS = {
    "對外連線": [r"https?://[^\s\"'\)]+", r"\bfetch\s*\(", r"requests\.(get|post|put)",
                 r"urllib\.request", r"\baxios\b"],
    "刪除檔案": [r"rm\s+-rf", r"shutil\.rmtree", r"os\.remove\s*\(", r"os\.unlink\s*\(",
                 r"Remove-Item[^\n]{0,40}-Recurse", r"\.unlink\s*\(\s*\)"],
    "動態執行": [r"\beval\s*\(", r"\bexec\s*\(", r"__import__\s*\(", r"pickle\.loads"],
    "憑證硬編": [r"api[_-]?key\s*[=:]\s*[\"'][^\"']{8,}",
                 r"secret\s*[=:]\s*[\"'][^\"']{8,}",
                 r"password\s*[=:]\s*[\"'][^\"']{6,}"],
}

# SKILL.md 里提到的相对文件路径（用于查「说的文件到底在不在」）
REF_RE = re.compile(r"(?:^|[\s`'\"(（])((?:scripts|assets|references|hooks|templates)/[\w\-./]+\.\w{1,5})")


def read_text(path, limit=None):
    try:
        with io.open(path, encoding="utf-8", errors="replace") as f:
            return f.read() if limit is None else f.read(limit)
    except Exception:
        return ""


def load_json(path):
    if not os.path.isfile(path):
        return {}
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return {}


def sentences_of(md):
    return [s for s in re.split(r"[。；;！!？?\n]", md) if s.strip()]


def action_claims(md):
    """宣称要动手做的词，排除否定语境（按句判断）"""
    sents = sentences_of(md)
    hits = []
    for w in ACTION_WORDS:
        if w not in md:
            continue
        for s in sents:
            if w in s:
                if NEG_RE.search(s):
                    continue
                hits.append(w)
                break
    for pat in ACTION_RES:
        m = re.search(pat, md, re.I)
        if m:
            s = next((x for x in sents if m.group(0) in x), "")
            if not NEG_RE.search(s):
                hits.append(m.group(0).strip())
    return list(dict.fromkeys(hits))


def frontmatter(md):
    """取 --- 之间的字段（简单解析，不依赖 yaml）"""
    m = re.match(r"^\s*---\s*\n(.*?)\n---\s*\n", md, re.S)
    if not m:
        return {}
    out = {}
    cur = None
    for line in m.group(1).split("\n"):
        if re.match(r"^\s*[A-Za-z_][\w\-]*\s*:", line):
            k, _, v = line.partition(":")
            cur = k.strip()
            out[cur] = v.strip().strip("\"'")
        elif cur and line.strip():
            out[cur] = (out.get(cur, "") + " " + line.strip()).strip()
    return out


def trigger_count(fm, md):
    """粗估触发词数量：description 里逗号分隔 + SKILL.md 触发词段落"""
    d = fm.get("description") or ""
    n = 0
    seg = re.search(r"[Tt]riggers?\s*[:：](.{0,300})", d) or re.search(r"觸發詞[:：](.{0,300})", md) \
        or re.search(r"触发词[:：](.{0,300})", md)
    if seg:
        n = len([x for x in re.split(r"[,，、]", seg.group(1)) if x.strip()])
    return n


def placeholder_code(txt):
    """代码是否只是占位（有文件、没实现）"""
    stripped = re.sub(r"^\s*(#.*|//.*|\"\"\"[\s\S]*?\"\"\"|''')", "", txt, flags=re.M).strip()
    if len(stripped) < 60:
        return True
    if re.search(r"^\s*(pass|TODO|raise NotImplementedError|NotImplementedError)\s*$", txt, re.M):
        body = re.sub(r"^\s*(import .*|from .*|def .*|class .*|#.*)$", "", txt, flags=re.M).strip()
        if len(body) < 80:
            return True
    return False


def knowledge_density(md):
    """知识型 skill 的信息密度：有步骤、有清单、有示例、篇幅够"""
    d = 0
    if re.search(r"^\s*\d+[.、)]\s", md, re.M):
        d += 1
    if len(re.findall(r"^\s*[-*]\s+\S", md, re.M)) >= 3:
        d += 1
    if "```" in md:
        d += 1
    if len(md) > 2500:
        d += 1
    return d


def score_skill(md, real_code, code_lines, code_files, refs, missing,
                desc, tcount, risks, has_self_admit, claims, ft, tw, hard_shell):
    """五维加权评分，总分 100。返回 (score, 分维度 dict)"""
    dims = {}

    # 1) 实质功能 40 分
    if real_code:
        s = 40 if code_lines >= 50 else 32
        why = "有可运行代码 %d 行" % code_lines
    else:
        dens = knowledge_density(md)
        if dens >= 3:
            s, why = 26, "纯方法型，但步骤/清单/示例齐全"
        elif dens >= 1:
            s, why = 17, "纯方法型，内容偏薄"
        else:
            s, why = 8, "无代码、无方法、无示例"
    dims["substance"] = {"score": s, "max": 40, "why": why}

    # 2) 宣称一致 25 分
    s = 25
    if has_self_admit:
        s = 0
    if claims and not real_code:
        s = min(s, 3)
    if missing:
        s = max(0, s - 5 * len(missing))
    dims["consistency"] = {"score": s, "max": 25,
                           "why": "宣称与文件对得上" if s >= 20 else "宣称与内容有落差"}

    # 3) 说明清晰 15 分
    s = 15
    if len(desc) < 25:
        s -= 7
    if tcount > 20:
        s -= 5
    elif tcount == 0 and len(desc) < 40:
        s -= 4
    s = max(0, s)
    dims["clarity"] = {"score": s, "max": 15,
                       "why": "用途写得清" if s >= 12 else "用途说得含糊"}

    # 4) 安全 10 分
    s = 10
    cats = {r["type"] for r in risks}
    if "憑證硬編" in cats:
        s = 0
        why = "有硬编码密钥"
    elif cats & {"刪除檔案", "動態執行"}:
        s = 7
        why = "有删除或动态执行"
    elif cats:
        s = 8
        why = "有对外连线"
    else:
        why = "没发现风险操作"
    dims["safety"] = {"score": s, "max": 10, "why": why}

    # 5) 可维护 10 分
    s = 10
    if not re.search(r"(scripts|assets|references|hooks)/", " ".join(refs)) and code_files == 0:
        s -= 3
    if tw:
        s -= 2
    if ft:
        s -= 2  # 工具名可能只是宿主差异，轻扣即可
    s = max(0, s)
    dims["maintain"] = {"score": s, "max": 10,
                        "why": "结构完整" if s >= 8 else "结构松散"}

    total = sum(v["score"] for v in dims.values())
    return max(0, min(100, total)), dims
    """代码是否只是占位（无实际实现）"""
    stripped = re.sub(r"^\s*(#.*|//.*|\"\"\"[\s\S]*?\"\"\"|''')", "", txt, flags=re.M).strip()
    if len(stripped) < 60:
        return True
    if re.search(r"^\s*(pass|NotImplementedError|TODO|raise NotImplementedError)\s*$", txt, re.M):
        body = re.sub(r"^\s*(import .*|from .*|def .*|class .*|#.*)$", "", txt, flags=re.M).strip()
        if len(body) < 80:
            return True
    return False


def scan_one(d):
    name = os.path.basename(os.path.normpath(d))
    md_path = os.path.join(d, "SKILL.md")
    if not os.path.isfile(md_path):
        return None

    md = read_text(md_path)
    fm = frontmatter(md)

    code_files, all_files, code_lines = [], [], 0
    for dp, dn, fn in os.walk(d):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, d).replace("\\", "/")
            all_files.append(rel)
            if os.path.splitext(f)[1].lower() in CODE_EXT:
                t = read_text(p)
                code_files.append({"path": rel, "lines": t.count("\n") + 1,
                                   "placeholder": placeholder_code(t), "text": t})
                code_lines += t.count("\n") + 1

    hub = load_json(os.path.join(d, "_skillhub_meta.json"))
    meta = load_json(os.path.join(d, "_meta.json"))
    is_market = os.path.isfile(os.path.join(d, "_skillhub_meta.json")) or bool(meta.get("ownerId"))
    slug = hub.get("slug") or meta.get("slug") or name
    version = hub.get("version") or meta.get("version") or fm.get("version") or ""
    installs = hub.get("installs")
    ns = hub.get("namespace") or ""

    reasons, evidence, risks = [], [], []
    hard_shell = False

    real_code = [c for c in code_files if not c["placeholder"]]
    claims = action_claims(md) if not real_code else []
    tw = tpl_hits(md)
    ft = fake_tool_hits(md)
    has_self_admit = bool(SELF_ADMIT_RE.search(md))
    refs = set(REF_RE.findall(md))
    missing = [r for r in refs if not os.path.exists(os.path.join(d, r.replace("/", os.sep)))]
    desc = fm.get("description") or fm.get("description_zh") or ""
    tcount = trigger_count(fm, md)

    # 安全扫描（只扫代码）
    for c in code_files:
        for cat, pats in RISK_PATTERNS.items():
            for pat in pats:
                m = re.search(pat, c["text"])
                if m:
                    risks.append({"type": cat, "file": c["path"],
                                  "match": m.group(0)[:50]})
                    break

    # ---- 硬判：命中这些直接「别装」----
    if has_self_admit:
        hard_shell = True
        reasons.append("作者自己写明：操作细节还没实作")
    if claims and not real_code:
        hard_shell = True
        reasons.append("说要做「%s」，但一个代码文件都没有" % "、".join(claims[:3]))
    if code_files and not real_code:
        hard_shell = True
        reasons.append("有 %d 个代码文件，但都是占位，没有实际实现" % len(code_files))

    # 工具名是否「存在」取决于宿主环境（WorkBuddy 叫 WebFetch，别的宿主可能就叫
    # web_fetch），所以只作提示，不参与硬判——曾经把它当一票否决，跨平台会误杀。
    if ft:
        reasons.append("文件里写的工具名（%s）在部分宿主不存在，换环境时要自己确认"
                       % ft[0])

    score, dims = score_skill(md, real_code, code_lines, len(code_files), refs,
                              missing, desc, tcount, risks, has_self_admit,
                              claims, ft, tw, hard_shell)

    # 有硬伤的直接压到「不及格」区间，避免出现「56 分却判别装」的矛盾
    if hard_shell:
        score = min(39, int(score * 0.6))

    # ---- 人话理由（按重要性排）----
    if real_code:
        reasons.insert(0, "有 %d 个代码文件、共 %d 行，是真能跑的"
                       % (len(real_code), sum(c["lines"] for c in real_code)))
    elif not claims and not has_self_admit:
        dens = knowledge_density(md)
        if dens >= 3:
            reasons.insert(0, "没有代码，但步骤、清单、示例都写全了，靠文档本身起作用")
        else:
            reasons.insert(0, "没有代码，内容也比较精简——能不能帮上忙取决于你会不会照它做")
    if missing:
        reasons.append("提到 %d 个文件，其中 %d 个实际不存在" % (len(refs), len(missing)))
        evidence.append({"label": "找不到的文件", "value": "、".join(sorted(missing)[:5])})
    elif refs:
        reasons.append("文件里提到的 %d 个附件都在" % len(refs))
    if len(tw) >= 2:
        reasons.append("有 %d 处套模板的空话（%s）" % (len(tw), "、".join(tw[:3])))
    if len(desc) < 25:
        reasons.append("用途一句话说不清，描述太短")
    if tcount > 20:
        reasons.append("触发词 %d 个，容易在你没想用的时候被误触发" % tcount)
    if any(r["type"] == "憑證硬編" for r in risks):
        reasons.append("代码里有看起来像密钥的字符串")

    # ---- 证据 ----
    if is_market and ns.startswith("clawhub_"):
        evidence.append({"label": "来源", "value": "市集镜像同步（%s）" % ns})
    elif is_market:
        evidence.append({"label": "来源", "value": "市集安装"})
    else:
        evidence.append({"label": "来源", "value": "本地自建"})
    if version:
        evidence.append({"label": "版本", "value": version})
    if installs not in (None, ""):
        evidence.append({"label": "市集安装量", "value": str(installs)})
    evidence.append({"label": "文件", "value": "%d 个（代码 %d、共 %d 行）"
                     % (len(all_files), len(code_files), code_lines)})
    evidence.append({"label": "五维得分", "value": " / ".join(
        "%s %d" % (k, v["score"]) for k, v in dims.items())})

    # ---- 分档 ----
    if hard_shell or score < 40:
        verdict = "skip"
        headline = "别装——它做不了自己说的事"
    elif score < 70:
        verdict = "depends"
        if not code_files:
            headline = "看你要什么——它是份文档，不是工具"
        else:
            headline = "看你要什么——能用，但有短板"
    else:
        verdict = "worth"
        headline = "值得装——有实际功能，说得清做什么"

    return {
        "name": name, "slug": slug, "version": version,
        "source": "market" if is_market else "local",
        "namespace": ns, "installs": installs,
        "files": len(all_files), "codeFiles": len(code_files),
        "codeLines": code_lines,
        "score": score, "verdict": verdict, "headline": headline,
        "dims": dims,
        "description": (desc or "")[:180],
        "reasons": reasons, "evidence": evidence,
        "risks": risks, "missingRefs": sorted(missing),
        "dir": d,
    }


# 常见的 skill 存放位置（不限于某一个平台）
CANDIDATE_DIRS = [
    "~/.workbuddy/skills",
    "~/.claude/skills",
    "~/.codex/skills",
    "~/.codeium/windsurf/skills",
    "~/.cursor/skills",
    "~/.config/claude/skills",
    "~/.config/opencode/skills",
    "~/Library/Application Support/Claude/skills",
]


def discover_dirs():
    """找出现存的所有 skill 目录"""
    out = []
    seen = set()
    for c in CANDIDATE_DIRS:
        p = os.path.expanduser(c)
        rp = os.path.realpath(p)
        if os.path.isdir(p) and rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def build_payload(results, mode, label):
    totals = {
        "count": len(results),
        "worth": sum(1 for r in results if r["verdict"] == "worth"),
        "depends": sum(1 for r in results if r["verdict"] == "depends"),
        "skip": sum(1 for r in results if r["verdict"] == "skip"),
        "market": sum(1 for r in results if r["source"] == "market"),
        "local": sum(1 for r in results if r["source"] == "local"),
        "codeLines": sum(r["codeLines"] for r in results),
        "emptyCoded": sum(1 for r in results if r["codeFiles"] == 0),
    }
    return {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mode": mode,
        "skillsDir": label,
        "totals": totals,
        "skills": results,
    }


def scan_target(path):
    """评估单个 skill 目录，返回 payload；没有 SKILL.md 返回 None"""
    r = scan_one(path)
    if r is None:
        return None
    return build_payload([r], "target", path)


def scan_dirs(roots=None):
    """扫描一个或多个 skills 根目录，同名去重。返回 payload"""
    roots = roots or discover_dirs()
    seen, results = set(), []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for n in sorted(os.listdir(root)):
            d = os.path.join(root, n)
            if not os.path.isdir(d) or n.lower() in seen:
                continue
            r = scan_one(d)
            if r:
                seen.add(n.lower())
                results.append(r)
    return build_payload(results, "all", "、".join(roots)), roots


def main():
    ap = argparse.ArgumentParser(description="扫描 skill，判断值不值得装")
    ap.add_argument("--all", action="store_true", help="扫描全部已安装 skill")
    ap.add_argument("--target", default=None, help="只扫一个目录（装前评估）")
    ap.add_argument("--dir", default=None, help="指定 skills 根目录")
    ap.add_argument("--out", default=None, help="把 JSON 写到文件")
    args = ap.parse_args()

    if args.target:
        payload = scan_target(args.target)
        if payload is None:
            print(json.dumps({"error": "目录里没有 SKILL.md：%s" % args.target},
                             ensure_ascii=False))
            return 2
    else:
        payload, roots = scan_dirs([args.dir] if args.dir else None)
        if not roots:
            print(json.dumps({
                "error": "没找到 skill 目录，请用 --dir 指定",
                "searched": [os.path.expanduser(c) for c in CANDIDATE_DIRS],
            }, ensure_ascii=False))
            return 2

    text = json.dumps(payload, ensure_ascii=False, indent=1)
    if args.out:
        with io.open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print("OK -> %s（%d 个 skill）" % (args.out, len(payload["skills"])))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
