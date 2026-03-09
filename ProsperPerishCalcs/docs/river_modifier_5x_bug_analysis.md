# River Modifier 5x Display Bug – Root Cause

## Summary

In the **location view**, `river_flowing_through` modifiers (e.g. `local_fish_output_modifier = 0.1`) are shown correctly. In the **building view** (when building or inspecting a building), the same modifiers appear multiplied by **5**.

## Root Cause

The bug comes from a mismatch in **employment_size** between PP buildings and the game’s display logic.

### Vanilla vs Prosper or Perish

| Source | Building | employment_size | Value |
|--------|----------|-----------------|-------|
| Vanilla ([default_values.txt](c:\Games\steamapps\common\Europa Universalis V\game\main_menu\common\script_values\default_values.txt)) | RGO buildings | `rural_peasant_produce_employment` | **1.0** |
| Vanilla | Village buildings | `village_employment_size` | **1.0** |
| PP ([pp_building_adjustments.txt](c:\Users\Anwender\Documents\Paradox Interactive\Europa Universalis V\mod\Prosper or Perish (Population Growth & Food Rework)\in_game\common\building_types\pp_building_adjustments.txt)) | fruit_orchard | hardcoded | **5** |
| PP | sheep_farms | hardcoded | **5** |
| PP | fishing_village | hardcoded | **5** |
| PP | forest_village | hardcoded | **5** |
| PP | farming_village | `rural_peasant_produce_employment` | **1.0** |

### What the game does

The building production efficiency tooltip scales the displayed effect of location modifiers by `employment_size`. So for:

- **Location view**: shows raw modifier (e.g. `local_fish_output_modifier = 0.1` → +10% fish)
- **Building view**: shows modifier × employment_size → 0.1 × 5 = **0.5** → displayed as +50%

Hence the exact 5x difference.

## Affected Buildings

- `fruit_orchard` (line 145)
- `sheep_farms` (line 176)
- `fishing_village` (line 207)
- `forest_village` (line 257)

`farming_village` uses `rural_peasant_produce_employment` (1.0), so its display should match the location view.

## Fix Options

### Option A: Use vanilla script value (display matches location view)

Change `employment_size = 5` to `employment_size = rural_peasant_produce_employment` for the four buildings above.

**Effect:**
- Display of modifiers in the building view matches the location view.
- Employment per building level changes from 5 to 1 pops; this may affect balance and pop distribution.

### Option B: Keep employment_size = 5 (intended balance)

Leave employment_size at 5. The building view then correctly shows the total effect across all 5 employment slots, but the numbers look 5x higher than in the location view.

### Option C: Custom script value

Introduce a script value (e.g. `pp_rgo_employment_size = 1`) used only for these buildings, so they display like vanilla while letting you tune employment later if needed.

## Recommendation

If the 5x difference is unintentional, use **Option A** for consistency with vanilla and with the location view.

If `employment_size = 5` is intentional for balance, the display is consistent with the logic; the “bug” is only that the UI scales by employment, which may be confusing. Option C can be used if you want display consistency now and flexibility to adjust employment later.
