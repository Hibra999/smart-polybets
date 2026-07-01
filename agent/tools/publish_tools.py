"""Publicación en X (Twitter) vía Metricool — portado de pypro_x_automatic_post.

Agenda/publica un tweet en Metricool (`/v2/scheduler/posts`). DRY-RUN por defecto:
no envía nada, sólo devuelve el payload. Para publicar de verdad: `dry_run=False`
con las credenciales en el entorno (METRICOOL_USER_TOKEN/USER_ID/BLOG_ID).

`autoPublish=True` hace que Metricool publique automáticamente en la fecha; con
False queda agendado para revisión en el panel.
"""
from __future__ import annotations

import json
import logging
import os

from core.utils import utcnow

logger = logging.getLogger(__name__)

BASE_URL = "https://app.metricool.com/api"
DEFAULT_TZ = os.getenv("METRICOOL_TIMEZONE", "America/Mexico_City")


def build_payload(text: str, schedule_at: str, timezone: str = DEFAULT_TZ,
                  thread: list[str] | None = None, auto_publish: bool = False) -> dict:
    """Cuerpo de /v2/scheduler/posts para un post de X/Twitter."""
    payload: dict = {
        "text": text,
        "publicationDate": {"dateTime": schedule_at, "timezone": timezone},
        "providers": [{"network": "twitter"}],
        "autoPublish": auto_publish,
        "saveExternalMediaFiles": True,
    }
    if thread:
        payload["descendants"] = [{"text": t} for t in thread]
    return payload


def _auth_params() -> dict:
    return {
        "userToken": os.environ["METRICOOL_USER_TOKEN"],
        "userId": os.environ["METRICOOL_USER_ID"],
        "blogId": os.environ["METRICOOL_BLOG_ID"],
    }


def schedule_post(payload: dict, *, dry_run: bool = True) -> dict:
    """POST del payload a Metricool. dry_run imprime y devuelve el payload."""
    if dry_run:
        logger.info("[DRY RUN] POST %s/v2/scheduler/posts", BASE_URL)
        logger.info("[DRY RUN] payload:\n%s", json.dumps(payload, ensure_ascii=False, indent=2))
        return {"dry_run": True, "payload": payload}

    import requests

    resp = requests.post(
        f"{BASE_URL}/v2/scheduler/posts",
        params=_auth_params(), json=payload, timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    logger.info("Scheduled post id=%s", result.get("data", {}).get("id"))
    return result


def _now_in_tz(timezone: str, buffer_min: int = 3) -> str:
    """Hora local en `timezone` + buffer (Metricool agenda en hora local)."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    local = utcnow().astimezone(ZoneInfo(timezone)) + timedelta(minutes=buffer_min)
    return local.strftime("%Y-%m-%dT%H:%M:%S")


def publish_tweet(text: str, *, schedule_at: str | None = None, timezone: str = DEFAULT_TZ,
                  thread: list[str] | None = None, auto_publish: bool = False,
                  dry_run: bool = True) -> dict:
    """Conveniencia: arma el payload y lo agenda/publica. Sin `schedule_at`, usa la
    hora local actual (en `timezone`) + 3 min."""
    schedule_at = schedule_at or _now_in_tz(timezone)
    payload = build_payload(text, schedule_at, timezone, thread, auto_publish)
    return schedule_post(payload, dry_run=dry_run)
