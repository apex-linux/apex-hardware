"""A dated acceptance record, as JSON and as Markdown.

The owner copies both files back into the repository; the Markdown reads
on GitHub, the JSON is what a later run or a script compares against.
"""

from collections.abc import Mapping, Sequence
import json

from apex_hw.kernel import result

SCHEMA = 1

LABELS = {
    result.Status.PASS: "PASS",
    result.Status.FAIL: "FAIL",
    result.Status.ABSENT: "SKIP",
    result.Status.NEEDS_PERSON: "TODO",
}

_FACTS = (
    ("machine", "Machine"),
    ("bios", "BIOS"),
    ("os", "OS"),
    ("image", "Image version"),
    ("variant", "Variant"),
    ("kernel", "Kernel"),
    ("nvidia", "NVIDIA module"),
    ("upower", "UPower"),
    ("libfprint", "libfprint"),
    ("suspends", "Suspends this boot at the start"),
    ("checker", "Checker"),
    ("started", "Started"),
)


def line(row: result.Result) -> str:
    """Formats one row as the run prints it."""
    return f"{LABELS[row.status]}  {row.row:<12} {row.value}"


def to_json(
    facts: Mapping[str, str], records: Sequence[result.RowRecord]
) -> str:
    """Returns the record as JSON text."""
    data = {
        "schema": SCHEMA,
        "facts": dict(facts),
        "rows": [
            {
                "row": r.result.row,
                "status": r.result.status.value,
                "value": r.result.value,
                "evidence": [
                    {"step": e.step, "status": e.status.value, "value": e.value}
                    for e in r.evidence
                ],
            }
            for r in records
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _cell(text: str) -> str:
    """Escapes text for a Markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def to_markdown(
    title: str, facts: Mapping[str, str], records: Sequence[result.RowRecord]
) -> str:
    """Returns the record as a Markdown page."""
    counts: dict[str, int] = {}
    for r in records:
        label = LABELS[r.result.status]
        counts[label] = counts.get(label, 0) + 1
    summary = ", ".join(
        f"{counts[label]} {label}"
        for label in ("PASS", "FAIL", "TODO", "SKIP")
        if label in counts
    )
    out = [f"# {title}", "", f"Result: {summary}.", ""]
    out += ["| Item | Value |", "| --- | --- |"]
    for key, name in _FACTS:
        if key in facts:
            out.append(f"| {name} | {_cell(facts[key])} |")
    out += ["", "## Output", "", "```text"]
    out += [line(r.result) for r in records]
    out += ["```", "", "## Evidence", ""]
    for r in records:
        out += [f"### {r.result.row}", ""]
        out += ["| Step | Status | Value |", "| --- | --- | --- |"]
        for e in r.evidence:
            out.append(
                f"| {_cell(e.step)} | {LABELS[e.status]} | {_cell(e.value)} |"
            )
        out.append("")
    return "\n".join(out)
