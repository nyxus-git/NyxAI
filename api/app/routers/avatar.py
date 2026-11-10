"""
api/app/routers/avatar.py

Endpoints for managing the companion girl avatar:
  - GET    /avatar/config        — Read persisted avatar config + voice options
  - POST   /avatar/config        — Update avatar mode, name, voice, and face landmarks
  - POST   /avatar/photo         — Upload a portrait photo of the companion girl
  - DELETE /avatar/photo         — Remove uploaded portrait photo and reset to default
  - POST   /avatar/model         — Upload a 3D .vrm or .glb avatar model
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from api.app.services.avatar_service import (
    AVATAR_ASSETS_DIR,
    AVAILABLE_FEMALE_VOICES,
    AvatarConfig,
    ensure_avatar_assets_dir,
    load_avatar_config,
    save_avatar_config,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/avatar", tags=["Avatar"])

ALLOWED_IMAGE_EXTS: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
ALLOWED_MODEL_EXTS: set[str] = {".vrm", ".glb"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_MODEL_BYTES = 60 * 1024 * 1024   # 60 MB


def _config_response(cfg: AvatarConfig) -> dict[str, Any]:
    return {
        **cfg.model_dump(),
        "available_voices": AVAILABLE_FEMALE_VOICES,
    }


def _remove_existing_with_prefix(directory: Path, stem_prefix: str) -> None:
    for item in directory.glob(f"{stem_prefix}.*"):
        if item.is_file():
            item.unlink(missing_ok=True)


@router.get("/config", summary="Get avatar configuration and available voices")
async def get_avatar_config() -> dict[str, Any]:
    """Return the active companion character configuration and curated female voices."""
    cfg = load_avatar_config()
    return _config_response(cfg)


@router.post("/config", summary="Update avatar configuration")
async def update_avatar_config(body: AvatarConfig) -> dict[str, Any]:
    """Persist updated avatar mode, name, voice ID, and photo landmark alignment."""
    saved = save_avatar_config(body)
    logger.info("avatar_config_updated", mode=saved.mode, voice=saved.voice, name=saved.name)
    return _config_response(saved)


@router.post("/photo", summary="Upload a portrait photo for the animated girl avatar")
async def upload_avatar_photo(file: UploadFile = File(...)) -> dict[str, Any]:
    """Validate and save a portrait image (.png, .jpg, .webp) for photo-driven animation."""
    filename = file.filename or "avatar.png"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image format '{ext}'. Allowed: .png, .jpg, .jpeg, .webp",
        )

    payload = await file.read()
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )
    if len(payload) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image exceeds 10 MB size limit.",
        )

    assets_dir = ensure_avatar_assets_dir(AVATAR_ASSETS_DIR)
    _remove_existing_with_prefix(assets_dir, "custom_avatar")

    dest = assets_dir / f"custom_avatar{ext}"
    dest.write_bytes(payload)

    cfg = load_avatar_config()
    cfg.mode = "photo"
    cfg.photo_url = f"/avatar/assets/{dest.name}?v={int(time.time())}"
    saved = save_avatar_config(cfg)

    logger.info("avatar_photo_uploaded", filename=dest.name, size_bytes=len(payload))
    return _config_response(saved)


@router.delete("/photo", summary="Remove custom portrait photo")
async def delete_avatar_photo() -> dict[str, Any]:
    """Delete uploaded portrait photo and switch back to stylized or VRM mode."""
    assets_dir = ensure_avatar_assets_dir(AVATAR_ASSETS_DIR)
    _remove_existing_with_prefix(assets_dir, "custom_avatar")

    cfg = load_avatar_config()
    cfg.photo_url = None
    if cfg.mode == "photo":
        cfg.mode = "vrm" if cfg.model_url else "stylized"
    saved = save_avatar_config(cfg)

    logger.info("avatar_photo_deleted", new_mode=saved.mode)
    return _config_response(saved)


@router.post("/model", summary="Upload a 3D .vrm or .glb avatar model")
async def upload_avatar_model(file: UploadFile = File(...)) -> dict[str, Any]:
    """Validate and save a 3D VRM/GLB character file for Three.js rendering."""
    filename = file.filename or "avatar.vrm"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_MODEL_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported 3D model format '{ext}'. Allowed: .vrm, .glb",
        )

    payload = await file.read()
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded model file is empty.",
        )
    if len(payload) > MAX_MODEL_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Model exceeds 60 MB size limit.",
        )

    assets_dir = ensure_avatar_assets_dir(AVATAR_ASSETS_DIR)
    _remove_existing_with_prefix(assets_dir, "custom_model")

    dest = assets_dir / f"custom_model{ext}"
    dest.write_bytes(payload)

    cfg = load_avatar_config()
    cfg.mode = "vrm"
    cfg.model_url = f"/avatar/assets/{dest.name}?v={int(time.time())}"
    saved = save_avatar_config(cfg)

    logger.info("avatar_model_uploaded", filename=dest.name, size_bytes=len(payload))
    return _config_response(saved)

