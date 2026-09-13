"""Render a scan as terminal text or a single self-contained HTML page."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from .scan import AMBIGUOUS, CRASH, PASS, SILENT_SUCCESS, Report

_LABEL = {
    PASS: "PASS",
    SILENT_SUCCESS: "SILENT SUCCESS",
    CRASH: "CRASH",
    AMBIGUOUS: "ambiguous",
}


def terminal(report: Report, verbose: bool = False) -> str:
    out: list[str] = []
    rate = f"{report.pass_rate * 100:.0f}%"
    out.append("")
    out.append(f"  {report.server}   grade {report.grade}   {rate} pass   {report.total_checks} checks")
    out.append("")

    for tool in report.tools:
        if tool.skipped:
            out.append(f"  {tool.name}  [skipped]  {tool.skipped}")
            continue
        if not tool.baseline_ok:
            out.append(f"  {tool.name}  [INCONCLUSIVE]  {tool.baseline_note}")
            continue
        counts: dict[str, int] = {}
        for finding in tool.findings:
            counts[finding.verdict] = counts.get(finding.verdict, 0) + 1
        summary = "  ".join(
            f"{_LABEL[v].lower()} {counts[v]}" for v in (PASS, SILENT_SUCCESS, CRASH, AMBIGUOUS) if v in counts
        )
        out.append(f"  {tool.name}  [{tool.pass_rate * 100:.0f}%]  {summary}")

        if not tool.baseline_ok:
            out.append(f"      ! baseline: {tool.baseline_note}")

        shown = tool.findings if verbose else tool.failures
        for finding in shown:
            if finding.verdict == PASS and not verbose:
                continue
            out.append(f"      {_LABEL[finding.verdict]:<15} {finding.field_path}: {finding.detail}")
            if finding.verdict in (SILENT_SUCCESS, CRASH):
                out.append(f"      {'':<15} sent {json.dumps(finding.payload)}")
                out.append(f"      {'':<15} got  {finding.response[:110]}")
        out.append("")

    if report.inconclusive:
        out.append(f"  {len(report.inconclusive)} tools inconclusive - "
                   "they rejected their own valid input, so nothing was graded")
    if report.failures:
        out.append(f"  {len(report.failures)} failing checks")
    elif report.gradable:
        out.append("  no failures")
    out.append("")
    return "\n".join(out)


_CSS = """
:root { color-scheme: light dark; --bg:#fbfaf9; --fg:#1a1a1a; --dim:#6b6b6b;
  --line:#e4e1dd; --card:#fff; --pass:#2f7d4f; --fail:#c0392b; --amb:#9a7b28; }
@media (prefers-color-scheme: dark) { :root { --bg:#16161a; --fg:#e8e6e3;
  --dim:#9a9a9a; --line:#2c2c33; --card:#1d1d22; --pass:#57b87f; --fail:#e57366; --amb:#d4ac52; } }
* { box-sizing:border-box }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.55 ui-sans-serif,system-ui,-apple-system,sans-serif; }
main { max-width:900px; margin:0 auto; padding:48px 24px 80px; }
h1 { font-size:24px; margin:0 0 4px; letter-spacing:-.01em }
.sub { color:var(--dim); font-size:13px; margin-bottom:32px }
.hero { display:flex; align-items:baseline; gap:16px; padding:20px 24px; background:var(--card);
  border:1px solid var(--line); border-radius:10px; margin-bottom:28px }
.grade { font-size:44px; font-weight:600; line-height:1 }
.grade.a,.grade.b { color:var(--pass) } .grade.c { color:var(--amb) }
.grade.d,.grade.f { color:var(--fail) }
.metrics { color:var(--dim); font-size:13px }
.metrics b { color:var(--fg); font-weight:600 }
h2 { font-size:15px; margin:28px 0 10px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace }
.bar { height:6px; border-radius:3px; background:var(--line); overflow:hidden; margin-bottom:14px }
.bar span { display:block; height:100% ; background:var(--pass) }
table { width:100%; border-collapse:collapse; font-size:13px }
th { text-align:left; font-weight:500; color:var(--dim); padding:6px 10px; border-bottom:1px solid var(--line) }
td { padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top }
tr.fail td { background:color-mix(in srgb, var(--fail) 7%, transparent) }
.v { font-weight:600; font-size:11px; letter-spacing:.04em; white-space:nowrap }
.v.pass { color:var(--pass) } .v.silent_success,.v.crash { color:var(--fail) } .v.ambiguous { color:var(--amb) }
code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px;
  background:var(--bg); padding:1px 5px; border-radius:4px; border:1px solid var(--line) }
.wrap { overflow-x:auto }
.empty { color:var(--pass); padding:10px 0 }
footer { margin-top:48px; color:var(--dim); font-size:12px; border-top:1px solid var(--line); padding-top:16px }
"""


def to_html(report: Report) -> str:
    e = html.escape
    rows: list[str] = []

    for tool in report.tools:
        rows.append(f"<h2>{e(tool.name)}</h2>")
        if tool.skipped:
            rows.append(f'<p class="v ambiguous">skipped - {e(tool.skipped)}</p>')
            continue
        if not tool.baseline_ok:
            rows.append(f'<p class="v crash">inconclusive - {e(tool.baseline_note)}</p>')
            continue
        rows.append(f'<div class="bar"><span style="width:{tool.pass_rate * 100:.0f}%"></span></div>')
        if not tool.baseline_ok:
            rows.append(f'<p class="v crash">baseline: {e(tool.baseline_note)}</p>')

        rows.append('<div class="wrap"><table><tr><th>verdict</th><th>field</th>'
                    "<th>violation</th><th>sent</th><th>response</th></tr>")
        for f in sorted(tool.findings, key=lambda f: (f.verdict == PASS, f.field_path)):
            cls = "fail" if f.failed else ""
            rows.append(
                f'<tr class="{cls}"><td class="v {f.verdict}">{_LABEL[f.verdict]}</td>'
                f"<td><code>{e(f.field_path)}</code></td><td>{e(f.detail)}</td>"
                f"<td><code>{e(json.dumps(f.payload))[:90]}</code></td>"
                f"<td>{e(f.response[:90])}</td></tr>"
            )
        rows.append("</table></div>")

    failures = len(report.failures)
    verdict_line = (
        f"<b>{failures}</b> failing checks" if failures else "<b>no failures</b>"
    )
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tempered — {e(report.server)}</title><style>{_CSS}</style></head>
<body><main>
<h1>Tempered</h1>
<p class="sub">conformance report — {e(report.server)}</p>
<div class="hero">
  <div class="grade {report.grade.lower()}">{report.grade}</div>
  <div class="metrics">
    <b>{report.pass_rate * 100:.0f}%</b> pass rate &nbsp;·&nbsp;
    <b>{report.total_checks}</b> adversarial checks &nbsp;·&nbsp;
    {verdict_line}
  </div>
</div>
{"".join(rows)}
<footer>Every payload violates exactly one declared constraint. Generated {stamp}.</footer>
</main></body></html>
"""


def to_json(report: Report) -> str:
    return json.dumps(
        {
            "server": report.server,
            "grade": report.grade,
            "pass_rate": round(report.pass_rate, 4),
            "total_checks": report.total_checks,
            "tools": [
                {
                    "name": t.name,
                    "pass_rate": round(t.pass_rate, 4),
                    "baseline_ok": t.baseline_ok,
                    "skipped": t.skipped,
                    "findings": [
                        {
                            "field": f.field_path,
                            "constraint": f.constraint,
                            "detail": f.detail,
                            "verdict": f.verdict,
                            "payload": f.payload,
                            "response": f.response,
                        }
                        for f in t.findings
                    ],
                }
                for t in report.tools
            ],
        },
        indent=2,
    )
