"""Run the adversarial suite against a live server and classify what comes back.

The oracle: a conformant server, handed a payload that violates its own declared
schema, must reject it. Accepting it means the calling agent proceeds on garbage
with nothing raised anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import client, synth

# Verdicts
PASS = "pass"  # rejected the invalid payload, as it should
SILENT_SUCCESS = "silent_success"  # accepted it and returned success
CRASH = "crash"  # died or hung
AMBIGUOUS = "ambiguous"  # accepted it, but the spec does not clearly forbid that

FAILING = (SILENT_SUCCESS, CRASH)

# Constraints where accepting the payload is defensible rather than wrong.
# Kept deliberately narrow: every entry here is a finding we choose NOT to score,
# and a harness that flags correct servers is worse than no harness.
_AMBIGUOUS_WHEN_ACCEPTED = {
    # JSON-RPC clients stringify numbers often enough that coercing "5" -> 5 is
    # a reasonable server behaviour rather than a bug.
    ("type", "string numeral"),
    # The MCP spec does not require servers to reject unknown properties.
    ("additionalProperties", ""),
}


def _is_ambiguous(violation: synth.Violation) -> bool:
    return any(
        violation.constraint == constraint and marker in violation.detail
        for constraint, marker in _AMBIGUOUS_WHEN_ACCEPTED
    )


@dataclass
class Finding:
    tool: str
    field_path: str
    constraint: str
    detail: str
    payload: dict[str, Any]
    verdict: str
    response: str

    @property
    def failed(self) -> bool:
        return self.verdict in FAILING


@dataclass
class ToolReport:
    name: str
    description: str
    baseline_ok: bool
    baseline_note: str
    findings: list[Finding] = field(default_factory=list)
    skipped: str = ""  # non-empty when the tool was not called at all

    @property
    def total(self) -> int:
        return len(self.findings)

    @property
    def passed(self) -> int:
        return sum(1 for f in self.findings if f.verdict == PASS)

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if f.failed]

    @property
    def pass_rate(self) -> float:
        scored = [f for f in self.findings if f.verdict != AMBIGUOUS]
        if not scored:
            return 1.0
        return sum(1 for f in scored if f.verdict == PASS) / len(scored)

    @property
    def scanned(self) -> bool:
        """Did this tool produce a result worth grading?

        A tool that rejects its own valid example is not being strict, it is
        broken or unreachable — and it would otherwise score 100% for rejecting
        everything we sent. Refusing to grade it is the honest answer.
        """
        return not self.skipped and self.baseline_ok


@dataclass
class Report:
    server: str
    tools: list[ToolReport] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        rates = [t.pass_rate for t in self.tools if t.scanned]
        return sum(rates) / len(rates) if rates else 1.0

    @property
    def skipped(self) -> list[ToolReport]:
        return [t for t in self.tools if not t.scanned]

    @property
    def gradable(self) -> bool:
        return any(t.scanned for t in self.tools)

    @property
    def grade(self) -> str:
        return grade_for(self.pass_rate) if self.gradable else "?"

    @property
    def inconclusive(self) -> list[ToolReport]:
        return [t for t in self.tools if not t.skipped and not t.baseline_ok]

    @property
    def failures(self) -> list[Finding]:
        return [f for t in self.tools for f in t.failures]

    @property
    def total_checks(self) -> int:
        return sum(t.total for t in self.tools)


_BANDS = ((0.95, "A"), (0.85, "B"), (0.70, "C"), (0.50, "D"))


def grade_for(rate: float) -> str:
    for threshold, letter in _BANDS:
        if rate >= threshold:
            return letter
    return "F"


def meets(grade: str, minimum: str) -> bool:
    order = "ABCDF"
    return order.index(grade) <= order.index(minimum)


async def scan_tool(server: client.Server, tool: client.ToolInfo) -> ToolReport:
    """Every single-constraint violation of one tool's schema, called for real."""
    report = ToolReport(
        name=tool.name, description=tool.description, baseline_ok=True, baseline_note=""
    )

    # Sanity first: if the server rejects its own valid example, every result
    # below is meaningless.
    baseline = synth.example(tool.input_schema)
    if isinstance(baseline, dict):
        outcome = await server.call(tool.name, baseline)
        if outcome.kind != client.OK:
            report.baseline_ok = False
            report.baseline_note = f"valid input was not accepted: {outcome.text}"
            # Nothing below this point can be trusted, so do not spend the calls.
            return report

    for violation in synth.synthesize(tool.input_schema):
        outcome = await server.call(tool.name, violation.payload)
        if outcome.kind == client.CRASH:
            verdict = CRASH
        elif outcome.rejected:
            verdict = PASS
        elif _is_ambiguous(violation):
            verdict = AMBIGUOUS
        else:
            verdict = SILENT_SUCCESS

        report.findings.append(
            Finding(
                tool=tool.name,
                field_path=violation.field,
                constraint=violation.constraint,
                detail=violation.detail,
                payload=violation.payload,
                verdict=verdict,
                response=outcome.text,
            )
        )
    return report


async def scan(
    command: str,
    args: list[str],
    label: str,
    methods: dict[str, str] | None = None,
    allow_writes: bool = False,
) -> Report:
    """Spawn a server and scan every tool it exposes.

    Adversarial payloads are never sent to a tool known to mutate state unless
    `allow_writes` says so. `methods` is the tool -> HTTP method manifest written
    beside a generated server; without it every tool is scanned, because a
    hand-written server gives us nothing to be careful with.
    """
    from .generate import READ_ONLY_METHODS

    methods = methods or {}
    report = Report(server=label)

    async with client.connect(command, args) as server:
        for tool in await server.tools():
            method = methods.get(tool.name, "")
            if method and method not in READ_ONLY_METHODS and not allow_writes:
                report.tools.append(
                    ToolReport(
                        name=tool.name,
                        description=tool.description,
                        baseline_ok=True,
                        baseline_note="",
                        skipped=f"{method.upper()} tool - not called (pass --allow-writes)",
                    )
                )
                continue
            report.tools.append(await scan_tool(server, tool))
    return report
