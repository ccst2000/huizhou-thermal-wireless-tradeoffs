# Thermal–Wireless Trade-Offs of Terrain-Constrained Settlement Morphology in Huizhou Traditional Villages — Reproducibility Package

This repository contains the full analysis code, village-level analysis tables, figure scripts, and
supporting data for the manuscript:

> L. Zhang, *Thermal–Wireless Trade-Offs of Terrain-Constrained Settlement Morphology in Huizhou
> Traditional Villages* (under review).

All inputs are public datasets (Copernicus DEM GLO-30, ESA WorldCover 2021 v200, Landsat 8/9
Collection-2 Level-2 via Microsoft Planetary Computer). No field data are used. The pipeline is
deterministic; the only stochastic steps use fixed seeds (noted below).

## Repository layout

```
code/        analysis scripts (run order below)
data/        village-level analysis tables, scene manifest, coverage results, statistics JSON
tables/      Tables 1, 2 and Appendix Tables A1–A9 (CSV, UTF-8-BOM)
figures/     Figures 1–5 (PNG, 300 dpi)
```

Large raster intermediates (30-m UTM DEM/built-up grids, Landsat per-scene stacks, Esri tiles) are
**not** included; they are rebuilt automatically by `s20a_build_grids.py`, `s40_lst_v2.py`, and
`s42_fig1.py` from the public sources above.

## Environment

- Python 3.12.4 (Windows; Linux/macOS should work identically)
- numpy 2.5.2, pandas 3.0.5, scipy 1.18.0, rasterio 1.5.1, matplotlib 3.11.1,
  python-docx 1.2.0, pystac-client 0.9.0, planetary-computer 1.0.0, pyproj
- See `requirements.txt`.

## Run order

```bash
python code/s20a_build_grids.py        # 30-m UTM DEM + WorldCover built-up grids (downloads via STAC)
python code/s40_lst_v2.py 120039       # Landsat QA-masked per-scene stacks, per WRS frame
python code/s40_lst_v2.py 120040
python code/s40_lst_v2.py 121039
python code/s40_lst_v2.py 121040
python code/s40_lst_v2.py combine      # frames -> lst_summer_median.tif, obs counts, lst_village_v2.csv
python code/s20b_coverage.py 0 0           # coverage, grid phase (0,0), 2.6 GHz
python code/s20b_coverage.py 1250 0        # phase (1250,0)
python code/s20b_coverage.py 0 1250        # phase (0,1250)
python code/s20b_coverage.py 1250 1250     # phase (1250,1250)
python code/s20b_coverage.py 0 0 0.7       # 700 MHz sensitivity, all four phases
python code/s20b_coverage.py 1250 0 0.7
python code/s20b_coverage.py 0 1250 0.7
python code/s20b_coverage.py 1250 1250 0.7
python code/s20b_coverage.py 0 0 2.6 nlos5k  # NLOS 5-km truncation variant (phase 0,0)
python code/s21_phase_aggregate.py     # four-phase village means -> v3_master.csv
python code/s50_round2.py              # scene-matched dLST + bootstrap CIs, scene composition,
                                       # NLOS-truncation sensitivity, 700-MHz four-phase table,
                                       # full jackknife -> lst_village_v3.csv, dlst_scene_matrix.csv, ...
python code/s53_worldcover_calib.py    # 10-m WorldCover per-village reconstruction + water ring shares
python code/s54_morph_recompute.py     # Frame-O plan-form definitions, precise recompute (diagnostic)
python code/s55_framed_morph.py        # Frame-D plan-form metrics -> morphology_framed.csv
python code/s41c_stats_v3.py           # correlations, FDR families F1/F2, sensitivity batteries,
                                       # stats_v3.json, Tables 1/2/A1/A3/A4/A5/A6/A7/A8
python code/s41c2_spatial_v3.py        # Moran's I (UTM weights) + Fisher 95% CIs -> stats_v3.json, Table A5
python code/s52_calib_linkbudget.py    # worked link budgets -> Table A9 (and definition calibration)
python code/s42_fig1.py                # Fig. 1 (downloads Esri World Imagery tiles)
python code/s23_fig234.py              # Figs. 2–4
python code/s22_fig5.py                # Fig. 5
python code/s31b_revision.py           # manuscript DOCX (plain single-column layout)
```

Expected runtime: ~3–5 h total, dominated by STAC downloads (first run) and the 700-MHz recomputation;
all scripts cache downloads and are safe to re-run. Fixed seeds: scene bootstrap (`seed=7`),
Moran's I permutations (`seed=7`), Fig. 2c jitter (`seed=7`).

## Key data files

- `data/v3_master.csv` — 29 villages × morphological metrics + four-phase performance variables
- `data/lst_village_v3.csv` — village LST plus scene-matched ΔLST with bootstrap 95% CI and P(ΔLST > 0)
- `data/dlst_scene_matrix.csv` — per-village per-scene scene-matched anomalies (29 × 36)
- `data/morphology_framed.csv` — Frame-D plan-form metrics (elongation, compactness) used in the paper
- `data/morphology_v2.csv`, `data/morph_calib_10m.csv` — Frame-O recompute and cross-version
  calibration diagnostics (document why the Frame-O shape metrics were retired)
- `data/built_domain_area.csv` — domain-clipped vs connected-component built-up areas (the two spatial frames)
- `data/coverage_p*.csv` — per-phase village coverage (`_f0.7` = 700 MHz, `_nlos5k` = NLOS truncation)
- `data/coverage_700mhz_4phase.csv` — 700-MHz four-phase village coverage (Appendix Table A6)
- `data/village_sample_v2.csv` — candidate list with per-village coordinate verification status
  (`_draft`/`_v1` retained for provenance)
- `data/lst_scene_manifest.csv` — 36 queried Landsat scenes (3 invalid under the QA chain, 2 near-zero;
  marked in Appendix Table A2)
- `data/stats_v3.json` — every in-text statistic, generated by `s41c_stats_v3.py` / `s41c2_spatial_v3.py`

## Known limitations (quoted from the manuscript)

Coverage targets for Zuyuan and Mulihong use a 150-m fallback grid (WorldCover under-detection);
component-anchored metrics are unavailable for these two villages (n = 27 where applicable), and
Mulihong additionally lacks Frame-D plan-form metrics (n = 28 where applicable). Yuliang's
connected component merges with the adjacent county seat (robustness verified by exclusion). The radio
chain is a deterministic received-power scenario under a stylized deployment, not an operational
network estimate. LST is a summer daytime surface measure, not air temperature or thermal comfort.

## License

- Code: MIT
- Data tables and figures: CC BY 4.0

## Citation

[Paper DOI to be added upon publication.]
