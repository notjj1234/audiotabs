# Unslop Svelte Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` (or subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the shipping Svelte app read as a guitar-tab studio (Tab PDF), not a generic AI converter card—by fixing contract drift against DESIGN.md / PRODUCT.md.

**Architecture:** Light-slop polish mode. Keep HOME navy/amber, Satoshi, JetBrains Mono, screen order, and copy deck. Widen the shell, quiet chrome, one transport shadow, brand string restored. No new palette, no hero image generation, no practice-player rebuild.

**Tech Stack:** Svelte (`app/web`), CSS tokens in `app/web/src/app.css`, pytest contract tests in `tests/test_web_tokens.py`.

**Spec:** DESIGN.md, PRODUCT.md, docs/superpowers/specs/2026-11-18-ui-redesign-design.md

## Direction (locked)

| Line | Value |
|------|--------|
| Product | Local desktop app that turns a recording into guitar tab for practice |
| Character | Exact, studio-quiet, a little warm |
| World | Guitar desk / tab paper under warm lamp — navy workspace, amber as the only bright mark |
| Moments | Rendered tab staff (and transport when present); chrome stays quiet |
| Signature | Amber playhead / active segment on notation |

## Global Constraints

- Brand name in chrome and `document.title`: **Tab PDF**
- One accent: `#f6ad49`; no second accent, glow, gradient text, or glass panels
- Content max width **1180px**, gutters **32px**
- One shadow: pinned transport only
- `--weight-semibold: 500`

## Tasks (executed 2026-11-22)

- [x] Task 1: Design tokens and motion contract
- [x] Task 2: Brand and shell width
- [x] Task 3: Entry + Waiting surface polish
- [x] Task 4: Library + Result chrome polish
- [x] Task 5: Copy audit (no confirmed AI-hype tells; chevron glyph → SVG)
- [x] Task 6: Verify

## Out of scope

- Custom practice transport rebuild
- README badge cleanup
- Notation SVG rendering quality overhaul
