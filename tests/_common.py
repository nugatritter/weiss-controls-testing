"""Gemeinsame Hilfen der Prüfskripte: Argumente, Sicherheitsabfrage und einheitliche Ausgabe."""
import argparse
import os
import sys

BESTAETIGT = "[BESTÄTIGT]"
NICHT_BESTAETIGT = "[NICHT BESTÄTIGT]"
PREFIX = "WEISS:TEST:"

_results: list[bool] = []


def parse_args(description: str, ws: bool = False, api: bool = False) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    if ws:
        p.add_argument("--ws", default=os.getenv("WS_URL", "ws://localhost:8080"),
                       help="WebSocket-Adresse der PV-Brücke (Standard: ws://localhost:8080)")
    if api:
        p.add_argument("--api", default=os.getenv("API_URL", "http://localhost:8000"),
                       help="Adresse der WEISS-API im Demo-Modus (Standard: http://localhost:8000)")
    p.add_argument("--yes", action="store_true",
                   help="bestätigt, dass gegen eine TEST-Installation geprüft wird "
                        "(Skripte schreiben PVs WEISS:TEST:* und legen Snapshots an)")
    args = p.parse_args()
    if not args.yes:
        sys.exit("Abbruch: Dieses Skript schreibt PVs (WEISS:TEST:*) beziehungsweise legt Snapshots an.\n"
                 "Nur gegen eine Test-Installation ausführen und mit --yes bestätigen.")
    return args


def report(claim: str, confirmed: bool, detail: str = "") -> None:
    """Gibt eine Aussage mit Ergebnis aus. BESTÄTIGT heißt: das beschriebene Verhalten tritt auf."""
    print(f"{BESTAETIGT if confirmed else NICHT_BESTAETIGT} {claim}")
    if detail:
        print(f"    {detail}")
    _results.append(confirmed)


def summary() -> None:
    print(f"\nZusammenfassung: {sum(_results)} von {len(_results)} Aussagen bestätigt.")
