"""
データ読み込み・前処理モジュール
REX地価コンテンツデータセット（nouhin_line）の読み込み・クレンジング・変化率計算を担う。

実データには触れない。スクリプトはデータパスを引数で受け取る設計。
生レコードの出力は行わない（集計統計のみ許可）。
"""

from __future__ import annotations
from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np


# ── 型定義 ────────────────────────────────────────────────────────────────
DTYPE_MAP: dict[str, str] = {
    "serial_id":  "Int64",
    "nendo":      "Int32",
    "code":       "Int32",
    "linkcode":   "Int32",
    "lineno":     "Int32",
    "kakaku":     "Int32",
    "chikukbn":   "Int16",
    "swari":      "Int16",
    "kigo_1":     "Int16",
    "kigo_2":     "Int16",
    "marknum":    "Int16",
    "markangle":  "Int16",
    "pre1_nendo": "Int32",
    "pre1_kakak": "Int32",
    "pre1_chiku": "Int16",
    "pre1_swari": "Int16",
    "pre2_nendo": "Int32",
    "pre2_kakak": "Int32",
    "pre2_chiku": "Int16",
    "pre2_swari": "Int16",
    "point_cnt":  "Int32",
    "color":      "Int32",
    "pen_style":  "Int32",
    "pen_width":  "Int32",
    "arrow":      "Int32",
}

# 分析に使う列（可視化・描画用の列は除外）
ANALYSIS_COLS = [
    "serial_id", "nendo", "code", "linkcode", "lineno", "jushoname",
    "kakaku", "chikukbn", "swari", "kigo_1", "kigo_2", "marknum", "markangle",
    "pre1_nendo", "pre1_kakak", "pre1_chiku", "pre1_swari",
    "pre2_nendo", "pre2_kakak", "pre2_chiku", "pre2_swari",
    "prevlink", "nextlink", "flgdraw", "geometry",
]

# 地区区分のラベル
CHIKUKBN_LABEL = {
    0: "削除",
    1: "ビル街地区",
    2: "高度商業地区",
    3: "繁華街地区",
    4: "普通商業・併用住宅地区",
    5: "普通住宅地区",
    6: "中小工場地区",
    7: "大工場地区",
}

# 借地権割合のラベル（コード → 割合）
SWARI_RATIO = {0: None, 1: 0.9, 2: 0.8, 3: 0.7, 4: 0.6, 5: 0.5, 6: 0.4, 7: 0.3, 8: 0.2}


# ── 読み込み ──────────────────────────────────────────────────────────────

