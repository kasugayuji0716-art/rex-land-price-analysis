"""
合成データ生成スクリプト
REX地価コンテンツデータセット（nouhin_line）のスキーマを模した偽物データを生成する。
実データには一切触れない。生成データは開発・テスト専用。

使用方法:
    python src/make_synthetic.py --n 10000 --out data_synthetic/nouhin_line_synthetic.shp
    python src/make_synthetic.py --n 1000 --out data_synthetic/nouhin_line_synthetic.parquet
"""

import argparse
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString
from pathlib import Path


# ── コード表（仕様書 別表より） ────────────────────────────────────────
CHIKUKBN_CODES = [1, 2, 3, 4, 5, 6, 7]       # 地区区分
CHIKUKBN_NAMES = {
    1: "ビル街地区",
    2: "高度商業地区",
    3: "繁華街地区",
    4: "普通商業・併用住宅地区",
    5: "普通住宅地区",
    6: "中小工場地区",
    7: "大工場地区",
}
SWARI_CODES = [1, 2, 3, 4, 5, 6, 7, 8]       # 借地権割合（1=90%〜8=20%）

# ── 価格レンジ（地区区分別の大まかな相場、単位: 千円/㎡） ────────────
KAKAKU_RANGE = {
    1: (5000, 50000),   # ビル街
    2: (2000, 20000),   # 高度商業
    3: (1000, 10000),   # 繁華街
    4:  (200,  3000),   # 普通商業・併用住宅
    5:   (50,  1000),   # 普通住宅
    6:   (30,   500),   # 中小工場
    7:   (20,   300),   # 大工場
}

# ── 地区区分ごとの出現比率（全国統計の概算） ─────────────────────────
CHIKUKBN_WEIGHTS = [0.02, 0.05, 0.05, 0.15, 0.60, 0.08, 0.05]

# ── 三大都市圏のバウンディングボックス（緯度, 経度）────────────────────
REGIONS = {
    "tokyo":  {"lat": (35.4, 35.9), "lon": (139.3, 139.9), "weight": 0.40},
    "osaka":  {"lat": (34.4, 34.8), "lon": (135.2, 135.7), "weight": 0.25},
    "nagoya": {"lat": (34.9, 35.4), "lon": (136.7, 137.1), "weight": 0.15},
    "others": {"lat": (31.0, 43.0), "lon": (130.0, 145.0), "weight": 0.20},
}

# ── 市区町村コードサンプル（JIS X 0402） ──────────────────────────────
SAMPLE_CODES = [
    13101, 13102, 13103, 13104, 13105,  # 東京都特別区
    27100, 27102, 27103, 27104,          # 大阪市
    23100, 23101, 23102,                 # 名古屋市
    11000, 14000, 28000,                 # 埼玉・神奈川・兵庫
]


def _make_linestring(lat_center: float, lon_center: float, rng: np.random.Generator) -> LineString:
    """矢線（LineString）を生成。長さは数m〜数百m相当のランダムな線分。"""
    # 緯度経度の微小オフセット（約10m〜500m相当）
    offset = rng.uniform(0.0001, 0.005)
    angle = rng.uniform(0, 2 * np.pi)
    dx = offset * np.cos(angle)
    dy = offset * np.sin(angle)
    start = (lon_center, lat_center)
    end = (lon_center + dx, lat_center + dy)
    # 中間点を1〜2点追加（point_cnt=2〜4）
    n_mid = rng.integers(0, 3)
    coords = [start]
    for _ in range(n_mid):
        t = rng.uniform(0, 1)
        coords.append((lon_center + t * dx, lat_center + t * dy))
    coords.append(end)
    return LineString(coords)


def _sample_location(rng: np.random.Generator) -> tuple[float, float]:
    """地域ウェイトに従って緯度・経度をサンプリング。"""
    region_keys = list(REGIONS.keys())
    weights = [REGIONS[k]["weight"] for k in region_keys]
    chosen = rng.choice(region_keys, p=weights)
    r = REGIONS[chosen]
    lat = rng.uniform(*r["lat"])
    lon = rng.uniform(*r["lon"])
    return lat, lon


