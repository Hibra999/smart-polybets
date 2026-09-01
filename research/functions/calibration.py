"""Utilidades puras para quitar vigorish y medir calibración probabilística."""
from __future__ import annotations

import math
from collections.abc import Sequence


def power_devig(implied: Sequence[float]) -> list[float]:
    """Normaliza probabilidades implícitas con el método power ``sum(q**k)=1``."""
    q = [float(value) for value in implied]
    if len(q) < 2 or any(not 0 < value < 1 for value in q):
        raise ValueError("se requieren al menos dos probabilidades entre 0 y 1")
    lo, hi = 0.0, 100.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if sum(value ** mid for value in q) > 1:
            lo = mid
        else:
            hi = mid
    fair = [value ** ((lo + hi) / 2) for value in q]
    total = sum(fair)
    return [value / total for value in fair]


def multiclass_log_loss(probabilities: Sequence[Sequence[float]],
                        outcomes: Sequence[int]) -> float:
    if not probabilities or len(probabilities) != len(outcomes):
        raise ValueError("probabilidades y resultados deben tener igual longitud no vacía")
    losses = []
    for row, outcome in zip(probabilities, outcomes, strict=True):
        if outcome < 0 or outcome >= len(row):
            raise ValueError("resultado fuera del rango de clases")
        losses.append(-math.log(max(min(float(row[outcome]), 1.0), 1e-15)))
    return sum(losses) / len(losses)


def multiclass_brier(probabilities: Sequence[Sequence[float]],
                     outcomes: Sequence[int]) -> float:
    """Brier multiclase estándar: promedio de la suma de errores cuadrados."""
    if not probabilities or len(probabilities) != len(outcomes):
        raise ValueError("probabilidades y resultados deben tener igual longitud no vacía")
    total = 0.0
    for row, outcome in zip(probabilities, outcomes, strict=True):
        if outcome < 0 or outcome >= len(row):
            raise ValueError("resultado fuera del rango de clases")
        total += sum((float(p) - float(i == outcome)) ** 2 for i, p in enumerate(row))
    return total / len(outcomes)


def expected_calibration_error(probabilities: Sequence[Sequence[float]],
                               outcomes: Sequence[int], bins: int = 10) -> float:
    """ECE top-label: confianza del pronóstico vs frecuencia de acierto por bin."""
    if bins <= 0 or not probabilities or len(probabilities) != len(outcomes):
        raise ValueError("bins debe ser positivo y las entradas no vacías deben coincidir")
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for row, outcome in zip(probabilities, outcomes, strict=True):
        if not row or outcome < 0 or outcome >= len(row):
            raise ValueError("fila o resultado inválido")
        confidence = max(float(p) for p in row)
        predicted = max(range(len(row)), key=lambda i: row[i])
        buckets[min(int(confidence * bins), bins - 1)].append((confidence, predicted == outcome))
    n = len(outcomes)
    return sum(
        len(bucket) / n * abs(
            sum(c for c, _ in bucket) / len(bucket)
            - sum(ok for _, ok in bucket) / len(bucket)
        )
        for bucket in buckets if bucket
    )