def load(
    path: str | Path,
    *,
    drop_deleted: bool = True,
    cols: list[str] | None = None,
    crs: int | None = None,
) -> gpd.GeoDataFrame:
    """
    Shapefile または GeoParquet を読み込み、基本的なクレンジングを施す。

    Parameters
    ----------
    path : str | Path
        入力ファイルパス（.shp または .parquet）
    drop_deleted : bool
        True のとき削除矢線（flgdraw=False）を除外する（デフォルト True）
    cols : list[str] | None
        読み込む列名のリスト。None のとき ANALYSIS_COLS を使用
    crs : int | None
        変換先の EPSG コード。None のとき変換しない

    Returns
    -------
    gpd.GeoDataFrame
        クレンジング済みの GeoDataFrame
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {path}")

    read_cols = cols or ANALYSIS_COLS

    if path.suffix == ".parquet":
        gdf = gpd.read_parquet(path, columns=read_cols)
    elif path.suffix in (".shp", ".gpkg"):
        gdf = gpd.read_file(path, engine="pyogrio", columns=read_cols)
    else:
        raise ValueError(f"未対応の拡張子: {path.suffix}（.parquet / .shp / .gpkg を指定）")

    gdf = _cast_dtypes(gdf)

    # CRS が未設定の場合は EPSG:4326 を仮定（REX データは WGS84）
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)

    if drop_deleted:
        before = len(gdf)
        gdf = gdf[gdf["flgdraw"]].copy()
        n_dropped = before - len(gdf)
        if n_dropped > 0:
            print(f"削除矢線を除外: {n_dropped:,}件 → 残り {len(gdf):,}件")

    if crs is not None:
        gdf = gdf.to_crs(epsg=crs)

    return gdf


def _cast_dtypes(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """数値列の dtype を最適化する（メモリ削減）。"""
    for col, dtype in DTYPE_MAP.items():
        if col in gdf.columns:
            gdf[col] = gdf[col].astype(dtype)
    return gdf


# ── 前処理 ────────────────────────────────────────────────────────────────

def add_change_rate(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    年次変化率を計算して列を追加する。

    追加列:
        change_y1 : 当年 vs 前年の変化率（%）
        change_y2 : 前年 vs 前前年の変化率（%）
        change_2y : 当年 vs 前前年の変化率（%）

    価格が 0 の行（削除済み矢線の混入等）は NaN とする。
    """
    gdf = gdf.copy()

    def _rate(a: pd.Series, b: pd.Series) -> pd.Series:
        """(a - b) / b * 100。b=0 のとき NaN。"""
        return (a - b) / b.replace(0, np.nan) * 100

    gdf["change_y1"] = _rate(gdf["kakaku"], gdf["pre1_kakak"])
    gdf["change_y2"] = _rate(gdf["pre1_kakak"], gdf["pre2_kakak"])
    gdf["change_2y"] = _rate(gdf["kakaku"], gdf["pre2_kakak"])

    return gdf


def add_labels(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    地区区分・借地権割合の数値コードを人間が読めるラベルに変換した列を追加する。

    追加列:
        chikukbn_label : 地区区分の日本語名
        swari_ratio    : 借地権割合（0.3〜0.9の実数）
    """
    gdf = gdf.copy()
    gdf["chikukbn_label"] = gdf["chikukbn"].map(CHIKUKBN_LABEL)
    gdf["swari_ratio"] = gdf["swari"].map(SWARI_RATIO)
    return gdf


def filter_active(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """価格が正（kakaku > 0）かつ 地区区分が有効（chikukbn > 0）の行のみ残す。"""
    mask = (gdf["kakaku"] > 0) & (gdf["chikukbn"] > 0)
    return gdf[mask].copy()


def summary_stats(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    集計統計を返す（生レコードは出力しない）。

    Returns
    -------
    pd.DataFrame
        数値列の件数・平均・標準偏差・分位数
    """
    num_cols = ["kakaku", "pre1_kakak", "pre2_kakak",
                "change_y1", "change_y2", "change_2y",
                "chikukbn", "swari"]
    existing = [c for c in num_cols if c in gdf.columns]
    return gdf[existing].describe().T


def chikukbn_counts(gdf: gpd.GeoDataFrame) -> pd.Series:
    """地区区分別の件数を返す。"""
    return (
        gdf["chikukbn"]
        .map(CHIKUKBN_LABEL)
        .value_counts()
        .rename("件数")
    )


# ── パイプライン ──────────────────────────────────────────────────────────

def load_and_prepare(
    path: str | Path,
    *,
    crs: int | None = None,
) -> gpd.GeoDataFrame:
    """
    読み込み → 削除矢線除外 → 変化率計算 → ラベル付与 を一括実行する。

    Parameters
    ----------
    path : str | Path
        入力ファイルパス
    crs : int | None
        変換先 EPSG コード（例: 6677 = JGD2011 平面直角9系）

    Returns
    -------
    gpd.GeoDataFrame
        分析すぐに使える状態の GeoDataFrame
    """
    gdf = load(path, drop_deleted=True, crs=crs)
    gdf = filter_active(gdf)
    gdf = add_change_rate(gdf)
    gdf = add_labels(gdf)
    return gdf
