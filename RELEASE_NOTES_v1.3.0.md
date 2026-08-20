# Release notes — v1.3.0 (v5 analysis chain)

Corresponds to the v5 manuscript (`manuscript/V3_manuscript_full_v5.docx`), rebuilt after the
fourth-round review.

## Analysis changes

- **Morphology chain switched to fully scripted**: `s10_morph_terrain.py` (terrain/landscape,
  COP-DEM + WorldCover via Planetary Computer STAC) is now the primary chain; the legacy hand-built
  table is retained for provenance and compared in Table A13.
- **New building-fabric metrics** (`s62_fabric_metrics.py`): building coverage ratio, edge density,
  patch density, largest-patch share, and the corrected-perimeter domain compactness — all from the
  10-m WorldCover raster inside the 500-m site domain.
- **New analysis table of record**: `data/v3_master_v5.csv` (29 villages × 16 metrics × 4 outcomes),
  merged by `s63_master_v5.py`.
- **Inference framework** (`s41e_stats_v5.py`, `data/stats_v5.json`): primary decision rule is now a
  dual criterion — within-family Benjamini–Hochberg q < 0.05 AND a 0.15° spatial block-bootstrap 95%
  CI excluding zero (B = 2999, seed 11). Exact cyclic-shift permutation p-values (floor 1/29) and a
  rank-Moran's-I effective-sample-size heuristic are reported as diagnostics only. Block-size and
  grid-origin sensitivity: Table A14. Test families: F1 = 64 raw, F2 = 60 size-controlled partials.
- **Thermal diagnostics** (`s64_thermal_diagnostics.py`): post-matching balance audit (Table A15),
  water-mask threshold sensitivity (Table A16), and an absolute-LST estimand audit
  (overpass-resolved vs composite-raster extraction, `data/lst_abs_composite_v5.csv`).
- **Worked link budgets** regenerated under the primary model (`s52b_linkbudget_v5.py`, Table A12);
  the earlier calibration script moved to `code/legacy_v3/`.

## Result changes relative to v1.2.0 (v4 chain)

- The forest ring is now a **two-sided** attribute: associated with lower village LST
  (ρ = −0.58, dual criterion) as well as with signal shadowing (ρ = −0.65). The earlier null thermal
  result was an artifact of the legacy chain's narrower component-anchor window.
- Terrain-horizon openness vs LST is **marginal** under the dual criterion (CI touches zero).
- Fabric consolidation is associated with higher LST and ΔLST (coverage ratio ρ = +0.65 / +0.56;
  largest-patch share; edge and patch density with opposite sign).
- All seven size-controlled (F2) survivors lie on the coverage side.

## Reproducibility fixes

- Removed the sibling-repo dependency: `s20a`/`s56` now fetch COP-DEM and WorldCover tiles from
  public S3 buckets via `code/v3_inputs.py` (`data/external/`).
- The 100-m analysis grid is defined by `code/s00_grid_ref.py` → `data/lst_grid_ref.tif`
  (clones the shipped median composite's grid; documented bbox fallback).
- `run_all.py` sentinels are real pipeline products (no marker flags).
- `.gitattributes` pins `*.csv -text` so `CHECKSUMS.sha256` is platform-stable (60 files).
- New `code/s65_verify_v5.py`: audits 44 in-text numeric claims against `stats_v5.json`.
