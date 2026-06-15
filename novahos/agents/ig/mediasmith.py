"""MEDIASMITH — media prep (a shared capability): probe, cover frame, register assets. (Agents.)

Uses ffmpeg/ffprobe when present; degrades gracefully if absent. MEDIA_DIR from env.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ...models import MediaAsset


def checksum(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ffprobe(path: str) -> dict:
    if not shutil.which("ffprobe"):
        return {}
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path],
            capture_output=True, text=True, timeout=60)
        data = json.loads(out.stdout or "{}")
        v = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        return {"duration_s": float(data.get("format", {}).get("duration", 0) or 0),
                "width": int(v.get("width", 0) or 0), "height": int(v.get("height", 0) or 0)}
    except Exception:
        return {}


def _cover_frame(path: str, out_dir: Path) -> str | None:
    if not shutil.which("ffmpeg"):
        return None
    out = out_dir / (Path(path).stem + "_cover.jpg")
    try:
        subprocess.run(["ffmpeg", "-y", "-i", path, "-ss", "00:00:01", "-vframes", "1", str(out)],
                       capture_output=True, timeout=60)
        return str(out) if out.exists() else None
    except Exception:
        return None


async def prepare(db: AsyncSession, user_id: str, *, content_piece_id: str,
                  source_asset: MediaAsset) -> dict[str, MediaAsset]:
    info = _ffprobe(source_asset.path)
    if info:
        source_asset.duration_s = info.get("duration_s") or source_asset.duration_s
        source_asset.width = info.get("width") or source_asset.width
        source_asset.height = info.get("height") or source_asset.height

    assets = {"source": source_asset}
    media_dir = Path(os.environ.get("MEDIA_DIR", "./media"))
    media_dir.mkdir(parents=True, exist_ok=True)
    cover_path = _cover_frame(source_asset.path, media_dir)
    if cover_path:
        cover = MediaAsset(user_id=user_id, content_piece_id=content_piece_id,
                           kind="cover", path=cover_path, mime="image/jpeg")
        db.add(cover)
        assets["cover"] = cover

    await db.flush()
    return assets
