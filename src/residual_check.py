"""
残差診断モジュール (Phase B-4)
LightGBM モデルの残差に対して空間的自己相関・グループ別偏りを診断する。

分析しないと「空間予測モデルとして優れている」とは主張できない。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from spatial_autocorr import global_moran, build_weights, HAS_PYSAL
except ImportError:
    HAS_PYSAL = False

from rex_io import CHIKUKBN_LABEL


def add_residuals(
    gdf: gpd.GeoDataFrame,
    y_true: pd.Series,
    y_pred: np.ndarray,
    log_scale: bool = True,
) -> gpd.GeoDataFrame:
    """
    残差を GeoDataFrame に追加する。

    Parameters
    ----------
    log_scale : bool
        True のとき対数空間の残差。False のとき実価格空間。

    追加列:
        y_pred      : 予測値
        residual    : 残差（y_true - y_pred）
        abs_error   : 絶対誤差
        rel_error   : 相対誤差（%）
    """
    gdf = gdf.copy()
    gdf["y_true"] = y_true.values
    gdf["y_pred"] = y_pred

    if log_scale:
        gdf["residual"]  = y_true.values - y_pred
        gdf["abs_error"] = np.abs(gdf["residual"])
        # 実価格空間での相対誤差
        y_real      = np.expm1(y_true.values)
        y_pred_real = np.expm1(y_pred)
        gdf["rel_error"] = np.abs(y_real - y_pred_real) / np.where(y_real > 0, y_real, np.nan) * 100
    else:
        gdf["residual"]  = y_true.values - y_pred
        gdf["abs_error"] = np.abs(gdf["residual"])
        gdf["rel_error"] = gdf["abs_error"] / np.where(y_true.values > 0, y_true.values, np.nan) * 100

    return gdf


def residual_moran(
    gdf: gpd.GeoDataFrame,
    residual_col: str = "residual",
) -> dict:
    """
    残差の Global Moran's I を計算する。

    有意（p < 0.05）なら空間構造が取り残されており、
    モデル改善（空間ラグ追加・GWR 比較等）が必要。
    """
    if not HAS_PYSAL:
        return {"error": "libpysal/esda が未インストールです"}

    gdf_proj = gdf.to_crs(epsg=3857)
    result = global_moran(gdf_proj, col=residual_col)
    result["interpretation"] = (
        "⚠️ 空間構造が残っています（モデル改善を検討）"
        if result["significant"]
        else "✅ 残差に有意な空間自己相関なし"
    )
    return result


def residual_by_chikukbn(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """地区区分別の残差統計を返す。"""
    gdf = gdf.copy()
    gdf["chikukbn_label"] = gdf["chikukbn"].map(CHIKUKBN_LABEL)

    return (
        gdf.groupby("chikukbn_label")[["residual", "abs_error", "rel_error"]]
        .agg(["count", "mean", "median", "std"])
        .round(3)
    )


def residual_by_prefecture(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """都道府県別の残差統計を返す。"""
    gdf = gdf.copy()
    gdf["pref_code"] = (gdf["code"] // 1000).astype(int)

    return (
        gdf.groupby("pref_code")
        .agg(
            count=("residual", "count"),
            residual_mean=("residual", "mean"),
            abs_error_median=("abs_error", "median"),
            rel_error_median=("rel_error", "median"),
        )
        .round(3)
        .sort_values("abs_error_median", ascending=False)
    )


def plot_residuals(
    gdf: gpd.GeoDataFrame,
    residual_col: str = "residual",
    figsize: tuple = (15, 5),
) -> None:
    """
    残差の診断プロット（3パネル）を表示する。

    Panel 1: 残差の分布（ヒストグラム）
    Panel 2: 予測値 vs 残差（散布図）
    Panel 3: 実測値 vs 予測値（散布図）
    """
    fig, axes = plt.subplots(1, 3, figsize=figsize)

    res = gdf[residual_col].dropna()
    y_true = gdf["y_true"].dropna()
    y_pred = gdf["y_pred"].dropna()

    # 1. 残差の分布
    axes[0].hist(res, bins=50, color="steelblue", edgecolor="white")
    axes[0].axvline(0, color="red", linestyle="--")
    axes[0].axvline(res.mean(), color="orange", linestyle="-",
                    label=f"mean={res.mean():.3f}")
    axes[0].set_title("残差の分布")
    axes[0].set_xlabel("残差")
    axes[0].set_ylabel("件数")
    axes[0].legend()

    # 2. 予測値 vs 残差
    axes[1].scatter(y_pred, gdf[residual_col], alpha=0.3, s=10, color="steelblue")
    axes[1].axhline(0, color="red", linestyle="--")
    axes[1].set_title("予測値 vs 残差")
    axes[1].set_xlabel("予測値（log）")
    axes[1].set_ylabel("残差")

    # 3. 実測値 vs 予測値
    mn = min(y_true.min(), y_pred.min())
    mx = max(y_true.max(), y_pred.max())
    axes[2].scatter(y_true, y_pred, alpha=0.3, s=10, color="coral")
    axes[2].plot([mn, mx], [mn, mx], "k--", linewidth=1, label="完全予測線")
    axes[2].set_title("実測値 vs 予測値")
    axes[2].set_xlabel("実測値（log）")
    axes[2].set_ylabel("予測値（log）")
    axes[2].legend()

    plt.tight_layout()
    plt.show()


def full_diagnosis(
    gdf: gpd.GeoDataFrame,
    y_true: pd.Series,
    y_pred: np.ndarray,
) -> None:
    """
    残差診断を一括実行してレポートを出力する。

    1. 残差の追加
    2. Moran's I
    3. 地区区分別残差
    4. 残差プロット
    """
    gdf = add_residuals(gdf, y_true, y_pred)

    print("=" * 50)
    print("【残差診断レポート】")
    print("=" * 50)

    print("\n▶ 残差の基本統計")
    res = gdf["residual"]
    print(f"  平均   : {res.mean():.4f}")
    print(f"  標準偏差: {res.std():.4f}")
    print(f"  中央値  : {res.median():.4f}")
    print(f"  |残差| > 0.5 の割合: {(res.abs() > 0.5).mean() * 100:.1f}%")

    print("\n▶ 空間的自己相関（残差のMoran's I）")
    moran_res = residual_moran(gdf)
    for k, v in moran_res.items():
        print(f"  {k}: {v}")

    print("\n▶ 地区区分別の残差（abs_error の中央値）")
    by_chiku = residual_by_chikukbn(gdf)
    print(by_chiku["abs_error"]["median"].sort_values(ascending=False).to_string())

    print("\n▶ 残差プロット")
    plot_residuals(gdf)
