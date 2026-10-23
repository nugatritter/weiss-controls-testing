#!/usr/bin/env python3
"""Prüft, ob der Snapshot der Brücke vom Standardprotokoll abhängt (EPICS_DEFAULT_PROTOCOL).

Das Skript abonniert drei PVs ausdrücklich mit dem Präfix ca:// und fordert einen Snapshot an.
Zwei Läufe mit unterschiedlicher Brücken-Konfiguration zeigen den Effekt:
    EPICS_DEFAULT_PROTOCOL=ca   -> erwartet: 3 PVs im Snapshot
    EPICS_DEFAULT_PROTOCOL=pva  -> Befund:   0 PVs, obwohl alle drei PVs abonniert und lesbar sind
Nutzung:  python3 tests/bridge_default_protocol.py --yes [--ws ws://localhost:8080]
Hinweis: Die Brücke muss nach dem Wechsel der Variable neu gestartet werden. Das Skript schreibt nichts.
"""
import asyncio
import json

import websockets

from _common import PREFIX, parse_args, report, summary

SUBSCRIBED = ["COUNTER", "SETPOINT", "SWITCH"]


async def main(url: str) -> None:
    async with websockets.connect(url, max_size=None, open_timeout=10) as ws:
        await ws.send(json.dumps({"type": "subscribe", "pvs": ["ca://" + PREFIX + n for n in SUBSCRIBED]}))
        await asyncio.sleep(3)
        await ws.send(json.dumps({"type": "snapshot", "exclude": []}))
        while True:
            raw = await asyncio.wait_for(ws.recv(), 10)
            if isinstance(raw, bytes):
                continue
            msg = json.loads(raw)
            if msg.get("type") == "snapshot":
                break
    names = sorted(k.split("://", 1)[-1].replace(PREFIX, "") for k in msg["pvs"])
    report("Mit ausdrücklich abonnierten ca://-PVs fehlen PVs im Snapshot (Standardprotokoll der Brücke nicht 'ca').",
           msg["count"] < len(SUBSCRIBED),
           f"abonniert: {len(SUBSCRIBED)}, im Snapshot: {msg['count']} {names}")
    summary()


if __name__ == "__main__":
    args = parse_args(__doc__, ws=True)
    asyncio.run(main(args.ws))
