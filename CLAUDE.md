# CLAUDE.md — REX地価コンテンツデータセット 分析プロジェクト

## プロジェクト概要

- 題材: NII IDR「REX地価コンテンツデータセット」（相続税路線価）
- データ: シェイプ形式、2020/2021/2022年版、全国約230万矢線、約15.4GB
- 属性: 路線価格 / 路線価矢線(ジオメトリ) / 借地権割合 / 地区区分 / 地区記号詳細 / 緯度経度
- 実データパス: `/path/to/REX_data/2022/nouhin_line_2022.shp`
- スタック: Python, GeoPandas(+pyogrio), shapely, pandas, scikit-learn, LightGBM, DuckDB(spatial)

---

## 【最重要】データ取り扱いポリシー — 絶対厳守

REXデータは NII IDR 利用許諾契約に基づくライセンスデータ。
**第三者サービス（クラウドAI含む）への送信・開示は契約違反。**

### 実データの保管方針

- REXの実データはこのリポジトリには置かない（`data/` ディレクトリ自体が存在しない）
- 実データはリポジトリ外（`/path/to/REX_data/`）で管理
- スクリプトは実データパスを引数で受け取る設計にする

### 禁止事項

1. 実データファイルを read / open / cat / view / ogrinfo 等で中身を読むこと
2. 生のレコードを標準出力・ログ・コンテキストに出すコードを書く／実行すること
   - `gdf.head()`, `print(行)`, feature dump は禁止
3. 実データに対してスクリプトを直接実行すること

### 許可される操作

- スキーマ・件数・集計統計（min/max/mean/分布）などの集約値の取得
- `data_synthetic/` の合成データに対する開発・テスト
- グラフ・モデル指標・集計結果（生レコードを含まない出力）の共有

### 作業分担

- **Claudeが書く / ユーザーが実行する** — 実データに触れるスクリプトはこの分担を守る
- 実データの中身を知る必要が生じたら、**ユーザーに集計統計のみ提供を依頼する**
  （実データを貼るよう求めてはいけない）

---

## ディレクトリ構成

```
data_analysis/
├── CLAUDE.md
├── README.md
├── .gitignore
├── requirements.txt
├── data_synthetic/          # 合成データ（開発・テスト用）
├── src/
│   ├── rex_io.py            # データ読み込み・前処理（※io.pyはPython標準と衝突するためrex_io.py）
│   ├── make_synthetic.py    # 合成データ生成
│   ├── compute_change.py    # 変化率集計・Donut Effect
│   ├── spatial_autocorr.py  # Global/Local Moran's I
│   ├── features.py          # 特徴量エンジニアリング
│   ├── train.py             # LightGBM学習・評価・SHAP
│   └── residual_check.py    # 残差診断
├── notebooks/
│   ├── A1_descriptive.ipynb # Phase A: 記述統計・空間自己相関
│   ├── B1_model.ipynb       # Phase B: 予測モデル
│   └── D1_visualization.ipynb # Phase D: 地図可視化
└── outputs/                 # 出力（git除外）
    ├── lgbm_model.pkl
    ├── cv_results.csv
    ├── feature_importance.csv
    ├── map_*.png / map_*.html
    └── research_overview_v2.pptx
```

※ `data/` ディレクトリは存在しない。実データはリポジトリ外で管理。

---

## スキーマ確定情報（REX_data_spec.xlsxより）

- ファイル名: `nouhin_line_〇〇.shp`（〇〇=年度）
- 主キー: `serial_id`（bigint）= code(5桁) + linkcode(7桁)
- CRS: EPSG:4326（WGS84）
- ジオメトリ: LineString（矢線）
- 重要列: `kakaku`（当年価格, 千円/㎡）, `pre1_kakak`（前年）, `pre2_kakak`（前前年）
- 地区区分: `chikukbn`（1-7）, 借地権割合: `swari`（1-8）
- 削除矢線: `flgdraw=False`, `kakaku=0` で識別
- 1ファイルに当年・前年・前前年の3年分が含まれる（年次結合不要）

---

## 研究テーマ・分析結果サマリー

### 研究テーマ
コロナ禍（2020–2022）の路線価変動パターンを空間統計と機械学習で分析する。

### Phase A: 空間的変動分析（完了）
- `compute_change.py`: 地区区分別・都道府県別・距離帯別の変化率集計
- `spatial_autocorr.py`: Global Moran's I（全国スケールの空間自己相関）/ Local Moran's I（LISA クラスター）
- 結果: Moran's I が有意 → 地価に明確な空間クラスター構造が存在
- Donut Effect 検証: 都市中心からの距離帯別変化率を分析

### Phase B: 予測モデル（完了）
- 特徴量: 空間ラグ（k=8近傍）/ ジオメトリ / 前年価格 / 地区区分
- モデル: LightGBM + Spatial CV（都道府県GroupKFold, 5-fold）
- 結果: R²=0.9985, MAE_real=3.4千円/㎡
- SHAP: 前年価格（#1）> 近傍平均価格（#2）> 前前年価格（#3）が支配的
- 残差 Moran's I = 0.34（有意）→ 地域固有の構造が残存

### Phase D: 可視化（完了）
- 静止図: matplotlib + contextily（map_price.png 等）
- インタラクティブ: Folium（5万件サンプリング）→ map_interactive.html
- 大規模WebGL: pydeck（230万件対応）→ map_pydeck_*.html

---

## 既知の実データ対応バグ修正（適用済み）

- `rex_io.py`: `DTYPE_MAP` を `Int32`/`Int16`（nullable）に変更（NaN混入対応）
- `rex_io.py`: CRS未設定時に EPSG:4326 を自動セット
- `compute_change.py`: `.astype(int)` → `.fillna(0).astype(int)`
- `features.py`: `.values.astype(float)` → `.to_numpy(dtype=float, na_value=np.nan)`
- `spatial_autocorr.py`: NaN行を先に除外してから重み行列構築（サイズ不整合防止）
- `D1_visualization.ipynb`: Folium を最大5万件サンプリング / `pd.NA` の安全変換

---

## 次のアクション

### コロナ前後比較分析
- 2020年ファイル（`/path/to/REX_data/2020/nouhin_line_2020.shp`）を読み込む
- 2020年ファイルから 2018・2019年価格（`pre1_kakak`, `pre2_kakak`）を取得
- 2018〜2022年の5年分を揃えてコロナ前後の変化率を比較
- Donut Effect の本格検証（コロナ前ベースラインとの比較）

---

## 開発フロー

1. 合成データ（`data_synthetic/`）でスクリプトを開発・テスト
2. パスを引数として渡すことで実データにも適用可能にする
3. ノートブック冒頭の `DATA_PATH` を実データパスに変更して実行（ユーザー担当）
4. 出力（グラフ・指標）のみ確認・共有する
