from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import random
import re
import sys
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import aiohttp
from PIL import Image, UnidentifiedImageError

DISCORD_API_BASE = "https://discord.com/api/v10"
MAX_EMOJI_SIZE_BYTES = 256 * 1024
EMOJI_MAX_DIMENSION = 128
ALLOWED_EXTENSIONS = {".png", ".webp", ".jpg", ".jpeg", ".gif"}
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings


@dataclass(frozen=True)
class Source:
    path: Path
    emoji_type: str
    emoji_name: str
    logical_key: str


class DiscordApiError(RuntimeError):
    pass


def _log_item_status(status: str, source: Source, detail: str = "") -> None:
    suffix = f" | {detail}" if detail else ""
    print(f"[{status}] {source.emoji_name} ({source.emoji_type}){suffix}")


def _slug(stem: str) -> str:
    raw = stem.strip()
    ascii_stem = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    snake = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_stem.lower()).strip("_")
    snake = re.sub(r"_+", "_", snake)
    return snake or "x"


def _cap_name(name: str, used: set[str], max_len: int = 32) -> str:
    base = name[:max_len].strip("_")
    if len(base) < 2:
        base = (base + "_x")[:max_len]

    cand = base
    i = 2
    while cand in used:
        suffix = f"_{i}"
        trim = max_len - len(suffix)
        cand = (base[:trim].rstrip("_") + suffix) if trim > 0 else f"e{suffix}"
        i += 1

    used.add(cand)
    return cand


def _data_uri(mime: str, payload: bytes) -> str:
    b64 = base64.b64encode(payload).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _save_png(img: Image.Image) -> bytes:
    out = BytesIO()
    img.save(out, format="PNG", optimize=True, compress_level=9)
    return out.getvalue()


def _save_jpeg(img: Image.Image, quality: int) -> bytes:
    out = BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue()


def prepare_image(path: Path) -> tuple[str, bytes]:
    try:
        with Image.open(path) as opened:
            img = opened.copy()
    except UnidentifiedImageError as exc:
        raise ValueError(f"invalid_image:{path}") from exc

    has_alpha = "A" in img.getbands() or img.mode in {"LA", "RGBA", "PA"}
    working = img.convert("RGBA") if has_alpha else img.convert("RGB")
    working.thumbnail((EMOJI_MAX_DIMENSION, EMOJI_MAX_DIMENSION), Image.Resampling.LANCZOS)

    candidates: list[tuple[str, bytes]] = []

    png = _save_png(working.convert("RGBA"))
    candidates.append(("image/png", png))

    if has_alpha:
        for colors in (256, 128, 64, 32):
            try:
                q = working.convert("RGBA").quantize(colors=colors, method=2)
                candidates.append(("image/png", _save_png(q.convert("RGBA"))))
            except Exception:
                pass
    else:
        for q in (92, 85, 78, 70, 62, 55):
            candidates.append(("image/jpeg", _save_jpeg(working, q)))

    for mime, payload in candidates:
        if len(payload) <= MAX_EMOJI_SIZE_BYTES:
            return mime, payload

    resized = working.convert("RGBA")
    for side in (112, 96, 80, 72, 64):
        tmp = resized.copy()
        tmp.thumbnail((side, side), Image.Resampling.LANCZOS)
        payload = _save_png(tmp)
        if len(payload) <= MAX_EMOJI_SIZE_BYTES:
            return "image/png", payload

    raise ValueError(f"too_big:{path}")


