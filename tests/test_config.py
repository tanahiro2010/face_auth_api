from src.config import Settings


def test_fast_mode_keeps_embeddings_compatible_with_balanced_mode() -> None:
    settings = Settings(face_recognition_mode="fast")
    balanced = Settings(face_recognition_mode="balanced")

    assert (
        settings.effective_insightface_model_name
        == balanced.effective_insightface_model_name
    )
    assert settings.effective_face_det_size == 512
    assert settings.effective_face_tile_grid == 1
    assert settings.effective_face_tile_overlap == 0.0


def test_custom_face_recognition_mode_keeps_explicit_values() -> None:
    settings = Settings(
        face_recognition_mode="custom",
        insightface_model_name="buffalo_l",
        face_det_size=960,
        face_tile_grid=2,
        face_tile_overlap=0.2,
    )

    assert settings.effective_insightface_model_name == "buffalo_l"
    assert settings.effective_face_det_size == 960
    assert settings.effective_face_tile_grid == 2
    assert settings.effective_face_tile_overlap == 0.2
