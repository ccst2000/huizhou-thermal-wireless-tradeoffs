# -*- coding: utf-8 -*-
"""run_all.py — convenience runner for the v6 reproducibility pipeline.
Executes the analysis chain in the README run order, skipping steps whose
sentinel output already exists (safe to re-run; downloads are cached).

Usage:  python run_all.py            # run everything (skips existing products)
        python run_all.py --force    # re-run everything

Sentinels are real pipeline products (no marker-flag files). The per-frame
Landsat steps (s40) are self-skipping: scenes already present under
data/lst_v2_scenes/ are not re-downloaded, so they are listed without a
sentinel and effectively no-op on re-runs.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# (script, args, sentinel output relative to repo root)
# 顺序约束：s41f 全量写 stats_v6.json；s41g / s64b / s67 为读-改-写追加，必须在其后。
STEPS = [
    ("code/s00_grid_ref.py", [], "data/lst_grid_ref.tif"),
    ("code/s20a_build_grids.py", [], "data/dem_utm30.tif"),
    ("code/s40_lst_v2.py", ["120039"], None),
    ("code/s40_lst_v2.py", ["120040"], None),
    ("code/s40_lst_v2.py", ["121039"], None),
    ("code/s40_lst_v2.py", ["121040"], None),
    ("code/s40_lst_v2.py", ["combine"], "data/lst_scene_manifest.csv"),
    ("code/s56_thermal_v4.py", [], "data/lst_village_v4.csv"),
    ("code/s59_lst_composite_v4.py", [], "data/lst_summer_median_v4.tif"),
    ("code/s20b_coverage_v4.py", ["0", "0"], "data/coverage_p0_0_v4.csv"),
    ("code/s20b_coverage_v4.py", ["1250", "0"], "data/coverage_p1250_0_v4.csv"),
    ("code/s20b_coverage_v4.py", ["0", "1250"], "data/coverage_p0_1250_v4.csv"),
    ("code/s20b_coverage_v4.py", ["1250", "1250"], "data/coverage_p1250_1250_v4.csv"),
    ("code/s20b_coverage_v4.py", ["0", "0", "0.7"], "data/coverage_p0_0_f0.7_v4.csv"),
    ("code/s20b_coverage_v4.py", ["1250", "0", "0.7"], "data/coverage_p1250_0_f0.7_v4.csv"),
    ("code/s20b_coverage_v4.py", ["0", "1250", "0.7"], "data/coverage_p0_1250_f0.7_v4.csv"),
    ("code/s20b_coverage_v4.py", ["1250", "1250", "0.7"], "data/coverage_p1250_1250_f0.7_v4.csv"),
    ("code/s20b_coverage_v4.py", ["0", "0", "2.6", "nocap"], "data/coverage_p0_0_v4nocap.csv"),
    ("code/s20b_coverage_v4.py", ["1250", "0", "2.6", "nocap"], "data/coverage_p1250_0_v4nocap.csv"),
    ("code/s20b_coverage_v4.py", ["0", "1250", "2.6", "nocap"], "data/coverage_p0_1250_v4nocap.csv"),
    ("code/s20b_coverage_v4.py", ["1250", "1250", "2.6", "nocap"], "data/coverage_p1250_1250_v4nocap.csv"),
    ("code/s21_phase_aggregate_v4.py", [], "data/v3_master_v4.csv"),
    ("code/s10b_morph_terrain_v6.py", [], "data/morphology_terrain_v6.csv"),
    ("code/s58_dsm_crosscheck.py", [], "tables/TableA10_dsm_crosscheck.csv"),
    ("code/s62b_fabric_metrics_v6.py", [], "data/morphology_fabric_v6.csv"),
    ("code/s63b_master_v6.py", [], "data/v3_master_v6.csv"),
    ("code/s41f_stats_v6.py", [], "data/stats_v6.json"),
    ("code/s41g_a14_mc_stability.py", [], "tables/TableA14b_mc_stability.csv"),
    ("code/s64b_thermal_diagnostics_v6.py", [], "tables/TableA15_match_diagnostics.csv"),
    ("code/s66_appendix_tables.py", [], "tables/TableA11_sampling_frame.csv"),
    ("code/s67_sensitivity_v6.py", [], "tables/TableA17_year_doy_sensitivity.csv"),
    ("code/s52b_linkbudget_v5.py", [], "tables/TableA12_link_budget.csv"),
    ("code/s42_fig1_v4.py", [], "figures/Fig1_study_area_EN.png"),
    ("code/s23b_fig234_v6.py", [], "figures/Fig4_coverage.png"),
    ("code/s22b_fig5_v6.py", [], "figures/Fig5_tradeoff.png"),
    ("code/s60_unit_tests.py", [], None),
    ("code/s61_morph_robustness.py", [], "tables/TableA13_morph_robustness.csv"),
    ("code/s32_manuscript_v6.py", [], "manuscript/V3_manuscript_full_v6.docx"),
    ("code/s65b_verify_v6.py", [], None),
]

LEGACY = [
    "code/s41d_stats_v4.py", "code/s31c_revision_v4.py", "code/s53_worldcover_calib.py",
    "code/s54_morph_recompute.py", "code/s55_framed_morph.py",
    "code/legacy_v3/s52_calib_linkbudget.py",
    # v4/v5 链（被 v6 取代，保留备查）
    "code/s10_morph_terrain.py", "code/s62_fabric_metrics.py", "code/s63_master_v5.py",
    "code/s64_thermal_diagnostics.py", "code/s41e_stats_v5.py",
    "code/s22_fig5_v5.py", "code/s23_fig234_v5.py",
    "code/s31d_manuscript_v5.py", "code/s65_verify_v5.py",
]


def main():
    force = "--force" in sys.argv[1:]
    for script, args, sentinel in STEPS:
        if sentinel and not force and os.path.exists(os.path.join(ROOT, sentinel)):
            print(f"[skip] {script} {' '.join(args)}  ({sentinel} exists)")
            continue
        print(f"[run ] {script} {' '.join(args)}", flush=True)
        r = subprocess.run([PY, "-X", "utf8", script, *args], cwd=ROOT)
        if r.returncode != 0:
            print(f"[FAIL] {script} exited {r.returncode}; stopping.")
            sys.exit(r.returncode)
    print("ALL STEPS DONE")


if __name__ == "__main__":
    main()
