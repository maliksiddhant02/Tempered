"""Bounded repair loop: failing checks -> patch -> re-verify.

Two rules make this trustworthy rather than a slot machine:

1. **Bounded.** Two attempts, then the tool is marked failed and left failed.
   A loop that retries until something passes will eventually pass by accident.
2. **Re-run the FULL suite after every patch**, not just the failing checks.
   Fixing one constraint by loosening another is the obvious failure mode, and
   only a full re-run catches it.

The patched file is only kept if it actually scores better.
"""

from __future__ import annotations

import asyncio
import difflib
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .report import terminal
from .scan import Report, scan

MODEL = "claude-opus-5"
MAX_ATTEMPTS = 2

SYSTEM = """You repair MCP (Model Context Protocol) servers that fail conformance testing.

The server below declares a JSON Schema for each tool but does not enforce it. A
conformance harness sent payloads that violate the declared schema, and the server
accepted them and returned success. An agent calling this server would proceed on
invalid data with nothing raised anywhere.

Fix the HANDLER so it rejects input the declared schema forbids. Raise an exception
with a clear message - the MCP framework turns that into a proper tool error.

Rules:
- Do NOT loosen or edit the declared schema to match the buggy behaviour. The schema
  is the contract; the handler is what is wrong.
- Do NOT change tool names, signatures, or what valid calls return. Valid input must
  still succeed exactly as before.
- Validate every constraint the schema declares: types, required fields, enums,
  numeric bounds, string lengths, and formats.
- Remember that bool is a subclass of int in Python.

Return the COMPLETE corrected file in a single ```python code block. No commentary."""


class MissingCredentials(RuntimeError):
    """No Anthropic credentials. Never SystemExit - this runs inside a server too."""


def credentials_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


@dataclass
class Attempt:
    number: int
    diff: str
    report: Report
    kept: bool


@dataclass
class RepairResult:
    before: Report
    after: Report
    attempts: list[Attempt]
    source: Path

    @property
    def improved(self) -> bool:
        return self.after.pass_rate > self.before.pass_rate

    @property
    def fixed(self) -> bool:
        return not self.after.failures


def _prompt(source: str, report: Report) -> str:
    lines = [f"Server source ({len(source.splitlines())} lines):", "", "```python", source, "```", ""]
    lines.append(f"It scored {report.pass_rate * 100:.0f}% ({report.grade}). Failing checks:")
    lines.append("")
    for finding in report.failures[:40]:
        lines.append(f"- tool `{finding.tool}`, field `{finding.field_path}`: {finding.detail}")
        lines.append(f"    sent:     {finding.payload}")
        lines.append(f"    returned: {finding.response[:160]}")
        lines.append(f"    expected: rejection, got {finding.verdict.replace('_', ' ')}")
    return "\n".join(lines)


def _extract(text: str) -> str | None:
    blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    return blocks[-1].strip() + "\n" if blocks else None


def _patch(source: str, report: Report) -> str | None:
    """One model call. Returns corrected source, or None if it produced nothing."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": _prompt(source, report)}],
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    return _extract(text)


async def repair(
    source_path: Path, command: str, args: list[str], label: str, verbose: bool = True
) -> RepairResult:
    """Scan, patch, re-verify. At most MAX_ATTEMPTS patches, best result kept."""
    if not credentials_available():
        raise MissingCredentials(
            "repair needs ANTHROPIC_API_KEY (or an `ant auth login` profile)"
        )

    original = source_path.read_text(encoding="utf-8")
    before = await scan(command, args, label)
    best, best_source = before, original
    attempts: list[Attempt] = []

    for number in range(1, MAX_ATTEMPTS + 1):
        if not best.failures:
            break
        if verbose:
            print(f"  repair attempt {number}/{MAX_ATTEMPTS} — {len(best.failures)} failing checks")

        candidate = await asyncio.to_thread(_patch, best_source, best)
        if not candidate:
            if verbose:
                print("  no patch returned, stopping")
            break

        source_path.write_text(candidate, encoding="utf-8")
        # The whole suite, not just what failed: a fix that loosens another
        # constraint has to show up here.
        after = await scan(command, args, label)

        diff = "".join(
            difflib.unified_diff(
                best_source.splitlines(keepends=True),
                candidate.splitlines(keepends=True),
                fromfile=f"{source_path.name} (before)",
                tofile=f"{source_path.name} (attempt {number})",
            )
        )
        kept = after.pass_rate > best.pass_rate
        attempts.append(Attempt(number, diff, after, kept))

        if verbose:
            print(f"  -> {before.grade if number == 1 else best.grade} "
                  f"{best.pass_rate * 100:.0f}%  ->  {after.grade} {after.pass_rate * 100:.0f}%"
                  f"{'' if kept else '  (rejected, no improvement)'}")

        if kept:
            best, best_source = after, candidate
        else:
            source_path.write_text(best_source, encoding="utf-8")

    source_path.write_text(best_source, encoding="utf-8")
    return RepairResult(before=before, after=best, attempts=attempts, source=source_path)


def summary(result: RepairResult) -> str:
    out = [terminal(result.after)]
    out.append(
        f"  repair: {result.before.grade} {result.before.pass_rate * 100:.0f}%"
        f"  ->  {result.after.grade} {result.after.pass_rate * 100:.0f}%"
        f"   ({len(result.attempts)} attempt{'s' if len(result.attempts) != 1 else ''})"
    )
    if not result.fixed:
        out.append(f"  {len(result.after.failures)} checks still failing — left failed, not forced")
    return "\n".join(out)
