#!/usr/bin/env python3
"""Misst die Größe der Update-Nachrichten der PV-Brücke (Grundlage der 200-Byte-Annahme im Skalierungsmodell).

Nutzung:  python3 tests/bridge_message_size.py --yes [--ws ws://localhost:8080] [--seconds 14]
Das Skript abonniert WEISS:TEST:COUNTER und WEISS:TEST:SINE (2 Hz) und schreibt nichts.
Gemessen wird die JSON-Nutzlast in Byte. Der WebSocket-Kopf kommt bei Nutzlasten von 126 bis 65535 Byte mit 4 Byte hinzu.
"""
import argparse
import asyncio
import json
import statistics
import sys

import websockets

from _common import PREFIX, parse_args, report, summary


async def main(url: str, seconds: float) -> None:
    first, sizes = {}, []
    async with websockets.connect(url, max_size=None, open_timeout=10) as ws:
        await ws.send(json.dumps({"type": "subscribe", "pvs": ["ca://" + PREFIX + "COUNTER", "ca://" + PREFIX + "SINE"]}))
        end = asyncio.get_event_loop().time() + seconds
        while asyncio.get_event_loop().time() < end:
            try:
                raw = await asyncio.wait_for(ws.recv(), 3)
            except asyncio.TimeoutError:
                break
            if isinstance(raw, bytes):
                continue
            msg = json.loads(raw)
            if msg.get("type") != "update":
                continue
            size = len(raw.encode("utf-8"))
            if msg["pv"] not in first:
                first[msg["pv"]] = size
            else:
                sizes.append(size)
    if not sizes:
        sys.exit("Fehler: keine Folge-Updates empfangen. Läuft die Test-IOC?")
    median = int(statistics.median(sizes))
    print(f"Erste Nachricht je PV (mit Metadaten): {first}")
    print(f"Folge-Updates: {len(sizes)}, JSON-Nutzlast in Byte: min {min(sizes)}, Median {median}, max {max(sizes)}")
    report("Ein Skalar-Update (Folge-Update) belegt rund 200 Byte einschließlich WebSocket-Kopf (150 bis 250).",
           150 <= median + 4 <= 250, f"Median {median} Byte Nutzlast + 4 Byte Kopf (PV-Name mit "
           f"{len(PREFIX + 'COUNTER')} Zeichen; längere Namen vergrößern die Nachricht)")
    summary()


if __name__ == "__main__":
    extra = argparse.ArgumentParser(add_help=False)
    extra.add_argument("--seconds", type=float, default=14)
    known, rest = extra.parse_known_args()
    sys.argv = [sys.argv[0]] + rest
    args = parse_args(__doc__, ws=True)
    asyncio.run(main(args.ws, known.seconds))
