# Release Notes v1.4.0 — v6 analysis chain (post reject-and-resubmit rebuild)

v1.4.0 replaces the analysis chain end-to-end in response to a reject-and-resubmit review round
(12 major points). The manuscript (`manuscript/V3_manuscript_full_v6.docx`) is regenerated from the
new chain; every in-text number is audited by `code/s65b_verify_v6.py` (53 checks).

## What changed

**Coordinates (P0: two competing coordinate sets)**
- New `data/village_geometry_v6.csv` is the single canonical anchor table (register coordinates as
  published, with `coord_source` / `verified_status` flags; Kantou and Lixi remain `approximate`).
  The v5 snap-to-fabric step is removed everywhere. Canonical-vs-register offsets audited in
  Appendix Table A11 (max 527 m).

**Morphology instrumentation (P0: code/text mismatch, Frame-O leftovers)**
- `s10b_morph_terrain_v6.py`: no snapping; forest ring = tree-cover fraction of the 500–800-m
  Euclidean annulus; water distance = built-pixel-to-water (domain-centre fallback for Mulihong);
  tSVF horizon angles truncated at ≥ 0.
- `s62b_fabric_metrics_v6.py`: edge/patch densities per hectare of **site domain**; four-connected
  patches. Component framing removed from the manuscript (Table A13 retains the earlier
  component-based table for comparison).

**Inference (P0: invalid permutation, A14 B=999 contradiction)**
- `s41f_stats_v6.py`: cyclic-shift permutation replaced by vectorized label-shuffle baseline
  (B = 9999, seed = 23) + Freedman–Lane rank-residual permutation for partial correlations; A14
  unified to B = 2999; `data/block_membership_0p15.csv` exported.
- `s41g_a14_mc_stability.py`: 20-seed × 6-design Monte-Carlo stability for every headline interval
  (Table A14b); 4 pairs are seed-sensitive and are reported as borderline in the text.

**New sensitivity evidence**
- `s66_appendix_tables.py`: Table A8 (scene composition), Table A11 (sampling frame + coordinate
  audit).
- `s67_sensitivity_v6.py`: Table A17 (WorldCover 2020-vs-2021 vintage; day-of-year adjustment).

**Reproducibility fixes**
- `s64b_thermal_diagnostics_v6.py`: WorldCover tiles resolved via `code/v3_inputs.py`
  (auto-download from the public ESA bucket); grid template via `data/lst_grid_ref.tif`; the
  sibling-directory hard-code is gone.
- README: platform claims narrowed (developed/verified on Windows; pinned versions required
  elsewhere), run order updated, JSON append-order constraint documented.
- ITU-R P.1812 citation corrected to P.1812-8 (09/2025).

## Result-level changes v5 → v6 (honest summary)

- Forest-ring associations strengthen (LST ρ = −0.68; cov85 ρ = −0.74) under the annulus
  definition; the ring is now explicitly flagged as definition-dependent.
- Edge density flips sign under domain denominators (+0.64 with LST): it now scales with built
  amount; the interpretation text was rewritten accordingly.
- tSVF–LST survives the dual criterion at the canonical anchor but is seed-sensitive in Table A14b
  → reported as borderline.
- Mulihong's canonical point is open (tSVF = 0.910), not valley-enclosed; the village narrative was
  corrected.
- Family counts: F1 64 tests / 24 dual / 23 permutation; F2 60 tests / 7 dual (six coverage-side +
  relief–LST).

## Compatibility

- v5 products (`*_v5`, `stats_v5.json`) are retained for provenance but are no longer regenerated;
  v5 scripts moved to the `LEGACY` list in `run_all.py`.
- No changes to the radio propagation core, the Landsat chain, or the coverage products.
