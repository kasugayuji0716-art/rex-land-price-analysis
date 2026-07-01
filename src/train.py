"""
モデル学習・評価モジュール (Phase B-2, B-3)
LightGBM + Spatial CV による路線価予測モデルを構築する。

目的変数: log(kakaku + 1)  ← 対数変換で右裾の歪みを緩和
評価指標: RMSE / MAE / R²（対数空間）、実価格空間でも報告
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from sklearn.model_selection import GroupKFold, cross_validate
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False


# ── デフォルトパラメータ ──────────────────────────────────────────────────
DEFAULT_PARAMS = {
    "objective":        "regression",
    "metric":           "rmse",
    "n_estimators":     500,
    "learning_rate":    0.05,
    "num_leaves":       63,
    "min_child_samples": 20,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "reg_alpha":        0.1,
    "reg_lambda":       1.0,
    "random_state":     42,
    "n_jobs":           -1,
    "verbose":          -1,
}


def _require_lgb():
    if not HAS_LGB:
        raise ImportError("lightgbm が必要です: pip install lightgbm")


# ── Spatial CV ────────────────────────────────────────────────────────────

def spatial_cv(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    params: dict | None = None,
    n_splits: int = 5,
) -> pd.DataFrame:
    """
    都道府県コードをグループとした Spatial GroupKFold CV を実行する。

    Parameters
    ----------
    X : pd.DataFrame
        特徴量マトリクス
    y : pd.Series
        目的変数（log変換済み）
    groups : pd.Series
        グループラベル（都道府県コード等）
    params : dict | None
        LightGBM パラメータ。None のとき DEFAULT_PARAMS を使用
    n_splits : int
        フォールド数

    Returns
    -------
    pd.DataFrame
        フォール別・集計の評価指標
    """
    _require_lgb()

    p = {**DEFAULT_PARAMS, **(params or {})}
    model = lgb.LGBMRegressor(**p)
    gkf = GroupKFold(n_splits=n_splits)

    fold_results = []
    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups)):
        X_tr, X_te = X.iloc[train_idx], X.iloc[test_idx]
        y_tr, y_te = y.iloc[train_idx], y.iloc[test_idx]

        model.fit(X_tr, y_tr)
        y_pred = model.predict(X_te)

        # 対数空間の指標
        rmse_log = np.sqrt(mean_squared_error(y_te, y_pred))
        mae_log  = mean_absolute_error(y_te, y_pred)
        r2_log   = r2_score(y_te, y_pred)

        # 実価格空間（逆変換）
        y_te_real   = np.expm1(y_te)
        y_pred_real = np.expm1(y_pred)
        rmse_real = np.sqrt(mean_squared_error(y_te_real, y_pred_real))
        mae_real  = mean_absolute_error(y_te_real, y_pred_real)

        fold_results.append({
            "fold":      fold + 1,
            "n_test":    len(test_idx),
            "rmse_log":  round(rmse_log, 5),
            "mae_log":   round(mae_log, 5),
            "r2_log":    round(r2_log, 4),
            "rmse_real": round(rmse_real, 0),
            "mae_real":  round(mae_real, 0),
        })

    df = pd.DataFrame(fold_results)
    # 集計行を追加
    summary = df.drop(columns="fold").agg(["mean", "std"]).round(4)
    summary.index = ["mean", "std"]
    summary.insert(0, "fold", summary.index)
    return pd.concat([df, summary], ignore_index=True)


# ── フル学習 ─────────────────────────────────────────────────────────────

def train(
    X: pd.DataFrame,
    y: pd.Series,
    params: dict | None = None,
) -> "lgb.LGBMRegressor":
    """
    全データでモデルを学習して返す。

    Parameters
    ----------
    X : pd.DataFrame
    y : pd.Series
        目的変数（log変換済み）
    params : dict | None

    Returns
    -------
    lgb.LGBMRegressor
    """
    _require_lgb()
    p = {**DEFAULT_PARAMS, **(params or {})}
    model = lgb.LGBMRegressor(**p)
    model.fit(X, y)
    return model


# ── 特徴量重要度 ──────────────────────────────────────────────────────────

def feature_importance(
    model: "lgb.LGBMRegressor",
    X: pd.DataFrame,
    importance_type: str = "gain",
) -> pd.Series:
    """
    特徴量重要度を降順で返す。

    Parameters
    ----------
    importance_type : str
        "gain"（情報利得）または "split"（分割回数）
    """
    _require_lgb()
    imp = model.booster_.feature_importance(importance_type=importance_type)
    return (
        pd.Series(imp, index=X.columns, name=importance_type)
        .sort_values(ascending=False)
    )


# ── SHAP ─────────────────────────────────────────────────────────────────

def compute_shap(
    model: "lgb.LGBMRegressor",
    X: pd.DataFrame,
    sample_n: int = 500,
) -> tuple[np.ndarray, "shap.Explainer"]:
    """
    SHAP 値を計算して返す。

    Parameters
    ----------
    sample_n : int
        計算に使うサンプル数（大規模データでのコスト削減用）

    Returns
    -------
    shap_values : np.ndarray  shape=(n, features)
    explainer   : shap.Explainer
    """
    if not HAS_SHAP:
        raise ImportError("shap が必要です: pip install shap")

    X_sample = X.sample(min(sample_n, len(X)), random_state=42)
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_sample)
    return shap_values, explainer, X_sample


# ── 評価指標サマリー ──────────────────────────────────────────────────────

def evaluate(
    model: "lgb.LGBMRegressor",
    X: pd.DataFrame,
    y: pd.Series,
) -> dict:
    """
    モデルの予測精度指標を返す（生データは出力しない）。
    """
    _require_lgb()
    y_pred_log = model.predict(X)
    y_real     = np.expm1(y)
    y_pred_real = np.expm1(y_pred_log)

    return {
        "n":          len(y),
        "rmse_log":   round(np.sqrt(mean_squared_error(y, y_pred_log)), 5),
        "mae_log":    round(mean_absolute_error(y, y_pred_log), 5),
        "r2_log":     round(r2_score(y, y_pred_log), 4),
        "rmse_real":  round(np.sqrt(mean_squared_error(y_real, y_pred_real)), 1),
        "mae_real":   round(mean_absolute_error(y_real, y_pred_real), 1),
        "mape":       round(
            np.mean(np.abs((y_real - y_pred_real) / y_real.replace(0, np.nan))) * 100, 2
        ),
    }
