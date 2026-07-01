# REX地価コンテンツデータセット 分析プロジェクト

NII IDR「REX地価コンテンツデータセット」（相続税路線価）を用いた地理空間データ分析・機械学習パイプライン。

## 注意事項

**REXデータは NII IDR 利用許諾契約に基づくライセンスデータです。**
`data/` 配下のファイルは絶対にコミット・外部送信しないこと。詳細は `CLAUDE.md` を参照。

## セットアップ

```bash
# 仮想環境作成
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存パッケージインストール
pip install -r requirements.txt
```

## ディレクトリ構成

```
data_analysis/
├── CLAUDE.md            # データポリシー・プロジェクト規約（必読）
├── README.md
├── requirements.txt
├── data/                # 実データ（git除外・閲覧禁止）
├── data_synthetic/      # 合成データ（開発・テスト用）
├── src/                 # ソースコード
│   ├── make_synthetic.py  # 合成データ生成（スキーマ確定後）
│   └── io.py              # データ読み込み・前処理モジュール
├── notebooks/           # 分析ノートブック
└── outputs/             # 出力（git除外）
```

## 開発フロー

1. `data_synthetic/` の合成データで開発・テスト
2. 実データへの適用はパス引数を変えるだけ
3. 実データは必ずユーザーが手元で実行する

## データ仕様

- 形式: シェイプファイル（.shp）
- 年次: 2020 / 2021 / 2022
- 件数: 全国約230万矢線
- 主要属性: 路線価格、借地権割合、地区区分、地区記号詳細、緯度経度
