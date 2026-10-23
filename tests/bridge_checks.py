#!/usr/bin/env python3
"""Prüft das Verhalten der PV-Brücke (weiss-epicsws) über den WebSocket, ohne Anmeldung.

Voraussetzung: Test-IOC aus softioc/ läuft, die Brücke ist auf localhost:8080 erreichbar.
Nutzung:  python3 tests/bridge_checks.py --yes [--ws ws://localhost:8080]

Das Skript legt keine Dateien an. Es schreibt WEISS:TEST:SETPOINT und WEISS:TEST:COUNTER und stellt
SETPOINT am Ende wieder her. BESTÄTIGT bedeutet: das im Vergleichsdokument beschriebene Verhalten tritt auf.
"""
import asyncio
import json
import sys

import websockets

from _common import PREFIX, parse_args, report, summary

NAMES = ["COUNTER", "SINE", "SETPOINT", "READBACK", "SWITCH", "STATUS", "MESSAGE", "WAVE"]
DISPLAY_ONLY = ["COUNTER", "SINE", "READBACK", "STATUS"]


def full(name: str) -> str:
    return "ca://" + PREFIX + name


def bare(pv: str) -> str:
    return pv.split("://", 1)[-1]


class Client:
    """Dünner WebSocket-Client. Merkt sich die zuletzt gesehenen Werte (Binärframes werden übersprungen)."""

    def __init__(self, url: str, origin: str | None = None):
        self.url, self.origin, self.values = url, origin, {}

    async def __aenter__(self):
        self.ws = await websockets.connect(self.url, origin=self.origin, max_size=None, open_timeout=10)
        return self

    async def __aexit__(self, *exc):
        await self.ws.close()

    @property
    def status(self) -> int:
        return self.ws.response.status_code

    async def send(self, msg: dict) -> None:
        await self.ws.send(json.dumps(msg))

    async def next_json(self, timeout: float) -> dict:
        while True:
            raw = await asyncio.wait_for(self.ws.recv(), timeout)
            if isinstance(raw, bytes):
                continue
            msg = json.loads(raw)
            if msg.get("type") == "update" and "value" in msg:
                self.values[bare(msg["pv"])] = msg["value"]
            return msg

    async def wait_type(self, typ: str, timeout: float = 10) -> dict:
        while True:
            msg = await self.next_json(timeout)
            if msg.get("type") == typ:
                return msg

    async def wait_value(self, name: str, predicate, timeout: float = 5):
        """Wartet, bis ein Update der PV das Prädikat erfüllt. Gibt den Wert oder None zurück."""
        key = PREFIX + name
        end = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < end:
            if key in self.values and predicate(self.values[key]):
                return self.values[key]
            try:
                await self.next_json(0.5)
            except asyncio.TimeoutError:
                pass
        return self.values.get(key) if predicate(self.values.get(key)) else None

    async def settle(self, seconds: float) -> None:
        end = asyncio.get_event_loop().time() + seconds
        while asyncio.get_event_loop().time() < end:
            try:
                await self.next_json(0.3)
            except asyncio.TimeoutError:
                pass


async def main(url: str) -> None:
    # 1 und 2: Verbindung ohne Cookie, Token oder Anmeldung, auch mit fremder Origin
    async with Client(url) as anon:
        report("Die Brücke nimmt eine anonyme WebSocket-Verbindung an (HTTP 101).", anon.status == 101,
               f"Status: {anon.status}")
    async with Client(url, origin="https://evil.example") as foreign:
        report("Die Brücke nimmt eine Verbindung mit fremder Origin an (HTTP 101).", foreign.status == 101,
               f"Origin https://evil.example, Status: {foreign.status}")

    async with Client(url) as a, Client(url) as b:
        await a.send({"type": "subscribe", "pvs": [full(n) for n in NAMES]})
        await a.settle(3)
        original = a.values.get(PREFIX + "SETPOINT")
        if original is None:
            sys.exit("Fehler: keine Werte von WEISS:TEST:SETPOINT. Läuft die Test-IOC und passt EPICS_CA_ADDR_LIST?")
        try:
            # 3: Client B schreibt eine PV, die nur Client A abonniert hat
            target = original + 1.5 if original + 1.5 <= 100 else original - 1.5
            await b.send({"type": "write", "pv": full("SETPOINT"), "value": target})
            seen = await a.wait_value("SETPOINT", lambda v: v == target, 5)
            report("Client B schreibt eine PV, die nur Client A abonniert hat (Kanäle sind global).",
                   seen == target, f"SETPOINT {original} -> {seen}")

            # 4: Snapshot-Inhalt
            await a.send({"type": "snapshot", "exclude": []})
            snap = await a.wait_type("snapshot")
            pvs = {bare(k): v for k, v in snap["pvs"].items()}
            if snap["count"] == 0:
                print("    Hinweis: Der Snapshot ist leer. Das passiert, wenn EPICS_DEFAULT_PROTOCOL der Brücke nicht 'ca' ist\n"
                      "    (siehe bridge_default_protocol.py). Die Prüfungen 4 bis 6 verwenden dann die zuletzt gesehenen Werte.")
            else:
                report("Der Snapshot enthält auch reine Anzeige-PVs, jeweils mit Alarm und Zeitstempel.",
                       all(PREFIX + n in pvs for n in DISPLAY_ONLY)
                       and all({"alarm", "timeStamp"} <= set(pvs[PREFIX + n]) for n in DISPLAY_ONLY),
                       f"{snap['count']} PVs im Snapshot: {sorted(n.replace(PREFIX, '') for n in pvs)}")
                wave = pvs.get(PREFIX + "WAVE", {})
                report("Array-Werte stehen im Snapshot nur als b64arr, value ist leer.",
                       wave.get("value") is None and bool(wave.get("b64arr")),
                       f"WAVE: value={wave.get('value')!r}, b64arr vorhanden={bool(wave.get('b64arr'))}")

            # 5 und 6: Restore wie in der Oberfläche (nur 'value' je PV), mit verändertem COUNTER und einer fehlenden PV
            current = a.values.get(PREFIX + "COUNTER", 0)
            counter_target = (int(current) + 40) % 100
            payload = {}
            for n in NAMES:
                v = pvs.get(PREFIX + n, {}).get("value", a.values.get(PREFIX + n))
                payload[full(n)] = {"value": None if n == "WAVE" else v}
            payload[full("COUNTER")] = {"value": counter_target}
            payload[full("DOES_NOT_EXIST")] = {"value": 1}
            await a.send({"type": "restore", "pvs": payload})
            result = await a.wait_type("restore_result")
            missing = [r for r in result["results"] if r["pv"].endswith("DOES_NOT_EXIST")]
            report("Der Restore meldet auch für eine nicht vorhandene PV und für ein Array Erfolg.",
                   result["succeeded"] == result["total"] and bool(missing) and missing[0]["success"],
                   f"{result['succeeded']} von {result['total']} als erfolgreich gemeldet")
            jumped = await a.wait_value("COUNTER", lambda v: v is not None and (int(v) - counter_target) % 100 <= 4, 4)
            report("Der Restore schreibt auch eine reine Anzeige-PV (COUNTER) zurück.", jumped is not None,
                   f"COUNTER vorher ca. {current}, im Restore {counter_target}, danach gesehen: {jumped}")
        finally:
            await b.send({"type": "write", "pv": full("SETPOINT"), "value": original})
            await asyncio.sleep(0.5)
    summary()


if __name__ == "__main__":
    args = parse_args(__doc__, ws=True)
    asyncio.run(main(args.ws))
