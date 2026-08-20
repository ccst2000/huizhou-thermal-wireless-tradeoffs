# -*- coding: utf-8 -*-
"""s60 单元测试（R3 M5/M9）：对 geo_utils 的独立核验
  T1 平地链路手算核验（RMa PL1，独立代码路径复算）
  T2 NLOS >= LOS；NLOS 超 5km 截断为 inf（主模型）；nocap 时为有限值
  T3 d3d 单调性：固定 d2d，d3d 增大 -> PL 增大（三维修正确实生效）
  T4 正方形周长/紧凑度手算核验（各向同性 dx=dy）
  T5 矩形周长各向异性核验（dx!=dy，直接检验 M9 分别加权修正）
  T6 双斑块聚合规则核验
  T7 带孔斑块：内边界计入周长
  T8 EIRP/EPRE 常数核验（46 dBm 总功率, 1200 子载波, +17 dBi, -2 dB 损耗）
用法: python s60_unit_tests.py   （任意 cwd，不依赖栅格数据）
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from geo_utils import rma_pl, aggregate_perimeter

FC, HB, HUT, H_ENV, W_ENV = 2.6, 30.0, 1.5, 5.0, 20.0
PASS = []


def check(name, got, want, tol=1e-6):
    ok = abs(got - want) <= tol * max(1.0, abs(want))
    PASS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}: got={got:.6f} want={want:.6f}")


# ---- T1 平地链路手算（独立实现 RMa PL1，d2d=1000 < d_bp）----
d2d, dz = 1000.0, HB - HUT
d3d = math.hypot(d2d, dz)
d_bp = 2 * math.pi * HB * HUT * FC * 1e9 / 3e8
t1 = min(0.03 * H_ENV ** 1.72, 10)
t2 = min(0.044 * H_ENV ** 1.72, 14.77)
t3 = 0.002 * math.log10(H_ENV)
pl_hand = (20 * math.log10(40 * math.pi * d3d * FC / 3)
           + t1 * math.log10(d3d) - t2 + t3 * d3d)
pl_code = float(rma_pl(np.array([d2d]), np.array([d3d]), np.array([True]),
                       FC, HB, HUT, H_ENV, W_ENV, True)[0])
check("T1 RMa-LOS PL1 hand-calc", pl_code, pl_hand, tol=1e-9)
print(f"      (d_bp={d_bp:.0f} m, PL1={pl_hand:.2f} dB)")

# ---- T2 NLOS 行为 ----
pl_los = float(rma_pl(np.array([2000.0]), np.array([2000.0]), np.array([True]),
                      FC, HB, HUT, H_ENV, W_ENV, True)[0])
pl_nlos = float(rma_pl(np.array([2000.0]), np.array([2000.0]), np.array([False]),
                       FC, HB, HUT, H_ENV, W_ENV, True)[0])
PASS.append(pl_nlos >= pl_los)
print(f"{'PASS' if pl_nlos >= pl_los else 'FAIL'}  T2a NLOS({pl_nlos:.2f}) >= LOS({pl_los:.2f})")
pl_far = float(rma_pl(np.array([6000.0]), np.array([6000.0]), np.array([False]),
                      FC, HB, HUT, H_ENV, W_ENV, True)[0])
PASS.append(math.isinf(pl_far))
print(f"{'PASS' if math.isinf(pl_far) else 'FAIL'}  T2b NLOS d2d=6000m capped -> inf")
pl_far_nc = float(rma_pl(np.array([6000.0]), np.array([6000.0]), np.array([False]),
                         FC, HB, HUT, H_ENV, W_ENV, False)[0])
PASS.append(math.isfinite(pl_far_nc))
print(f"{'PASS' if math.isfinite(pl_far_nc) else 'FAIL'}  T2c NLOS d2d=6000m nocap -> finite ({pl_far_nc:.1f} dB)")

# ---- T3 d3d 单调性 ----
pl_a = float(rma_pl(np.array([1000.0]), np.array([1000.4]), np.array([True]),
                    FC, HB, HUT, H_ENV, W_ENV, True)[0])
pl_b = float(rma_pl(np.array([1000.0]), np.array([1100.0]), np.array([True]),
                    FC, HB, HUT, H_ENV, W_ENV, True)[0])
PASS.append(pl_b > pl_a)
print(f"{'PASS' if pl_b > pl_a else 'FAIL'}  T3 d3d 1000.4->1100: PL {pl_a:.2f} -> {pl_b:.2f} dB")

# ---- T4 正方形（dx=dy=10）----
bb = np.zeros((20, 20), dtype=np.uint8); bb[2:12, 3:13] = 1
P = aggregate_perimeter(bb, 10.0, 10.0)
A = 100 * 100.0
check("T4a square P", P, 400.0)
check("T4b square compact", 4 * math.pi * A / P ** 2, 4 * math.pi * 10000 / 400 ** 2)

# ---- T5 矩形各向异性（dx=8.68, dy=9.93，模拟 30°N WorldCover 像元）----
bb = np.zeros((30, 40), dtype=np.uint8); bb[5:10, 5:25] = 1   # 5 行 x 20 列
P = aggregate_perimeter(bb, 8.68, 9.93)
P_want = 2 * 5 * 9.93 + 2 * 20 * 8.68          # 垂直边×dy + 水平边×dx
check("T5a rect P (M9 weighted)", P, P_want)
P_old = (2 * 5 + 2 * 20) * (8.68 + 9.93) / 2   # 旧实现（统一均值权重）
print(f"      (旧实现 P={P_old:.1f}，修正后 {P_want:.1f}，差异 {100*(P_want-P_old)/P_old:+.2f}%)")

# ---- T6 双斑块聚合 ----
bb = np.zeros((20, 40), dtype=np.uint8); bb[2:7, 2:7] = 1; bb[10:15, 20:25] = 1
P = aggregate_perimeter(bb, 10.0, 10.0)
check("T6 two-patch aggregate P", P, 400.0)     # 2 × (4×5×10)

# ---- T7 带孔斑块 ----
bb = np.zeros((20, 20), dtype=np.uint8); bb[2:12, 2:12] = 1; bb[6:8, 6:8] = 0
P = aggregate_perimeter(bb, 10.0, 10.0)
check("T7 holed patch P (incl. inner boundary)", P, 400.0 + 80.0)

# ---- T8 EPRE 常数 ----
EIRP = 46 - 10 * math.log10(1200) + 17 - 2
check("T8 EPRE = 30.21 dBm", EIRP, 30.21, tol=1e-3)

print(f"\n{'ALL PASS' if all(PASS) else 'SOME FAILED'}  ({sum(PASS)}/{len(PASS)})")
sys.exit(0 if all(PASS) else 1)
