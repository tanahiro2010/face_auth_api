# face-auth-api

顔画像から人物を登録・識別する FastAPI + PostgreSQL(pgvector) API です。
顔特徴量の抽出には [insightface](https://github.com/deepinsight/insightface) (`buffalo_l`) を使用し、
抽出した embedding を PostgreSQL の [pgvector](https://github.com/pgvector/pgvector) 拡張でコサイン類似度検索します。

## 構成

- `src/main.py` — FastAPI エントリポイント。起動時に顔認識モデルをロードします。
- `src/face_service.py` — insightface のラッパー。画像から顔 embedding を抽出します。
- `src/models.py` / `src/database.py` — SQLAlchemy モデル・DB接続（`people` テーブル: 名前・任意情報(JSONB)・embedding(vector)）。
- `src/crud.py` — DB操作（登録・一覧・取得・削除・類似検索）。
- `src/routers/faces.py` — API エンドポイント。
- `alembic/` — DBマイグレーション。
- `static/` — 簡易Web UI（登録・識別・一覧）。FastAPIが `/ui` で配信します。

## セットアップ (Docker)

```bash
cp .env.example .env
docker compose up --build
```

初回起動時、`insightface` がモデルファイルをダウンロードします（`insightface_models` ボリュームにキャッシュされ、以降は再ダウンロードされません）。
起動時に Alembic マイグレーションが自動実行され、テーブルが作成されます。

API は `http://localhost:8000` で待ち受けます。Swagger UI は `http://localhost:8000/docs` です。

Web UI（カメラ撮影 or 画像ファイルで登録・識別・一覧確認ができる簡易画面）は `http://localhost:8000/ui/` です（`/` へアクセスすると自動でリダイレクトされます）。カメラ機能は HTTPS または `localhost` でのみ動作します。

## エンドポイント

### `POST /faces/register` — 顔と名前の登録

`multipart/form-data`:

| フィールド | 必須 | 説明 |
| --- | --- | --- |
| `name` | ✔ | 登録する名前 |
| `image` | ✔ | 顔写真ファイル |
| `info` | - | 追加情報（JSON文字列。例: `{"department": "営業部", "age": 30}`） |

```bash
curl -X POST http://localhost:8000/faces/register \
  -F "name=山田太郎" \
  -F 'info={"department": "営業部", "employee_id": "E001"}' \
  -F "image=@./yamada.jpg"
```

### `POST /faces/identify` — 顔から名前・情報を取得

`multipart/form-data` の `image` フィールドに写真を渡すと、最も類似度の高い登録者を返します。
類似度が閾値（既定 `0.5`、`.env` の `FACE_MATCH_THRESHOLD` で変更可）未満の場合は `404` を返します。

```bash
curl -X POST http://localhost:8000/faces/identify -F "image=@./unknown.jpg"
```

### その他

- `GET /faces` — 登録者一覧
- `GET /faces/{id}` — 登録者詳細
- `DELETE /faces/{id}` — 登録者削除

## 小さい顔の検出について

insightfaceの検出器は画像全体を固定サイズ（既定 `960x960`, `.env` の `FACE_DET_SIZE`）に縮小してから顔を探すため、
大きな写真の中で顔が小さく写っている場合、縮小時にさらに小さくなり検出できないことがあります。
このAPIでは、画像全体での検出に失敗した場合、画像を格子状（既定 `2x2`, `FACE_TILE_GRID`。20%重なり `FACE_TILE_OVERLAP`）に
分割してタイルごとに再検出するフォールバックを行い、小さい顔でも見つけやすくしています。

`FACE_DET_SIZE` / `FACE_TILE_GRID` を上げるほど小さい顔を検出しやすくなりますが、処理時間は増加します。

## ローカル開発 (Docker を使わない場合)

```bash
uv sync
docker compose up -d db   # PostgreSQL(pgvector) のみ起動
uv run alembic upgrade head
uv run uvicorn src.main:app --reload
```

## マイグレーションの追加

モデル (`src/models.py`) を変更したら、以下でマイグレーションを生成します（DBが起動している必要があります）。

```bash
uv run alembic revision --autogenerate -m "説明"
uv run alembic upgrade head
```
