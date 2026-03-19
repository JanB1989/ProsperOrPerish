# Prosper or Perish — crash root-cause investigation

This document implements the investigation workflow: reproducibility, graphics isolation, in-mod bisection, log correlation, division/cap audit, and Paradox escalation.

## Established facts (from crash dumps)

| Item | Value |
|------|--------|
| Exception | `EXCEPTION_INT_DIVIDE_BY_ZERO` (`C0000094`) |
| Instruction | Same address across sessions (e.g. `0x00007FF70D541666`) |
| Stack | Wwise `AK::WriteBytesMem::Size`, ends near `NVSDK_NGX_D3D12_Shutdown1` |
| Implication | Native stack does **not** name a script line; treat as **weak** localization evidence |

### Parsed bundle facts (automated)

Use [`tools/parse_eu5_crash_bundles.py`](../tools/parse_eu5_crash_bundles.py) to aggregate every crash folder under `Documents/.../Europa Universalis V/crashes/` that contains `exception.txt`:

```text
uv run python tools/parse_eu5_crash_bundles.py
uv run python tools/parse_eu5_crash_bundles.py --crashes-dir "C:/Users/.../Europa Universalis V/crashes"
uv run python tools/parse_eu5_crash_bundles.py --known-address 0x00007FF70D541666
```

Optional env: `EU5_CRASHES_DIR` if you omit `--crashes-dir`. The script prints a **summary table** (exception code, fault address, **stack fingerprint** = SHA-256 of stack lines), then per-bundle **AppVersion**, **SCMCommit**, **RenderAPI**, GPU, **Mod_** lines, **Idler** lines, and the **last N lines** of `logs/debug.log` (default 25; use `--tail-lines`). Mark known fault PCs with repeated `--known-address` to flag **new** addresses.

**Recorded on repo machine (example):** four bundles shared the same fault address and stack fingerprint `80f62d827b85b863`; some sessions had **Prosper or Perish only**, others **Faster Universalis + Prosper or Perish** — same native fault either way.

**`pdx_settings.json` in the bundle** may show `"upscale": "DISABLED"` even when the stack unwind references NVIDIA NGX — still run the graphics matrix below.

### Why the main `logs/error.log` is not enough

Always grep the **crash bundle copy**: `crashes/<folder>/logs/error.log`. It is time-aligned with that session and includes lines the rolling log may have rotated away. High-signal strings (see Phase 3) often appear **only** there.

---

## Phase 0 — Repro matrix (fill every run)

Copy this block into a note or ticket:

| Field | Your value |
|-------|------------|
| Date/time | |
| Game version | e.g. 1.1.10 |
| Mods enabled | P&P only / P&P + Faster Universalis / other |
| Entry | Named bookmark / ironman / **save file name** |
| Graphics API | Vulkan / D3D12 |
| DLSS / frame gen | On / Off |
| Display mode | Fullscreen / borderless / windowed |
| Steps to crash | (numbered) |
| Crash folder | `Documents/.../crashes/Europa Universalis V...` |
| Notes | |

---

## Phase 1a — Mod isolation

1. Disable **all** mods except **Prosper or Perish**.
2. Reproduce with the **same** steps.
3. If stable: re-enable **one** other mod at a time (e.g. Faster Universalis) until the crash returns.

**Interpretation:** Pairwise interaction vs P&P-only fault.

---

## Phase 1b — Graphics / NGX matrix (same repro)

Run the **same** reproduction after each change. After a crash, run `parse_eu5_crash_bundles.py` and note the **fault address** and **stack fingerprint** — if they change, you are likely on a **different** bug.

| Run | API (launcher) | Upscale / DLSS / frame gen | Display mode | Steam overlay | Other overlays (GOG, OBS, RTSS) | Crash? (Y/N) | Fault address from `exception.txt` |
|-----|----------------|----------------------------|--------------|---------------|----------------------------------|--------------|-------------------------------------|
| 1   | (baseline)     |                            |              |               |                                  |              |                                     |
| 2   |                |                            |              |               |                                  |              |                                     |

Checklist (tick each before testing):

1. In-game: **upscale off**, **DLSS off**, **frame generation off** (match `pdx_settings.json` in the crash bundle if needed).
2. NVIDIA App / driver: no forced DLSS for EU5 if applicable.
3. **Vulkan** vs **DirectX 12** — full restart between runs; confirm `RenderAPI` in `meta.yml` after a crash.
4. **Borderless** vs **exclusive fullscreen**.
5. Disable **Steam overlay** (Steam → Properties) for one run; disable **Galaxy / OBS / capture** Vulkan layers if present (your `debug.log` lists instance layers when relevant).

