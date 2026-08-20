# -*- coding: utf-8 -*-
"""共享纯函数：RMa 路径损耗 + 聚合周长（供 s20b_coverage_v4 / s55_framed_morph / s60 单元测试复用）"""
import math
import numpy as np


def rma_pl(d2d, d3d, los, FC, HB, HUT, H_ENV, W_ENV, NLOS_CAP=True):
    """3GPP TR 38.901 RMa 路径损耗。d3d 必须为站-目标真实三维距离（调用方计算）。"""
    d2d = np.maximum(d2d, 10.0)
    d3d = np.maximum(d3d, 10.0)
    d_bp = 2 * math.pi * HB * HUT * FC * 1e9 / 3e8
    t1 = min(0.03 * H_ENV ** 1.72, 10)
    t2 = min(0.044 * H_ENV ** 1.72, 14.77)
    t3 = 0.002 * math.log10(H_ENV)
    pl1 = 20 * np.log10(40 * math.pi * d3d * FC / 3) + t1 * np.log10(d3d) - t2 + t3 * d3d
    pl2 = (20 * math.log10(40 * math.pi * d_bp * FC / 3) + t1 * math.log10(d_bp) - t2
           + t3 * d_bp + 40 * np.log10(d3d / d_bp))
    pl_los = np.where(d2d <= d_bp, pl1, pl2)
    pl_nlos = (161.04 - 7.1 * math.log10(W_ENV) + 7.5 * math.log10(H_ENV)
               - (24.37 - 3.7 * (H_ENV / HB) ** 2) * math.log10(HB)
               + (43.42 - 3.1 * math.log10(HB)) * (np.log10(d3d) - 3)
               + 20 * math.log10(FC) - (3.2 * (math.log10(11.75 * HUT)) ** 2 - 4.97))
    pl = np.where(los, pl_los, np.maximum(pl_los, pl_nlos))
    if NLOS_CAP:  # RMa NLOS 标准适用范围 d2D ≤ 5 km；超出视为不适用
        pl = np.where((~los) & (d2d > 5000.0), np.inf, pl)
    return pl


def aggregate_perimeter(bb, dx_m, dy_m):
    """聚合暴露边周长：四邻接；垂直边×dy_m、水平边×dx_m 分别加权；
    孔洞内边界经差分自然计入；栅格边界作保险项。"""
    return float((bb[:, :-1] != bb[:, 1:]).sum() * dy_m
                 + (bb[:-1, :] != bb[1:, :]).sum() * dx_m
                 + (bb[0, :].sum() + bb[-1, :].sum()) * dx_m
                 + (bb[:, 0].sum() + bb[:, -1].sum()) * dy_m)
