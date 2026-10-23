#!/usr/bin/env python3
"""Prüft die Snapshot-API von WEISS (Rechte, Ablage, IDs). Die API muss im Demo-Modus laufen (DEMO_MODE=true).

Nutzung:  python3 tests/api_snapshot_checks.py --yes [--api http://localhost:8000]
Das Skript meldet sich als Demo-Operator und Demo-Developer an, legt Snapshots unter dem Pfad
"tests/api-check/..." an und löscht sie am Ende wieder.
"""
import json
import time
import urllib.parse

import httpx

from _common import parse_args, report, summary

OPI = "tests/api-check/demo.opi.json"
OPI_SLASH = "tests/api-check/a/b.opi.json"
OPI_UNDERSCORE = "tests/api-check/a_b.opi.json"
PVS = {"X:PV": {"value": 1}}


def login(base: str, role: str) -> httpx.Client:
    c = httpx.Client(base_url=base, timeout=10)
    r = c.get("/api/v1/auth/demo/authorize", params={"demo_role": role})
    r.raise_for_status()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.json()["authorize_url"]).query)
    c.post("/api/v1/auth/callback", json={"provider": "demo", "code": q["code"][0], "state": q["state"][0],
                                          "redirect_uri": "http://localhost/auth/callback"}).raise_for_status()
    return c


def save(c: httpx.Client, name: str, opi: str = OPI) -> httpx.Response:
    return c.put("/api/v1/snapshots", json={"name": name, "opi_file": opi, "pvs": PVS})


def listing(c: httpx.Client, opi: str = OPI) -> list[dict]:
    return c.get("/api/v1/snapshots", params={"opi_file": opi}).json()


def main(base: str) -> None:
    created: list[tuple[str, str]] = []  # (opi, id) zum Aufräumen
    anon = httpx.Client(base_url=base, timeout=10)
    report("Anonyme Anfragen an die Snapshot-API werden abgewiesen (401).",
           anon.put("/api/v1/snapshots", json={"name": "x", "opi_file": OPI, "pvs": {}}).status_code == 401)

    op = login(base, "operator")
    dev = login(base, "developer")
    try:
        r = save(op, "operator-snapshot")
        created.append((OPI, r.json()["id"]))
        report("Ein Demo-Operator darf Snapshots speichern (keine Rollenprüfung).", r.status_code == 200,
               f"Status {r.status_code}")

        # Zwei Speicherungen in derselben Sekunde: kurz vor einem Sekundenwechsel starten, beide direkt hintereinander
        same_id = False
        for _ in range(5):
            time.sleep(1 - (time.time() % 1) + 0.05)
            r1, r2 = save(op, "erster"), save(op, "zweiter")
            created += [(OPI, r1.json()["id"]), (OPI, r2.json()["id"])]
            if r1.json()["id"] == r2.json()["id"]:
                same_id = True
                break
        names = [s["name"] for s in listing(op)]
        report("Zwei Speicherungen in derselben Sekunde überschreiben sich (ID mit Sekundenauflösung).",
               same_id and "erster" not in names and "zweiter" in names,
               f"gleiche ID: {same_id}, Namen in der Liste: {names}")

        detail = op.get(f"/api/v1/snapshots/{r2.json()['id']}", params={"opi_file": OPI}).json()
        report("Der gespeicherte Snapshot enthält keinen Benutzer.",
               not any(k in detail for k in ("user", "author", "username", "owner")),
               f"Felder: {sorted(detail)}")

        seen = [s["name"] for s in listing(dev)]
        victim = listing(dev)[0]["id"]
        deleted = dev.delete(f"/api/v1/snapshots/{victim}", params={"opi_file": OPI})
        report("Ein anderer Benutzer (Developer) sieht und löscht Snapshots des Operators.",
               "operator-snapshot" in seen and deleted.status_code == 200,
               f"sichtbar: {seen}, Löschen: Status {deleted.status_code}")

        a = save(op, "für a/b", OPI_SLASH)
        created.append((OPI_SLASH, a.json()["id"]))
        other = [s["name"] for s in listing(op, OPI_UNDERSCORE)]
        report("Die OPI-Pfade a/b.opi.json und a_b.opi.json teilen sich einen Snapshot-Ordner.",
               "für a/b" in other, f"Liste für a_b.opi.json: {other}")
    finally:
        for opi, sid in created:
            op.delete(f"/api/v1/snapshots/{sid}", params={"opi_file": opi})
    summary()


if __name__ == "__main__":
    args = parse_args(__doc__, api=True)
    main(args.api)