async def discord_request(
    session: aiohttp.ClientSession,
    method: str,
    endpoint: str,
    token: str,
    *,
    json_body: dict[str, Any] | None = None,
    max_retries: int = 6,
) -> Any:
    url = f"{DISCORD_API_BASE}{endpoint}"
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}

    for attempt in range(1, max_retries + 1):
        try:
            async with session.request(method, url, headers=headers, json=json_body) as resp:
                txt = await resp.text()
                if 200 <= resp.status < 300:
                    if not txt.strip():
                        return {}
                    return json.loads(txt)

                if resp.status in RETRYABLE_STATUS:
                    wait_s = 1.2 * attempt
                    if resp.status == 429:
                        try:
                            payload = json.loads(txt) if txt else {}
                        except json.JSONDecodeError:
                            payload = {}
                        wait_s = float(payload.get("retry_after", wait_s))
                    await asyncio.sleep(wait_s + random.uniform(0.0, 0.4))
                    continue

                raise DiscordApiError(f"{resp.status}:{method}:{endpoint}:{txt[:500]}")
        except aiohttp.ClientError as exc:
            if attempt >= max_retries:
                raise DiscordApiError(f"net_error:{method}:{endpoint}:{exc}") from exc
            await asyncio.sleep((1.1 * attempt) + random.uniform(0.0, 0.4))

    raise DiscordApiError(f"failed:{method}:{endpoint}")


def _extract_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("items"), list):
            return [x for x in payload["items"] if isinstance(x, dict)]
        if isinstance(payload.get("emojis"), list):
            return [x for x in payload["emojis"] if isinstance(x, dict)]
    return []


async def list_app_emojis(session: aiohttp.ClientSession, app_id: str, token: str) -> dict[str, dict[str, Any]]:
    payload = await discord_request(session, "GET", f"/applications/{app_id}/emojis", token)
    items = _extract_list(payload)
    out: dict[str, dict[str, Any]] = {}
    for it in items:
        name = str(it.get("name") or "").lower().strip()
        if name:
            out[name] = it
    return out


async def create_app_emoji(
    session: aiohttp.ClientSession,
    app_id: str,
    token: str,
    name: str,
    data_uri: str,
) -> dict[str, Any]:
    payload = await discord_request(
        session,
        "POST",
        f"/applications/{app_id}/emojis",
        token,
        json_body={"name": name, "image": data_uri},
    )
    if not isinstance(payload, dict) or "id" not in payload:
        raise DiscordApiError(f"create_unexpected:{name}:{payload}")
    return payload


async def delete_app_emoji(session: aiohttp.ClientSession, app_id: str, token: str, emoji_id: str) -> None:
    await discord_request(session, "DELETE", f"/applications/{app_id}/emojis/{emoji_id}", token)


def discover_media(root: Path) -> list[tuple[Path, str, str]]:
    media_dir = root / "media"
    if not media_dir.exists():
        raise ValueError(f"missing_media_dir:{media_dir}")

    targets = [
        (media_dir / "champions", "champ", "champ_"),
        (media_dir / "custom", "custom", ""),
        (media_dir / "items", "item", "item_"),
        (media_dir / "live", "live", ""),
        (media_dir / "ranks", "rank", "rank_"),
        (media_dir / "runes", "rune", "rune_"),
        (media_dir / "summoner-spells", "spell", "spell_"),
    ]

    out: list[tuple[Path, str, str]] = []
    for d, typ, prefix in targets:
        if not d.exists():
            continue
        for p in sorted(d.iterdir()):
            if not p.is_file():
                continue
            if p.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            out.append((p, typ, prefix))
    return out


def build_sources(root: Path) -> list[Source]:
    discovered = discover_media(root)
    used: set[str] = set()
    out: list[Source] = []

    for path, typ, prefix in discovered:
        stem = path.stem
        slug = _slug(stem)

        if typ in {"item", "spell"} and slug.isdigit():
            emoji_name = f"{prefix}{slug}"
            logical_key = slug
        else:
            emoji_name = f"{prefix}{slug}"
            logical_key = slug

        emoji_name = _cap_name(emoji_name, used)

        out.append(Source(path=path, emoji_type=typ, emoji_name=emoji_name, logical_key=f"{typ}:{logical_key}"))

    return out


def parse_args() -> argparse.Namespace:
    settings = get_settings()

    p = argparse.ArgumentParser()
    p.add_argument(
        "--application-id",
        default=settings.discord_application_id or os.getenv("DISCORD_APPLICATION_ID", ""),
        required=False,
    )
    p.add_argument(
        "--bot-token",
        default=settings.discord_token or os.getenv("DISCORD_TOKEN", ""),
        required=False,
    )
    p.add_argument("--root", default=".", required=False)
    p.add_argument("--overwrite", action="store_true", default=os.getenv("OVERWRITE", "").lower() in {"1", "true", "yes"})
    p.add_argument("--dry-run", action="store_true", default=os.getenv("DRY_RUN", "").lower() in {"1", "true", "yes"})
    p.add_argument("--out", default="emoji_map.json")
    p.add_argument("--only", default="")
    return p.parse_args()


