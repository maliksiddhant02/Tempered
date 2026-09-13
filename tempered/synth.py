"""Schema-directed adversarial payload synthesis.

Given a tool's JSON Schema, emit payloads that each violate EXACTLY ONE
constraint while leaving everything else valid. One violation per payload is
load-bearing: two violations make a failure unattributable, and unattributable
failures cannot be repaired automatically.

Pure stdlib, no I/O. Everything here is deterministic.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterator

# Sentinel: this field should be removed from the payload entirely.
OMIT = object()


@dataclass(frozen=True)
class Violation:
    """One adversarial payload and what makes it invalid."""

    path: tuple[str, ...]  # ("customer", "email") -> nested field
    constraint: str  # "type", "required", "enum", "minimum", ...
    detail: str  # human-readable: what we did and why it's wrong
    payload: dict[str, Any]  # the complete request body to send

    @property
    def field(self) -> str:
        return ".".join(self.path) or "<root>"

    def __str__(self) -> str:
        return f"{self.field}: {self.detail}"


# --------------------------------------------------------------------------
# Valid baseline
# --------------------------------------------------------------------------

_FORMAT_EXAMPLES = {
    "email": "user@example.com",
    "uri": "https://example.com",
    "url": "https://example.com",
    "date-time": "2026-01-01T00:00:00Z",
    "date": "2026-01-01",
    "uuid": "00000000-0000-4000-8000-000000000000",
}


def example(schema: dict[str, Any]) -> Any:
    """A minimal *valid* instance of `schema`.

    Every property is populated, not just the required ones, so that any field
    can be mutated in isolation later.
    """
    if "default" in schema:
        return schema["default"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]

    type_ = schema.get("type")
    if isinstance(type_, list):  # union type: take the first concrete one
        type_ = next((t for t in type_ if t != "null"), type_[0])

    if type_ == "object" or "properties" in schema:
        return {
            name: example(sub)
            for name, sub in schema.get("properties", {}).items()
        }
    if type_ == "array":
        items = schema.get("items")
        min_items = schema.get("minItems", 0)
        if not isinstance(items, dict):
            return [] if min_items == 0 else [None] * min_items
        return [example(items)] * max(min_items, 1)
    if type_ == "integer":
        return _in_range(schema, 1)
    if type_ == "number":
        return float(_in_range(schema, 1))
    if type_ == "boolean":
        return True
    if type_ == "null":
        return None

    # string, or untyped: honour format and length bounds
    if fmt := schema.get("format"):
        if fmt in _FORMAT_EXAMPLES:
            return _FORMAT_EXAMPLES[fmt]
    text = "x" * max(schema.get("minLength", 1), 1)
    if (cap := schema.get("maxLength")) is not None:
        text = text[:cap]
    return text


def _in_range(schema: dict[str, Any], fallback: int) -> int:
    low, high = schema.get("minimum"), schema.get("maximum")
    if low is not None and high is not None:
        return int((low + high) // 2)
    if low is not None:
        return int(low)
    if high is not None:
        return int(high)
    return fallback


# --------------------------------------------------------------------------
# Violations per constraint
# --------------------------------------------------------------------------


def _bad_values(schema: dict[str, Any]) -> Iterator[tuple[str, str, Any]]:
    """Yield (constraint, detail, value) that violate `schema` on its own."""
    type_ = schema.get("type")
    if isinstance(type_, list):
        type_ = next((t for t in type_ if t != "null"), None)

    # --- type -------------------------------------------------------------
    wrong_type = {
        "string": [("integer instead of string", 12345), ("array instead of string", [])],
        "integer": [('string numeral "5" instead of integer', "5"), ("float instead of integer", 1.5)],
        "number": [('string "1.5" instead of number', "1.5"), ("object instead of number", {})],
        "boolean": [('string "true" instead of boolean', "true"), ("integer instead of boolean", 1)],
        "array": [("string instead of array", "not-an-array"), ("object instead of array", {})],
        "object": [("string instead of object", "not-an-object"), ("array instead of object", [])],
    }
    for detail, value in wrong_type.get(type_, []):
        yield "type", detail, value
    if type_ and type_ != "null":
        yield "type", "null for a non-nullable field", None

    # --- enum -------------------------------------------------------------
    if options := schema.get("enum"):
        yield "enum", f"value outside enum {options!r}", "__not_in_enum__"

    # --- numeric bounds ---------------------------------------------------
    if (low := schema.get("minimum")) is not None:
        yield "minimum", f"below minimum {low}", low - 1
    if (high := schema.get("maximum")) is not None:
        yield "maximum", f"above maximum {high}", high + 1

    # --- string length ----------------------------------------------------
    if schema.get("minLength", 0) > 0:
        yield "minLength", f"empty string, minLength is {schema['minLength']}", ""
    if (cap := schema.get("maxLength")) is not None:
        yield "maxLength", f"string longer than maxLength {cap}", "x" * (cap + 1)

    # --- format -----------------------------------------------------------
    if (fmt := schema.get("format")) in _FORMAT_EXAMPLES:
        yield "format", f"malformed {fmt}", "not-a-valid-" + fmt

    # --- array items ------------------------------------------------------
    if type_ == "array" and isinstance(schema.get("items"), dict):
        item_type = schema["items"].get("type")
        if item_type in ("string", "integer", "number", "object"):
            bad = {"string": 123, "integer": "x", "number": "x", "object": "x"}[item_type]
            yield "items", f"array element of the wrong type ({item_type} expected)", [bad]


# --------------------------------------------------------------------------
# Payload assembly
# --------------------------------------------------------------------------


def _set(payload: dict, path: tuple[str, ...], value: Any) -> dict:
    """Copy `payload` with `path` set to `value`, or removed if value is OMIT."""
    out = copy.deepcopy(payload)
    cursor = out
    for key in path[:-1]:
        if not isinstance(cursor.get(key), dict):
            return out  # path does not exist in the baseline; leave untouched
        cursor = cursor[key]
    if value is OMIT:
        cursor.pop(path[-1], None)
    else:
        cursor[path[-1]] = value
    return out


def synthesize(schema: dict[str, Any]) -> list[Violation]:
    """Every single-constraint violation of `schema`, as complete payloads."""
    baseline = example(schema)
    if not isinstance(baseline, dict):
        baseline = {}
    found: list[Violation] = []

    def walk(sub: dict[str, Any], path: tuple[str, ...]) -> None:
        required = set(sub.get("required", []))
        props = sub.get("properties", {})

        if sub.get("additionalProperties") is False:
            found.append(
                Violation(
                    path + ("__unexpected__",),
                    "additionalProperties",
                    "extra key on a closed object",
                    _set(baseline, path + ("__unexpected__",), "surprise"),
                )
            )

        for name, child in props.items():
            here = path + (name,)

            if name in required:
                found.append(
                    Violation(here, "required", "required field omitted", _set(baseline, here, OMIT))
                )

            for constraint, detail, value in _bad_values(child):
                found.append(Violation(here, constraint, detail, _set(baseline, here, value)))

            if child.get("type") == "object" or "properties" in child:
                walk(child, here)

    walk(schema, ())
    return found


# --------------------------------------------------------------------------
# Self-check
# --------------------------------------------------------------------------


def _demo() -> None:
    schema = {
        "type": "object",
        "required": ["amount", "currency"],
        "additionalProperties": False,
        "properties": {
            "amount": {"type": "integer", "minimum": 1, "maximum": 100},
            "currency": {"type": "string", "enum": ["usd", "eur"]},
            "note": {"type": "string", "maxLength": 10},
            "customer": {
                "type": "object",
                "required": ["email"],
                "properties": {"email": {"type": "string", "format": "email"}},
            },
            "tags": {"type": "array", "items": {"type": "string"}},
        },
    }

    base = example(schema)
    assert base["amount"] == 50, base  # midpoint of [1, 100]
    assert base["currency"] == "usd", base  # first enum value
    assert base["customer"]["email"] == "user@example.com", base

    violations = synthesize(schema)
    by_constraint: dict[str, int] = {}
    for v in violations:
        by_constraint[v.constraint] = by_constraint.get(v.constraint, 0) + 1

    for expected in ("type", "required", "enum", "minimum", "maximum", "maxLength",
                     "format", "items", "additionalProperties"):
        assert expected in by_constraint, f"no {expected} violation generated"

    # Nested fields are reached.
    assert any(v.path == ("customer", "email") for v in violations), "nested walk failed"

    # The load-bearing rule: each payload differs from the baseline in one place.
    for v in violations:
        assert _diff_count(base, v.payload) == 1, f"{v} mutated more than one field"

    print(f"synth: {len(violations)} violations across {len(by_constraint)} constraint types")
    for name, count in sorted(by_constraint.items()):
        print(f"  {name:22} {count}")
    print("ok")


def _diff_count(a: Any, b: Any) -> int:
    """How many leaf positions differ between two nested dicts."""
    if not isinstance(a, dict) or not isinstance(b, dict):
        return 0 if a == b else 1
    return sum(
        _diff_count(a.get(k), b.get(k)) if k in a and k in b else 1
        for k in set(a) | set(b)
    )


if __name__ == "__main__":
    _demo()
