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

EDITH Face Tracker は `http://localhost:8000/ui/edith-face-tracker.html` で開けます。
カメラ映像上で顔を追跡し、補正済みの顔切り抜きを `/faces/register` と `/faces/identify` に送って、登録した名前を `trackId` に紐づけて表示します。
同じ名前で再登録すると新しい人物ではなく同一人物の角度サンプルとして追加されます。
識別成功時も、既存サンプルと近すぎない顔向きであれば追加サンプルとして自動保存されます。
Face Trackerでは、一度登録または識別された `trackId` は名前を保持し、角度が変わるたびに `/faces/{person_id}/samples` へ追加サンプルを送ります。

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
既定では識別に成功した顔を追加サンプル候補にし、既存サンプルとの類似度が高すぎる場合は保存をスキップします。
角度サンプルの重複判定は `FACE_SAMPLE_DUPLICATE_THRESHOLD`、自動追加を始める最低類似度は `FACE_AUTO_ENROLL_MIN_SIMILARITY`、一人あたりの最大サンプル数は `FACE_MAX_SAMPLES_PER_PERSON` で調整できます。

### `POST /faces/{person_id}/samples` — 登録者へ角度サンプルを追加

`multipart/form-data` の `image` フィールドに追加したい顔画像を渡します。
既存サンプルと近すぎる場合は保存せず、`sample_added: false` を返します。

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

## 傾き・向きの補正について

以下の2種類の「角度」を補正しています。

- **EXIF回転**: スマートフォン等で撮影した写真は、ピクセル自体は横向きのままEXIFの回転情報だけで正しい向きを表すことが多いため、検出前にEXIF情報に従って自動補正します。
- **90/180/270度回転**: 写真自体が横向き・逆さまでEXIF情報がない（または誤っている）場合に備え、4方向（そのまま／時計回り90度／180度／反時計回り90度）すべてで顔検出を行い、検出器の信頼度スコア（`det_score`）が最も高いものを採用します。誤った向きでもたまに低品質な顔を拾ってしまうことがあるため、最初に見つかった向きを即採用せず、必ず4方向を比較してから決定します。

なお、首の傾き程度の自然なポーズ変化はinsightface内部のランドマークに基づく顔位置合わせで元々吸収されるため、追加の補正は不要です。

**トレードオフ**: 常に4方向で検出するため、1リクエストあたりの処理時間はおよそ4倍になります（実測: 772x754pxの画像で約1.3〜1.7秒 / リクエスト、CPU推論）。同時アクセスが多い環境ではサーバーのCPUリソースを多めに見積もってください。

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