def _only_filter(only: str) -> set[str] | None:
    o = (only or "").strip().lower()
    if not o:
        return None
    parts = [x.strip() for x in o.split(",") if x.strip()]
    return set(parts) if parts else None


def _load_existing_mapping(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items() if isinstance(v, dict)}

    # Older or external files may use a flat array structure.
    if isinstance(raw, list):
        out: dict[str, dict[str, Any]] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            emoji_type = str(item.get("type") or "").strip()
            logical_name = str(item.get("logical_name") or "").strip()
            if not emoji_type or not logical_name:
                continue
            out[f"{emoji_type}:{logical_name}"] = dict(item)
        return out

    return {}


async def orchestrate(args: argparse.Namespace) -> int:
    app_id = str(args.application_id).strip()
    token = str(args.bot_token).strip()
    root = Path(args.root).expanduser().resolve()
    overwrite = bool(args.overwrite)
    dry = bool(args.dry_run)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = root / out_path

    if not app_id:
        raise ValueError("missing_application_id")
    if not token:
        raise ValueError("missing_discord_token")

    only = _only_filter(args.only)
    sources = build_sources(root)
    if only is not None:
        sources = [s for s in sources if s.emoji_type in only]

    timeout = aiohttp.ClientTimeout(total=120)
    uploaded = 0
    skipped = 0
    deleted = 0
    errors = 0

    mapping = _load_existing_mapping(out_path)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        existing = await list_app_emojis(session, app_id, token)

        for s in sources:
            ex = existing.get(s.emoji_name.lower())
            if ex and not overwrite:
                skipped += 1
                mapping[s.logical_key] = {
                    **mapping.get(s.logical_key, {}),
                    "name": s.emoji_name,
                    "id": str(ex.get("id") or ""),
                    "type": s.emoji_type,
                }
                _log_item_status("SKIPPED", s, "already_exists")
                continue

            try:
                mime, payload = prepare_image(s.path)
                if dry:
                    skipped += 1
                    mapping[s.logical_key] = {
                        **mapping.get(s.logical_key, {}),
                        "name": s.emoji_name,
                        "id": None,
                        "type": s.emoji_type,
                        "dry_run": True,
                    }
                    _log_item_status("SKIPPED", s, "dry_run")
                    continue

                if ex and overwrite:
                    old_id = str(ex.get("id") or "")
                    if old_id:
                        await delete_app_emoji(session, app_id, token, old_id)
                        deleted += 1
                        _log_item_status("DELETED", s, f"old_id={old_id}")

                created = await create_app_emoji(session, app_id, token, s.emoji_name, _data_uri(mime, payload))
                created_id = str(created.get("id") or "")
                existing[s.emoji_name.lower()] = created
                uploaded += 1
                mapping[s.logical_key] = {
                    **mapping.get(s.logical_key, {}),
                    "name": s.emoji_name,
                    "id": created_id,
                    "type": s.emoji_type,
                }
                _log_item_status("DONE", s, f"id={created_id}")
                await asyncio.sleep(0.08 + random.random() * 0.08)

            except Exception as exc:
                errors += 1
                mapping[s.logical_key] = {
                    **mapping.get(s.logical_key, {}),
                    "name": s.emoji_name,
                    "id": None,
                    "type": s.emoji_type,
                    "error": str(exc),
                }
                _log_item_status("ERROR", s, str(exc))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Found: {len(sources)}")
    print(f"Uploaded: {uploaded}")
    print(f"Skipped: {skipped}")
    print(f"Deleted: {deleted}")
    print(f"Errors: {errors}")
    print(f"Mapping: {out_path}")

    return 1 if errors else 0


def main() -> None:
    args = parse_args()
    raise SystemExit(asyncio.run(orchestrate(args)))


if __name__ == "__main__":
    main()
