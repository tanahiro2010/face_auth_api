from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/face_auth"
    face_match_threshold: float = 0.5
    insightface_model_name: str = "buffalo_l"
    # insightface のデフォルトは 640。960 に上げると小さい顔は拾いやすくなる一方、
    # フレーム一杯に写った大きい顔の検出スコアが閾値未満まで落ち込み逆に取りこぼす
    # （実測: 顔が画面いっぱいの写真で det_size 640→score 0.88 / 960→0.18）。
    # スマートグラス用途は目の前の人物＝大きい顔が主なので 640 を既定にし、
    # 小さい顔は下のタイル分割フォールバック（face_tile_grid）で補う。
    face_det_size: int = 640
    face_tile_grid: int = 2
    face_tile_overlap: float = 0.2
    face_sample_duplicate_threshold: float = 0.94
    face_auto_enroll_min_similarity: float = 0.68
    face_max_samples_per_person: int = 50


settings = Settings()
