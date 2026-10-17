"""
skill-worth — does this AI agent skill actually do what it claims?

Static analysis for skills that are safe but empty: template filler,
unimplemented claims, dead file references.

    from skill_worth import scan_target, render_report
    payload = scan_target("./some-skill")
    print(payload["totals"])
"""

__version__ = "1.0.0"
__all__ = ["scan_target", "scan_dirs", "scan_one", "render_report", "run_market"]

from .scan import scan_target, scan_dirs, scan_one  # noqa: E402
from .render import render as render_report  # noqa: E402


def run_market(top=20, min_installs=500, out=None, keep=False):
    """抽样检查市集热门 skill（需要网络）"""
    from .market import run as _run
    return _run(top=top, min_installs=min_installs, out=out, keep=keep)
