# Phase-2 Missions

Three sequential missions close the fidelity gaps identified in the phase-1
handoff (see `/README.md` → "Phase 2 gaps").

| ID | Mission | Depends on | Est. effort | Target audit score |
|----|---------|------------|-------------|--------------------|
| M1 | Two-column note apparatus (מקור right / צינור left) | — | ~2–4h | ≥ 48 (no regression) |
| M2 | Full-width spillover zone | M1 | ~3–6h | ≥ 55 |
| M3 | Winged-cherub end-of-chapter ornament | — (parallel to M1/M2) | ~1–2h | no regression |

# Phase-3 Missions

Close the last structural-fidelity gap (adaptive body-height) and a small
remaining visual polish (true oval cartouche). Designed to land after M3.

| ID | Mission | Depends on | Est. effort | Target |
|----|---------|------------|-------------|--------|
| M4 | Adaptive body-height layout (atomic-unit packing) | M2, M3 | ~8–16h | body-zone variance ≥ 30mm; audit Δ ≥ −1.0 vs M2 |
| M5 | Oval cartouche curve | M4 | ~2–4h | ellipse aspect 2.5:1 ±10%; audit Δ ≥ −0.5 vs M4 |

M4 is the core Phase-3 work — it replaces the fixed 75mm bottom margin
with a per-page body/notes split computed from each page's notes volume,
matching the reference book's adaptive body behaviour (`source_uploads/
pagination_study.md` §1.4). M5 rides along as a visual polish that's
trivial to ship once M4 is green.

Each mission directory contains:

- `mission.md` — goal, references, suggested approach
- `validation-contract.md` — testable assertions (A1…An)
- `AGENTS.md` — how to build/verify in the sandbox
- `validation-state.json` — machine-readable status tracking

## Running a mission

```bash
# 1) Pick a mission
MISSION=m1-two-col-notes

# 2) Read the contract
cat .factory/missions/$MISSION/mission.md

# 3) Work on the code (typst/template.typ, python/convert.py)

# 4) Build
python3 python/convert.py
~/.local/bin/typst compile --root . --font-path typst/fonts build/book.typ build/book.pdf
~/.local/bin/typst compile --root . --font-path typst/fonts build/book.typ build/page-{n}.png --ppi 120 --format png

# 5) Run the audit to get a score
python3 audit/image_diff.py

# 6) For each assertion in validation-contract.md, collect evidence and
#    update validation-state.json
```

## Handing off to a droid

To invoke a validation sub-droid (once in missions mode proper):

```bash
# from Factory UI: "Run mission M1 with full validation"
# ...or use the Task tool with subagent_type=user-testing-flow-validator,
#    passing {missionDir: ".factory/missions/m1-two-col-notes"}.
```
