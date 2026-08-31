#!/usr/bin/env python
"""Verifica la conexión con Polymarket CLOB V2 (SOLO LECTURA, no envía órdenes).

Usa el SDK oficial `polymarket` (SecureClient), nativo de CLOB V2 + pUSD. Deriva el
proxy wallet desde POLYMARKET_PRIVATE_KEY y consulta tu balance/allowance de pUSD.
Sirve para confirmar que todo está conectado ANTES de `place_bets --live`.

    python scripts/polymarket_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from core.console import enable_utf8
from core.env import load_env

enable_utf8()  # consola Windows: stdout/stderr en UTF-8
load_env(REPO / ".env")


def main() -> None:
    from core.exceptions import PolymarketClientError
    from core.polymarket_client import build_secure_client

    try:
        client = build_secure_client()
    except PolymarketClientError:
        print("[ERROR] No se pudo crear el cliente (configuración o SDK).")
        raise SystemExit(1) from None
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] No se pudo crear el cliente: {type(exc).__name__}")
        raise SystemExit(1) from None

    signer = getattr(client.signer, "address", client.signer)
    wallet = getattr(client, "wallet", None)
    print(f"[OK] signer (MetaMask)      : {signer}")
    print(f"[OK] wallet derivada (funder): {wallet}")

    try:
        ba = client.get_balance_allowance(asset_type="COLLATERAL")
        bal = int(getattr(ba, "balance", 0)) / 1e6  # pUSD, 6 decimales
        allows = getattr(ba, "allowances", {}) or {}
        approved = any(int(v) > 0 for v in allows.values())
        print(f"[OK] Balance pUSD           : {bal:.2f}")
        print(f"[OK] Allowance Exchange V2  : {'aprobado' if approved else 'NO aprobado (falta approve_erc20)'}")
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] No se pudo leer el balance: {type(exc).__name__}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
