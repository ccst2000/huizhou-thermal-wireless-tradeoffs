# -*- coding: utf-8 -*-
"""run_all.py — convenience runner for the v4 reproducibility pipeline.
Executes the analysis chain in the README run order, skipping steps whose
sentinel output already exists (safe to re-run; downloads are cached).

Usage:  python run_all.py            # run everything (skips existing products)
        python run_all.py --force    # re-run everything
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# (script, args, sentinel output relative to repo root)
STEPS = [
    ("code/s20a_build_grids.py", [], "data/_grids_done.flag"),
    ("code/s40_lst_v2.py", ["120039"], "data/_lst_120039.flag"),
    ("code/s40_lst_v2.py", ["120040"], "data/_lst_120040.flag"),
    ("code/s40_lst_v2.py", ["121039"], "data/_lst_121039.flag"),
    ("code/s40_lst_v2.py", ["121040"], "data/_lst_121040.flag"),
    ("code/s40_lst_v2.py", ["combine"], "data/_lst_combine.flag"),
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
    ("code/s10_morph_terrain.py", [], "data/morphology_terrain_v4.csv"),
    ("code/s58_dsm_crosscheck.py", [], "tables/TableA10_dsm_crosscheck.csv"),
    ("code/s55_framed_morph.py", [], "data/morphology_framed.csv"),
    ("code/s41d_stats_v4.py", [], "data/stats_v4.json"),
    ("code/s52_calib_linkbudget.py", [], None),
    ("code/s42_fig1_v4.py", [], "figures/Fig1_study_area_EN.png"),
    ("code/s23_fig234_v4.py", [], "figures/Fig4_coverage.png"),
    ("code/s22_fig5_v4.py", [], "figures/Fig5_tradeoff.png"),
    ("code/s60_unit_tests.py", [], None),
    ("code/s61_morph_robustness.py", [], "tables/TableA13_morph_robustness.csv"),
    ("code/s31c_revision_v4.py", [], None),
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
