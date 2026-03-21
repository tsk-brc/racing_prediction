# Racing Data Collector

競馬（JRA）および競艇のレースデータを Web スクレイピングで収集し、CSV に変換するツール。

## 概要

本リポジトリは、公営競技のレースデータを自動収集・変換するためのスクレイピング基盤です。対象サイトから HTML を取得し、構造化データ（CSV）に変換するパイプラインを提供します。

**本リポジトリはデータ収集部分のみを扱っています。** 予測・分析のロジックは含まれていません。

## データ収集対象

| 対象 | ソース | 取得内容 |
|------|--------|---------|
| 競馬（JRA） | netkeiba.com | レース URL → HTML → CSV |
| 競艇 | kyoteibiyori.com | 出走表 HTML → CSV |

## データ収集パイプライン

### 競馬（JRA）

```
get_race_url.py          指定期間のレース URL を Selenium で収集
       ↓
get_race_html.py         各 URL のレースページ HTML を取得
       ↓
convert_csv_into_html.py HTML をパースして CSV に変換
       ↓
csv_cleansing.py         データクレンジング（型変換、欠損処理）
```

### 競艇

```
get_kyotei_html.py       指定期間・場の出走表 HTML を取得 → CSV 変換
```

## 技術スタック

- **言語**: Python 3.8
- **スクレイピング**: Selenium (Firefox / Geckodriver), Requests, BeautifulSoup
- **データ処理**: pandas, NumPy
- **コンテナ**: Docker / Docker Compose

## セットアップ

### Docker（推奨）

```bash
docker-compose build
docker-compose run racing python get_race_url.py
```

### ローカル

```bash
pip install -r requirements.txt
python get_race_url.py
```

## 設定

`config.ini` でデータ取得範囲や保存先を設定します。

```ini
[CONST]
FROM_YEAR = 2010

[URL]
KEIBA_DB_URL = https://db.netkeiba.com/?pid=race_search_detail
KYOTEI_BASE_URL = https://kyoteibiyori.com/race_shusso.php
```

## ディレクトリ構成

```
racing_prediction/
├── get_race_url.py              # 競馬レース URL 収集（Selenium）
├── get_race_html.py             # 競馬レースページ HTML 取得
├── get_kyotei_html.py           # 競艇出走表 HTML 取得
├── convert_csv_into_html.py     # HTML → CSV 変換
├── csv_cleansing.py             # CSV データクレンジング
├── config.ini                   # 取得設定
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── url/                         # 収集した URL（gitignore）
├── html/                        # 取得した HTML（gitignore）
├── html_kyotei/                 # 競艇 HTML（gitignore）
├── csv/                         # 変換済み CSV（gitignore）
└── log/                         # 実行ログ（gitignore）
```

## 注意事項

- 本リポジトリはデータ収集の研究・学習目的で作成しています
- スクレイピング対象サイトの利用規約を遵守してください
- 過度なアクセスを避けるため、適切な間隔を設けて実行してください

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照してください。
