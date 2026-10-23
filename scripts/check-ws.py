#!/usr/bin/env python3
"""Prüft die PV-Brücke weiss-epicsws über den WebSocket (ohne Anmeldung, nur Port 8080).

Nutzung:
    python3 scripts/check-ws.py [ws://localhost:8080] [--write]

Ohne --write: abonniert WEISS:TEST:COUNTER und wartet auf einen Wert.
Mit --write:  schreibt zusätzlich WEISS:TEST:SETPOINT = 42.5 und wartet,
              bis dieser Wert über die Abo-Updates zurückkommt.
Exit-Code 0 = Prüfung bestanden, 1 = nicht bestanden.
Benötigt: pip install websockets
"""
import asyncio
import json
import sys

import websockets

COUNTER = "ca://WEISS:TEST:COUNTER"
SETPOINT = "ca://WEISS:TEST:SETPOINT"
TIMEOUT_S = 10


async def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    url = args[0] if args else "ws://localhost:8080"
    do_write = "--write" in sys.argv

    async with websockets.connect(url, open_timeout=TIMEOUT_S) as ws:
        print(f"Verbunden mit {url}")
        await ws.send(json.dumps({"type": "subscribe", "pvs": [COUNTER, SETPOINT]}))

        seen = {}
        if do_write:
            await asyncio.sleep(1)  # kurz warten, bis das Abo steht
            await ws.send(json.dumps({"type": "write", "pv": SETPOINT, "value": 42.5}))
            print("Schreibauftrag gesendet: WEISS:TEST:SETPOINT = 42.5")

        try:
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), TIMEOUT_S))
                if msg.get("type") != "update":
                    continue
                pv = msg.get("pv")
                seen[pv] = msg.get("value")
                print(f"  {pv} = {msg.get('value')}")
                if "WEISS:TEST:COUNTER" in seen and not do_write:
                    break
                if do_write and seen.get("WEISS:TEST:SETPOINT") == 42.5:
                    break
        except asyncio.TimeoutError:
            pass

    if "WEISS:TEST:COUNTER" not in seen:
        print("FEHLER: kein Lesewert für WEISS:TEST:COUNTER", file=sys.stderr)
        return 1
    if do_write and seen.get("WEISS:TEST:SETPOINT") != 42.5:
        print("FEHLER: Schreibwert 42.5 kam nicht zurück", file=sys.stderr)
        return 1
    print("OK: Lesen" + (" und Schreiben" if do_write else "") + " über die Brücke funktioniert")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