**Interpretation:**

- Crash **stops** when switching API or overlays → weight **driver/NGX** and/or **Paradox render path**; attach bundles when escalating.
- **Same fault address** across API changes → weight **mod bisection** (Phase 2) and simulation/data.
- Crash **only** with DLSS/upscale on (if you ever enable them) → treat as **driver/NGX** interaction; mod may still be the trigger for load/timing.

---

## Phase 2 — Binary search inside the mod (folder bisection)

Work on a **copy** of the mod or rename folders so the game does not load them (e.g. rename `map_modes` → `map_modes.off`).

**Default mod root (adjust to your install):**

`Documents/Paradox Interactive/Europa Universalis V/mod/Prosper or Perish (Population Growth & Food Rework)/`

**Order** (cheap → expensive); restore the previous step before trying the next:

1. **`in_game/gfx/map/map_modes/`** — all four files (`pp_food_map_modes.txt`, `pp_local_output_modifier_map_modes.txt`, `pp_population_capacity_map_modes.txt`, `pp_unemployed_peasants_map_modes.txt`). If removing the folder stops the crash, restore and delete **one file at a time** to find the culprit.
2. **`in_game/common/on_action/`** — temporarily disable or gut calls in `pp_game_start.txt` (e.g. comment `pp_remove_invalid_buildings` / precalculation blocks in a **copy** only).
3. **`in_game/common/building_types/`** — building defs.
4. **`main_menu/common/static_modifiers/`** and **`in_game/common/static_modifiers/`**.
5. **`loading_screen/common/defines/`**.

**Stopping rule:** Smallest subtree that **removes** the crash = first suspect; then bisect **files** inside that subtree.

---

## Phase 3 — Log correlation (high-signal strings)

After each session, search the **crash bundle** `crashes/<timestamp>/logs/error.log` first, then the main `Documents/.../logs/error.log`. The bundle file is the authoritative copy for that crash.

Search for:

- `building.cpp` — especially **null owner** / **Market Village**
- `building_manager` — **Max is** (negative max levels)
- `market_village`
- `divide` / `Script system error` spikes before exit

**Mod touchpoint:** `pp_remove_invalid_buildings` in `in_game/common/on_action/pp_game_start.txt` adjusts **market_village** levels vs `rural_building_cap`. A defensive **`has_owner = yes`** scope was added so building changes do not run on locations with no owner (see mod changelog / git).

**Save forensics:** Use ProsperPerishCalcs (`analysis/`, configured via `analysis/building_levels/config.json`) to inspect a named location’s buildings and owner ids when needed.

---

## Phase 4 — Division / cap audit (automated checklist)

Verified in-repo:

| Area | Status |
|------|--------|
| `pp_food_map_modes.txt` | `divide = { value = global_var:pp_*_global_range min = 1 }` |
| `pp_building_caps.txt` | Rural caps: `min = 0` on sheep/farming/forest/fishing; fruit_orchard already had `min = 0` |
| `pp_local_output_modifier_map_modes.txt` | `divide = @factor_divide` with `@factor_divide = 2.0` |
| Laws / other map modes | Constant divisors (10, 50, 500) |

Re-run ripgrep periodically:

```text
rg "divide\\s*=" "path/to/mod/in_game"
rg "max_levels\\s*=" "path/to/mod/in_game/common"
```

---

## Phase 5 — Paradox escalation pack

If you have a **minimal** repro (P&P-only or smallest file set), **DLSS off**, and **vanilla** does not crash, prepare a zip with:

1. `exception.txt`, `meta.yml`, full `logs/error.log` from the crash folder.
2. `pdx_settings.json` from the crash folder (optional).
3. The **save** (if load-dependent) or exact **bookmark** name and **date**.
4. **Mod version**: folder or Steam Workshop id + `metadata.json` / descriptor.
5. Short **repro steps** (from Phase 0 matrix).

Submit via Paradox forums or launcher with game version and build id from `meta.yml`.

---

## Audit notes: `pp_game_start.txt` (market_village)

The **market village** block (reduce to `rural_building_cap`) runs inside `every_location_in_the_world`. The engine log once reported a **Market Village with null owner** in a **location with no owner**. Building level changes on such locations are now restricted to **`has_owner = yes`** so scripted adjustments do not run in that edge case.

---

## Related files

- Mod: `.../mod/Prosper or Perish (Population Growth & Food Rework)/`
- Logs: `Documents/Paradox Interactive/Europa Universalis V/logs/`
- Crashes: `Documents/Paradox Interactive/Europa Universalis V/crashes/`
