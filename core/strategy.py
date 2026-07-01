"""StrategyConfig + parser de STRATEGY.md.

GAP RESUELTO: el whitepaper dice que Risk consume el "STRATEGY.md parseado como
StrategyConfig" pero no especifica el parser ni el modelo. Aquí se definen ambos.

`parse_strategy_md(text)` es una función PURA (string -> StrategyConfig). La
lectura del archivo desde disco vive en `tournaments/registry.py` (eso es IO).

El parser lee los pares `clave: valor` del documento (ignorando markdown) más el
bloque de QUALITATIVE RULES (`- QR-xxx: desc → acción`). Es tolerante a las
secciones decorativas del template: sólo extrae las claves conocidas.

Principio anti-deuda: ningún threshold vive hardcodeado en Python. Si no está en
el STRATEGY.md activo, no existe.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field, field_validator

from core.exceptions import StrategyParseError

# Líneas tipo `clave: valor` (permite comentarios inline con `#`).
_KV_RE = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.+?)\s*(?:#.*)?$")
# Líneas tipo `- QR-001: descripción → acción`
_QR_RE = re.compile(r"^\s*-\s*(QR-\d+)\s*:\s*(.+?)\s*(?:→|->)\s*(.+?)\s*$")


class QualitativeRule(BaseModel):
    """Una regla cualitativa (QR-xxx). Claude la evalúa con contexto."""

    id: str
    description: str
    action: str


class StrategyConfig(BaseModel):
    """Contrato parseado de un STRATEGY.md. Inmutable una vez aprobado.

    Es la única fuente de verdad de las reglas de trading para una combinación
    `torneo × tipo de mercado`.
    """

    model_config = {"frozen": True}

    # HEADER
    version: str
    status: str  # draft | under_review | approved | deprecated
    author: str | None = None
    last_updated: str | None = None

    # SCOPE
    tournament_id: str
    sport: str
    market_type: str
    venue: str = "Polymarket"
    outcomes: list[str] = Field(default_factory=list)

    # THESIS (texto libre, contexto cualitativo)
    thesis: str | None = None

    # THRESHOLDS DE DECISIÓN
    edge_threshold_auto: Decimal
    edge_threshold_review: Decimal
    edge_threshold_discard: Decimal
    min_market_volume_usdc: Decimal
    max_hours_to_event: float
    min_hours_to_event: float

    # RISK LIMITS (extensión canónica explícita — ver template STRATEGY.md)
    max_exposure_per_participant: Decimal = Decimal("0.15")
    max_open_positions: int = 10
    max_kelly_fraction: Decimal = Decimal("0.05")
    max_drawdown_7d: Decimal = Decimal("0.20")
    review_event_phases: list[str] = Field(
        default_factory=lambda: ["playoff", "knockout", "final"]
    )

    # SIZING
    sizing_method: str = "fractional_kelly"
    kelly_fraction: Decimal = Decimal("0.25")
    max_bet_usdc: Decimal = Decimal("50")
    min_bet_usdc: Decimal = Decimal("5")

    # SELECCIÓN DE LADO (migración worldcup: elo | bayes | blend | trueskill)
    side_criterion: str = "elo"
    blend_weight: Decimal = Decimal("0.5")        # peso de Elo en 'blend' (1-w para Bayes)
    warmup_match_no: int = 1                       # arranca en la N-ésima aparición del lado
    use_bayes_filter: bool = False
    bayes_threshold: Decimal = Decimal("0.5")

    # PERFORMANCE TARGETS
    win_rate_target: float | None = None
    roi_target: float | None = None
    max_drawdown_allowed: Decimal | None = None
    evaluation_period: str | None = None

    # QUALITATIVE RULES
    qualitative_rules: list[QualitativeRule] = Field(default_factory=list)

    # Procedencia (lo rellena el loader, no el parser)
    strategy_id: str | None = None
    source_path: str | None = None

    @field_validator("status")
    @classmethod
    def _status_known(cls, v: str) -> str:
        allowed = {"draft", "under_review", "approved", "deprecated"}
        if v not in allowed:
            raise ValueError(f"status inválido: {v!r} (permitidos: {sorted(allowed)})")
        return v

    @property
    def is_approved(self) -> bool:
        return self.status == "approved"


# ── Parsing ──────────────────────────────────────────────────────────────────

# Claves escalares conocidas y su caster.
_DECIMAL_KEYS = {
    "edge_threshold_auto",
    "edge_threshold_review",
    "edge_threshold_discard",
    "min_market_volume_usdc",
    "max_exposure_per_participant",
    "max_kelly_fraction",
    "max_drawdown_7d",
    "kelly_fraction",
    "max_bet_usdc",
    "min_bet_usdc",
    "max_drawdown_allowed",
    "blend_weight",
    "bayes_threshold",
}
_FLOAT_KEYS = {
    "max_hours_to_event",
    "min_hours_to_event",
    "win_rate_target",
    "roi_target",
}
_INT_KEYS = {"max_open_positions", "warmup_match_no"}
_BOOL_KEYS = {"use_bayes_filter"}
_LIST_KEYS = {"outcomes", "review_event_phases"}
_STR_KEYS = {
    "version",
    "status",
    "author",
    "last_updated",
    "tournament_id",
    "sport",
    "market_type",
    "venue",
    "sizing_method",
    "evaluation_period",
    "side_criterion",
}

_KNOWN = _DECIMAL_KEYS | _FLOAT_KEYS | _INT_KEYS | _BOOL_KEYS | _LIST_KEYS | _STR_KEYS

_TRUE = {"true", "yes", "1", "on"}
_FALSE = {"false", "no", "0", "off"}


def _parse_list(value: str) -> list[str]:
    value = value.strip().strip("[]")
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_strategy_md(text: str, *, strategy_id: str | None = None,
                      source_path: str | None = None) -> StrategyConfig:
    """Parsea el texto de un STRATEGY.md a StrategyConfig. Función pura.

    Levanta StrategyParseError si faltan campos obligatorios o hay valores
    inválidos.
    """
    fields: dict[str, Any] = {}
    qrs: list[QualitativeRule] = []

    for line in text.splitlines():
        qr_match = _QR_RE.match(line)
        if qr_match:
            qrs.append(
                QualitativeRule(
                    id=qr_match.group(1),
                    description=qr_match.group(2).strip(),
                    action=qr_match.group(3).strip(),
                )
            )
            continue

        kv = _KV_RE.match(line)
        if not kv:
            continue
        key, raw = kv.group(1), kv.group(2).strip()
        if key not in _KNOWN:
            continue
        # No sobreescribir: la primera aparición gana (evita capturar ejemplos).
        if key in fields:
            continue
        try:
            if key in _DECIMAL_KEYS:
                fields[key] = Decimal(raw)
            elif key in _FLOAT_KEYS:
                fields[key] = float(raw)
            elif key in _INT_KEYS:
                fields[key] = int(raw)
            elif key in _BOOL_KEYS:
                low = raw.strip().lower()
                if low not in _TRUE and low not in _FALSE:
                    raise ValueError(f"booleano inválido: {raw!r}")
                fields[key] = low in _TRUE
            elif key in _LIST_KEYS:
                fields[key] = _parse_list(raw)
            else:
                fields[key] = raw
        except (InvalidOperation, ValueError) as exc:
            raise StrategyParseError(f"Valor inválido para {key!r}: {raw!r} ({exc})") from exc

    if qrs:
        fields["qualitative_rules"] = qrs
    if strategy_id:
        fields["strategy_id"] = strategy_id
    if source_path:
        fields["source_path"] = source_path

    try:
        return StrategyConfig(**fields)
    except Exception as exc:  # pydantic ValidationError u otros
        raise StrategyParseError(f"STRATEGY.md inválido: {exc}") from exc
