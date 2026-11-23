# Lead + Rhythm as default — Implementation Plan

> **For agentic workers:** Use executing-plans or subagent-driven-development. Spec: `docs/superpowers/specs/2026-11-23-lead-rhythm-default-design.md`.

**Goal:** Make Lead + Rhythm the default conversion path and surface separate Lead / Rhythm / Combined tabs in Result.

**Architecture:** Reuse existing `_run_lead_rhythm_stage` artifacts; flip Entry defaults; soft-fallback on split failure; score/audio `part`/`kind` selectors; Result switcher.

**Tech Stack:** FastAPI, Svelte, existing Mel-Band RoFormer lead/rhythm split, Basic Pitch.

See Cursor plan `lead_rhythm_default` for full task breakdown.
