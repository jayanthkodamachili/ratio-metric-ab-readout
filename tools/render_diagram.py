"""Render the committed architecture SVG.

Hand written rather than produced by a diagramming library, for the reasons in ADR-004: a
committed SVG with intrinsic dimensions and an explicit light background renders the same
on GitHub in either theme, which a Mermaid fence does not reliably do.
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "architecture.svg"

W, H = 960, 500
INK = "#1b1f23"
MUTED = "#57606a"
BAD = "#b42318"
GOOD = "#116329"
LINE = "#8c959f"


def box(x, y, w, h, title, subtitle="", stroke=MUTED, fill="#ffffff", bold=False):
    weight = "600" if bold else "400"
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="1.5"/>',
        f'<text x="{x + w / 2}" y="{y + (20 if subtitle else h / 2 + 4)}" '
        f'text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="13" '
        f'font-weight="{weight}" fill="{INK}">{title}</text>',
    ]
    if subtitle:
        for index, line in enumerate(subtitle.split("|")):
            parts.append(
                f'<text x="{x + w / 2}" y="{y + 38 + index * 14}" text-anchor="middle" '
                f'font-family="Helvetica,Arial,sans-serif" font-size="11" '
                f'fill="{MUTED}">{line}</text>'
            )
    return "".join(parts)


def arrow(x1, y1, x2, y2, dashed=False):
    dash = ' stroke-dasharray="4 3"' if dashed else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE}" '
        f'stroke-width="1.5" marker-end="url(#a)"{dash}/>'
    )


def label(x, y, text, fill=MUTED, size=11, anchor="middle", weight="400"):
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Helvetica,Arial,sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">{text}</text>'
    )


def render() -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="Architecture of ratio-metric-ab-readout">',
        '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
        f'markerHeight="6" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="{LINE}"/>'
        "</marker></defs>",
        f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
        label(
            W / 2, 26,
            "One effect, three standard errors, and the unit each one believes in",
            INK, 14, weight="600",
        ),
    ]

    # Left: the data, at the unit it was randomised on.
    parts.append(box(24, 54, 190, 56, "seeded generator",
                     "users, not events|fixed seed, no network"))
    parts.append(box(24, 142, 190, 56, "one row per user",
                     "events and successes|per randomisation unit", bold=True))
    parts.append(arrow(119, 110, 119, 142))

    parts.append(box(24, 238, 190, 50, "SRM gate", "assignment sane?", stroke=GOOD,
                     fill="#f2fbf4"))
    parts.append(arrow(119, 198, 119, 238))

    # Middle: the fork. The naive path flattens the table first.
    parts.append(box(276, 78, 300, 58, "flatten to one row per event",
                     "the correlation is hidden, not removed",
                     stroke=BAD, fill="#fff5f4"))
    parts.append(box(276, 182, 300, 58, "keep the user as the unit",
                     "delta method, closed form", stroke=GOOD, fill="#f2fbf4"))
    parts.append(box(276, 262, 300, 58, "resample users with replacement",
                     "cluster bootstrap, the oracle", stroke=GOOD, fill="#f2fbf4"))

    parts.append(arrow(214, 165, 276, 107))
    parts.append(arrow(214, 170, 276, 211))
    parts.append(arrow(214, 178, 276, 291))

    # Right: three standard errors on one effect.
    parts.append(box(630, 78, 180, 58, "p = 0.012", "too small by 1.5x",
                     stroke=BAD, fill="#fff5f4", bold=True))
    parts.append(box(630, 182, 180, 58, "p = 0.092", "honest", stroke=GOOD,
                     fill="#f2fbf4", bold=True))
    parts.append(box(630, 262, 180, 58, "p = 0.090", "honest", stroke=GOOD,
                     fill="#f2fbf4", bold=True))

    for y in (107, 211, 291):
        parts.append(arrow(576, y, 630, y))

    parts.append(label(720, 155, "same rows, same effect,", MUTED, 10))
    parts.append(label(720, 167, "different verdict", MUTED, 10))

    parts.append(
        box(140, 392, 680, 76, "the effect is identical in all three; only its uncertainty moves",
            "no property of the naive p-value reveals the problem, because the problem is "
            "an assumption|the number never encodes: that the events were independent",
            bold=True)
    )
    parts.append(arrow(720, 320, 600, 392))
    parts.append(arrow(426, 240, 400, 392))

    parts.append(label(245, 160, "same", MUTED, 10))
    parts.append(label(245, 172, "rows", MUTED, 10))

    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render() + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
