"""
src/io.py のテスト
合成データ（data_synthetic/）のみを使用する。実データには触れない。
"""

import sys
from pathlib import Path
import numpy as np
import geopandas as gpd
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from make_synthetic import generate
from rex_io import (
    load,
    load_and_prepare,
    add_change_rate,
    add_labels,
    filter_active,
    summary_stats,
    chikukbn_counts,
    CHIKUKBN_LABEL,
    SWARI_RATIO,
)

# ── フィクスチャ ──────────────────────────────────────────────────────────

N = 500

@pytest.fixture(scope="module")
def synthetic_parquet(tmp_path_factory) -> Path:
    """合成データをParquetとして一時保存し、パスを返す。"""
    p = tmp_path_factory.mktemp("data") / "test.parquet"
    gdf = generate(n=N, seed=0)
    gdf.to_parquet(p)
    return p


@pytest.fixture(scope="module")
def synthetic_gdf() -> gpd.GeoDataFrame:
    """メモリ上の合成 GeoDataFrame（削除矢線込み）。"""
    return generate(n=N, seed=0)


# ── load() のテスト ───────────────────────────────────────────────────────

class TestLoad:
    def test_load_parquet_returns_geodataframe(self, synthetic_parquet):
        gdf = load(synthetic_parquet, drop_deleted=False)
        assert isinstance(gdf, gpd.GeoDataFrame)

    def test_load_parquet_row_count(self, synthetic_parquet):
        gdf = load(synthetic_parquet, drop_deleted=False)
        assert len(gdf) == N

    def test_load_drops_deleted_by_default(self, synthetic_parquet):
        gdf_all = load(synthetic_parquet, drop_deleted=False)
        gdf_clean = load(synthetic_parquet, drop_deleted=True)
        deleted = (~gdf_all["flgdraw"]).sum()
        assert len(gdf_clean) == len(gdf_all) - deleted

    def test_load_crs_conversion(self, synthetic_parquet):
        gdf = load(synthetic_parquet, drop_deleted=False, crs=6677)
        assert gdf.crs.to_epsg() == 6677

    def test_load_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load("non_existent.parquet")

    def test_load_unsupported_extension(self, tmp_path):
        p = tmp_path / "data.csv"
        p.write_text("dummy")
        with pytest.raises(ValueError):
            load(p)


# ── add_change_rate() のテスト ────────────────────────────────────────────

class TestAddChangeRate:
    def test_columns_added(self, synthetic_gdf):
        gdf = add_change_rate(synthetic_gdf)
        for col in ["change_y1", "change_y2", "change_2y"]:
            assert col in gdf.columns

    def test_change_rate_formula(self, synthetic_gdf):
        gdf = filter_active(synthetic_gdf)
        gdf = add_change_rate(gdf)
        expected = (gdf["kakaku"] - gdf["pre1_kakak"]) / gdf["pre1_kakak"] * 100
        pd.testing.assert_series_equal(
            gdf["change_y1"].dropna(),
            expected.dropna(),
            check_names=False,
        )

    def test_zero_price_yields_nan(self):
        """kakaku=0 の行は変化率が NaN になること。"""
        gdf = generate(n=10, seed=99)
        gdf.loc[gdf.index[0], "pre1_kakak"] = 0
        gdf = add_change_rate(gdf)
        assert np.isnan(gdf.loc[gdf.index[0], "change_y1"])

    def test_original_not_modified(self, synthetic_gdf):
        """元の GeoDataFrame を変更しないこと。"""
        before_cols = list(synthetic_gdf.columns)
        add_change_rate(synthetic_gdf)
        assert list(synthetic_gdf.columns) == before_cols


# ── add_labels() のテスト ─────────────────────────────────────────────────

class TestAddLabels:
    def test_columns_added(self, synthetic_gdf):
        gdf = add_labels(synthetic_gdf)
        assert "chikukbn_label" in gdf.columns
        assert "swari_ratio" in gdf.columns

    def test_chikukbn_label_values(self, synthetic_gdf):
        gdf = add_labels(filter_active(synthetic_gdf))
        valid_labels = set(CHIKUKBN_LABEL.values())
        assert set(gdf["chikukbn_label"].dropna()).issubset(valid_labels)

    def test_swari_ratio_range(self, synthetic_gdf):
        gdf = add_labels(filter_active(synthetic_gdf))
        ratios = gdf["swari_ratio"].dropna()
        assert (ratios >= 0.2).all() and (ratios <= 0.9).all()


# ── filter_active() のテスト ──────────────────────────────────────────────

class TestFilterActive:
    def test_no_zero_kakaku(self, synthetic_gdf):
        gdf = filter_active(synthetic_gdf)
        assert (gdf["kakaku"] > 0).all()

    def test_no_zero_chikukbn(self, synthetic_gdf):
        gdf = filter_active(synthetic_gdf)
        assert (gdf["chikukbn"] > 0).all()


# ── summary_stats() / chikukbn_counts() のテスト ─────────────────────────

class TestStats:
    def test_summary_stats_returns_dataframe(self, synthetic_gdf):
        gdf = load_and_prepare.__wrapped__(synthetic_gdf) if hasattr(load_and_prepare, "__wrapped__") else (
            add_change_rate(add_labels(filter_active(synthetic_gdf)))
        )
        stats = summary_stats(gdf)
        assert isinstance(stats, pd.DataFrame)
        assert "mean" in stats.columns

    def test_chikukbn_counts_returns_series(self, synthetic_gdf):
        counts = chikukbn_counts(filter_active(synthetic_gdf))
        assert isinstance(counts, pd.Series)
        assert counts.sum() <= N


# ── load_and_prepare() の統合テスト ──────────────────────────────────────

class TestLoadAndPrepare:
    def test_pipeline_output_columns(self, synthetic_parquet):
        gdf = load_and_prepare(synthetic_parquet)
        for col in ["change_y1", "change_y2", "change_2y",
                    "chikukbn_label", "swari_ratio"]:
            assert col in gdf.columns

    def test_pipeline_no_deleted_rows(self, synthetic_parquet):
        gdf = load_and_prepare(synthetic_parquet)
        assert gdf["flgdraw"].all()

    def test_pipeline_no_zero_price(self, synthetic_parquet):
        gdf = load_and_prepare(synthetic_parquet)
        assert (gdf["kakaku"] > 0).all()

    def test_pipeline_geometry_intact(self, synthetic_parquet):
        gdf = load_and_prepare(synthetic_parquet)
        assert gdf.geometry.is_valid.all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
