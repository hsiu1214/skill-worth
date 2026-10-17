# -*- coding: utf-8 -*-
"""用最小样本验证判定的三条底线：
   1. 说要做某事却零代码 → skip
   2. 作者自承未实作     → skip
   3. 有真能跑的代码     → worth
   4. 纯文档但步骤齐全   → 不该因为「没有代码」被判死
"""
import os
import io
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill_worth.scan import scan_one  # noqa: E402


class SkillWorthTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sw_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make(self, name, skill_md, files=None):
        d = os.path.join(self.tmp, name)
        os.makedirs(d, exist_ok=True)
        with io.open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(skill_md)
        for rel, content in (files or {}).items():
            p = os.path.join(d, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with io.open(p, "w", encoding="utf-8") as f:
                f.write(content)
        return d

    def test_empty_claim_is_skip(self):
        """宣称要爬取/批量处理，却没有任何代码"""
        d = self._make("empty-claim", """---
name: empty-claim
description: "Crawls 16 search engines and merges results into one list for you."
version: "1.0.0"
---

# Empty Claim

This skill crawls 16 search engines, downloads every result page and merges them.
""")
        r = scan_one(d)
        self.assertEqual(r["verdict"], "skip", r["reasons"])

    def test_self_admitted_scaffold_is_skip(self):
        """作者自己写着实作待补"""
        d = self._make("scaffold", """---
name: scaffold
description: "智能摘要工具，支持网页、PDF、Word、TXT 的内容提取与要点归纳。"
version: "1.0.0"
---

# 智能摘要

> 风险等级：低
> 门禁档位：L0
> 技能类型：摘要

本技能由规划规格 README 自动落地生成，操作细节应在接入真实运行时代补全。
""")
        r = scan_one(d)
        self.assertEqual(r["verdict"], "skip", r["reasons"])

    def test_real_code_is_worth(self):
        """有能跑的代码"""
        d = self._make("with-code", """---
name: with-code
description: "Counts lines in a directory and prints a summary table."
version: "1.0.0"
---

# With Code

Run `python scripts/count.py <dir>` to count lines.
""", {
            "scripts/count.py": "import sys, os\n\n\ndef count(root):\n"
                                "    total = 0\n"
                                "    for dp, dn, fn in os.walk(root):\n"
                                "        for f in fn:\n"
                                "            try:\n"
                                "                total += sum(1 for _ in open(os.path.join(dp, f)))\n"
                                "            except OSError:\n"
                                "                pass\n"
                                "    return total\n\n\n"
                                "if __name__ == '__main__':\n"
                                "    print(count(sys.argv[1]))\n",
        })
        r = scan_one(d)
        self.assertEqual(r["verdict"], "worth", r["reasons"])
        self.assertGreaterEqual(r["score"], 70)

    def test_prose_protocol_not_killed_for_no_code(self):
        """纯文档但步骤/清单/示例齐全——不该被判死"""
        body = ["---", "name: protocol",
                'description: "A four-step review protocol for third-party skills, '
                'with checklists and worked examples."',
                'version: "1.0.0"', "---", "", "# Protocol", "", "## Steps", ""]
        body += ["%d. Check item number %d and record the finding." % (i, i) for i in range(1, 7)]
        body += ["", "## Checklist", ""]
        body += ["- verify the source namespace", "- read SKILL.md end to end",
                 "- confirm referenced files exist", "- classify the risk"]
        body += ["", "```bash", "grep -rn 'http' ./skill", "```", ""]
        body += ["## Notes", ""] + ["This paragraph adds context so the document "
                                    "reaches a useful length and is not trivially short. "] * 12
        d = self._make("protocol", "\n".join(body))
        r = scan_one(d)
        self.assertNotEqual(r["verdict"], "skip",
                            "a complete prose protocol must not be rejected: %s" % r["reasons"])


    def test_host_specific_tool_name_not_fatal(self):
        """工具名与宿主不一致，不该单独判死

        WorkBuddy 的抓取工具叫 WebFetch，别的宿主可能就叫 web_fetch。
        同一份文档换个环境跑就应该还是好的——所以这条只能是提示。
        """
        body = ["---", "name: host-tools",
                'description: "A review checklist for web content, with worked '
                'examples showing how to fetch and read a page."',
                'version: "1.0.0"', "---", "", "# Host tools", "",
                "## Steps", ""]
        body += ["%d. Fetch the page, then check item %d against the checklist." % (i, i)
                 for i in range(1, 6)]
        body += ["", "## Checklist", "",
                 "- confirm the page actually loaded", "- check the publish date",
                 "- look for the original source", "- note any claims without evidence"]
        body += ["", "```python", "web_fetch(url)", "```", ""]
        body += ["## Notes", ""] + [
            "This paragraph adds enough context for the document to be useful "
            "rather than a stub, and is deliberately not short. "] * 12
        d = self._make("host-tools", "\n".join(body))
        r = scan_one(d)
        self.assertNotEqual(r["verdict"], "skip",
                            "a host-specific tool name must not be fatal: %s" % r["reasons"])
        # 但仍应被提示出来
        self.assertTrue(any("工具名" in x for x in r["reasons"]),
                        "should still surface the tool-name note: %s" % r["reasons"])


if __name__ == "__main__":
    unittest.main()
