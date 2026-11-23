# Lead + Rhythm as default — design

**Intent:** Default conversions try Lead vs Rhythm so you can hear/see whether the engine separates them. Solo guitar remains an explicit override.

**Goals:**
- New runs default to Full mix + stem separation + Lead + Rhythm engine (when available).
- Result shows a **Lead | Rhythm | Combined** part switcher when those artifacts exist.
- Matching listen sources: original / guitar stem / lead / rhythm.
- Soft fallback to one guitar tab + visible notice when the split fails or weights are missing.

**Non-goals:** Bass (or drums/vocals) tabs; multi-track editor; rebuilding result schema into a generic `parts[]` model; changing Mel-Band split quality itself.

**Approaches considered:**
1. Flip defaults + surface existing artifacts — **chosen**.
2. First-class multi-part run model — deferred.
3. Defaults without UI switcher — rejected (could not evaluate the split).

**Builder calls:** Default open part = `lead` when `lead_result` exists, else `combined`. Soft fallback writes `details.lead_rhythm_fallback` + message; does not fail the job.
