from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/face_auth"
    face_recognition_mode: str = "custom"
    face_match_threshold: float = 0.5
    insightface_model_name: str = "buffalo_l"
    face_det_size: int = 960
    face_tile_grid: int = 2
    face_tile_overlap: float = 0.2
    face_sample_duplicate_threshold: float = 0.94
    face_auto_enroll_min_similarity: float = 0.68
    face_max_samples_per_person: int = 32

    @property
    def effective_insightface_model_name(self) -> str:
        return self._mode_value("model_name", self.insightface_model_name)

    @property
    def effective_face_det_size(self) -> int:
        return self._mode_value("det_size", self.face_det_size)

    @property
    def effective_face_tile_grid(self) -> int:
        return self._mode_value("tile_grid", self.face_tile_grid)

    @property
    def effective_face_tile_overlap(self) -> float:
        return self._mode_value("tile_overlap", self.face_tile_overlap)

    def _mode_value(self, key: str, fallback):
        presets = {
            "fast": {
                "model_name": "buffalo_s",
                "det_size": 512,
                "tile_grid": 1,
                "tile_overlap": 0.0,
            },
            "balanced": {
                "model_name": "buffalo_l",
                "det_size": 640,
                "tile_grid": 1,
                "tile_overlap": 0.0,
            },
            "accurate": {
                "model_name": "buffalo_l",
                "det_size": 960,
                "tile_grid": 2,
                "tile_overlap": 0.2,
            },
        }
        mode = self.face_recognition_mode.lower()
        if mode in presets:
            return presets[mode][key]
        return fallback


settings = Settings()