def generate(n: int, seed: int = 42) -> gpd.GeoDataFrame:
    """
    n件の合成データを生成して GeoDataFrame で返す。

    Parameters
    ----------
    n : int
        生成件数
    seed : int
        乱数シード（再現性のため）
    """
    rng = np.random.default_rng(seed)

    # ── 地区区分（先にサンプリングして価格レンジを決める）
    chikukbn = rng.choice(CHIKUKBN_CODES, size=n, p=CHIKUKBN_WEIGHTS).astype(np.int16)

    # ── 当年価格（地区区分ごとのレンジから対数一様分布でサンプリング）
    kakaku = np.zeros(n, dtype=np.int32)
    for code in CHIKUKBN_CODES:
        mask = chikukbn == code
        lo, hi = KAKAKU_RANGE[code]
        kakaku[mask] = rng.integers(lo, hi, size=mask.sum())

    # ── 前年価格（当年から±10%以内の変動）
    pre1_change = rng.uniform(-0.10, 0.10, size=n)
    pre1_kakak = np.maximum(1, (kakaku * (1 + pre1_change)).astype(np.int32))

    # ── 前前年価格（前年からさらに±10%以内の変動）
    pre2_change = rng.uniform(-0.10, 0.10, size=n)
    pre2_kakak = np.maximum(1, (pre1_kakak * (1 + pre2_change)).astype(np.int32))

    # ── 削除矢線を5%混入（flgdraw=False）
    is_deleted = rng.random(n) < 0.05

    # ── 市区町村コード
    code = rng.choice(SAMPLE_CODES, size=n).astype(np.int32)

    # ── linkcode（市区町村内で1〜9999999）
    linkcode = rng.integers(1, 9999999, size=n).astype(np.int32)

    # ── serial_id = code * 10_000_000 + linkcode
    serial_id = (code.astype(np.int64) * 10_000_000 + linkcode).astype(np.int64)

    # ── 借地権割合（商業系は高め）
    p_commercial = [0.30, 0.30, 0.20, 0.10, 0.05, 0.03, 0.01, 0.01]
    p_residential = [0.01, 0.05, 0.10, 0.20, 0.35, 0.20, 0.07, 0.02]
    is_commercial = np.isin(chikukbn, [1, 2, 3])
    swari = np.array([
        rng.choice(SWARI_CODES, p=p_commercial if is_commercial[i] else p_residential)
        for i in range(n)
    ], dtype=np.int16)

    # ── ジオメトリ（矢線 LineString）
    geometries = []
    for i in range(n):
        lat, lon = _sample_location(rng)
        geom = _make_linestring(lat, lon, rng)
        geometries.append(geom)

    # ── 削除矢線の属性を仕様書通りに上書き
    kakaku[is_deleted] = 0
    swari[is_deleted] = 0
    chikukbn[is_deleted] = 0

    # ── DataFrame 組み立て
    df = pd.DataFrame({
        "serial_id":  serial_id,
        "nendo":      np.full(n, 2022, dtype=np.int32),
        "code":       code,
        "linkcode":   linkcode,
        "lineno":     np.zeros(n, dtype=np.int32),       # 変更なし想定
        "jushoname":  [f"合成市区町村{c}" for c in code],
        "kakaku":     kakaku,
        "chikukbn":   chikukbn,
        "swari":      swari,
        "kigo_1":     rng.integers(0, 7, size=n).astype(np.int16),
        "kigo_2":     rng.integers(0, 8, size=n).astype(np.int16),
        "marknum":    rng.integers(0, 5, size=n).astype(np.int16),
        "markangle":  rng.integers(0, 24, size=n).astype(np.int16),
        "pre1_nendo": np.full(n, 2021, dtype=np.int32),
        "pre1_kakak": pre1_kakak,
        "pre1_chiku": chikukbn,                           # 変動なし想定
        "pre1_swari": swari,
        "pre2_nendo": np.full(n, 2020, dtype=np.int32),
        "pre2_kakak": pre2_kakak,
        "pre2_chiku": chikukbn,
        "pre2_swari": swari,
        "prevlink":   [""] * n,
        "nextlink":   [""] * n,
        "point_cnt":  [len(g.coords) for g in geometries],
        "color":      np.full(n, 0, dtype=np.int32),
        "pen_style":  rng.choice([20, 40], size=n).astype(np.int32),
        "pen_width":  np.full(n, 2, dtype=np.int32),
        "arrow":      np.full(n, 4, dtype=np.int32),
        "flgdraw":    ~is_deleted,
    })

    gdf = gpd.GeoDataFrame(df, geometry=geometries, crs="EPSG:4326")
    return gdf


def main():
    parser = argparse.ArgumentParser(description="REX合成データ生成")
    parser.add_argument("--n",    type=int,  default=10_000, help="生成件数（デフォルト: 10000）")
    parser.add_argument("--seed", type=int,  default=42,     help="乱数シード")
    parser.add_argument(
        "--out",
        type=str,
        default="data_synthetic/nouhin_line_synthetic.parquet",
        help="出力パス（.parquet または .shp）",
    )
    args = parser.parse_args()

    print(f"合成データ生成: n={args.n}, seed={args.seed}")
    gdf = generate(n=args.n, seed=args.seed)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.suffix == ".parquet":
        gdf.to_parquet(out_path)
    elif out_path.suffix == ".shp":
        gdf.to_file(out_path)
    else:
        raise ValueError(f"未対応の拡張子: {out_path.suffix}（.parquet または .shp を指定）")

    print(f"保存完了: {out_path}  ({len(gdf):,}件)")
    # 件数・スキーマのみ出力（生レコードは出さない）
    print("\n--- スキーマ確認 ---")
    print(gdf.dtypes)
    print(f"\n件数: {len(gdf):,}")
    print(f"削除矢線(flgdraw=False): {(~gdf['flgdraw']).sum():,}")
    print(f"CRS: {gdf.crs}")
    print(f"ジオメトリ型: {gdf.geom_type.unique()}")


if __name__ == "__main__":
    main()
