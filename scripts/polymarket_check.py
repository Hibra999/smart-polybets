#!/usr/bin/env python
"""Verifica la conexión con Polymarket CLOB V2 (SOLO LECTURA, no envía órdenes).

Usa el SDK oficial `polymarket` (SecureClient), nativo de CLOB V2 + pUSD. Deriva el
proxy wallet desde POLYMARKET_PRIVATE_KEY y consulta tu balance/allowance de pUSD.
Sirve para confirmar que todo está conectado ANTES de `place_bets --live`.

    python scripts/polymarket_check.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8


def main() -> None:
    from core.polymarket_client import build_secure_client
    from core.exceptions import PolymarketClientError

    try:
        client = build_secure_client()
    except PolymarketClientError as exc:
        print(f"[FALTA] {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] No se pudo crear el cliente: {type(exc).__name__}: {exc}")
        return

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
        if bal > 0 and approved:
            print("\nTodo listo. Para operar real: POLYMARKET_LIVE=1 + place_bets --live")
        elif bal <= 0:
            print("\nSin pUSD libre: depositá USDC en Polymarket (se wrappea a pUSD).")
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] No se pudo leer el balance: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
