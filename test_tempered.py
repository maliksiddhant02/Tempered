"""End-to-end check: the harness must pass the good server and fail the broken one.

Both fixtures declare the identical schema, so any difference in verdict comes
from enforcement alone. This is the false-positive control from architecture.md —
if it ever goes green on broken_server or red on good_server, the harness is lying.

Run: python test_tempered.py
"""

import asyncio
import sys
from pathlib import Path

from tempered import synth
from tempered.scan import PASS, SILENT_SUCCESS, grade_for, meets, scan

PYTHON = sys.executable
ROOT = Path(__file__).parent


def check_synth() -> None:
    schema = {
        "type": "object",
        "required": ["n"],
        "properties": {
            "n": {"type": "integer", "minimum": 1, "maximum": 10},
            "s": {"type": "string", "enum": ["a", "b"]},
        },
    }
    baseline = synth.example(schema)
    assert baseline == {"n": 5, "s": "a"}, baseline

    violations = synth.synthesize(schema)
    assert violations, "no violations generated"

    # The load-bearing rule: exactly one field differs from the valid baseline.
    for v in violations:
        differing = [
            k for k in set(baseline) | set(v.payload)
            if baseline.get(k, object()) != v.payload.get(k, object())
        ]
        assert len(differing) == 1, f"{v} changed {differing}"

    constraints = {v.constraint for v in violations}
    for expected in ("type", "required", "enum", "minimum", "maximum"):
        assert expected in constraints, f"missing {expected}"
    print(f"  synth            {len(violations)} violations, one mutation each")


def check_grading() -> None:
    assert grade_for(1.0) == "A" and grade_for(0.0) == "F"
    assert grade_for(0.86) == "B" and grade_for(0.5) == "D"
    assert meets("A", "B") and not meets("C", "B")
    print("  grading          bands and thresholds")


async def check_fixtures() -> None:
    good = await scan(PYTHON, [str(ROOT / "fixtures" / "good_server.py")], "good")
    assert good.gradable, "good server produced nothing gradable"
    assert not good.failures, f"good server flagged {len(good.failures)} false positives"
    assert good.grade == "A", good.grade
    print(f"  good_server      {good.grade} {good.pass_rate:.0%} over {good.total_checks} checks")

    broken = await scan(PYTHON, [str(ROOT / "fixtures" / "broken_server.py")], "broken")
    assert broken.gradable, "broken server produced nothing gradable"
    assert broken.grade == "F", broken.grade
    silent = [f for f in broken.failures if f.verdict == SILENT_SUCCESS]
    assert len(silent) > 10, f"only {len(silent)} silent successes detected"
    print(f"  broken_server    {broken.grade} {broken.pass_rate:.0%}, "
          f"{len(silent)} silent successes caught")

    # Same declared contract, opposite outcome. That difference is the product.
    assert good.total_checks == broken.total_checks, "fixtures drifted apart"
    print(f"  control          identical {good.total_checks}-check contract, opposite verdicts")


async def check_write_safety() -> None:
    """A tool known to mutate state must not be called without --allow-writes."""
    fixture = str(ROOT / "fixtures" / "broken_server.py")
    guarded = await scan(PYTHON, [fixture], "guarded", methods={"create_charge": "post"})
    assert guarded.skipped, "POST tool was not skipped"
    assert guarded.total_checks == 0, "adversarial payloads were sent to a POST tool"
    assert not guarded.gradable and guarded.grade == "?", guarded.grade

    allowed = await scan(
        PYTHON, [fixture], "allowed", methods={"create_charge": "post"}, allow_writes=True
    )
    assert allowed.total_checks > 0, "--allow-writes did not re-enable the tool"
    print("  write safety     POST skipped by default, scanned with --allow-writes")


def main() -> int:
    print("tempered self-check")
    check_synth()
    check_grading()
    asyncio.run(check_fixtures())
    asyncio.run(check_write_safety())
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
