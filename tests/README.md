# Prüfskripte für die Befunde im Vergleichsdokument

Diese Skripte machen die Live-Befunde aus [`docs/vergleich-weiss-phoebus.adoc`](../docs/vergleich-weiss-phoebus.adoc)
nachvollziehbar. Sie sprechen die PV-Brücke (`weiss-epicsws`) und die API von WEISS an, so wie es ein Browser täte, aber
ohne Anmeldung an der Brücke. Sie testen **nicht** die Weboberfläche.

> **Achtung:** Die Skripte schreiben PVs (`WEISS:TEST:*`) und legen Snapshots an. Nur gegen eine Test-Installation mit der
> Test-SoftIOC aus [`softioc/`](../softioc) ausführen. Ohne `--yes` brechen sie ab.

## Überblick

| Skript | Prüft | Befund im Dokument |
|---|---|---|
| `bridge_checks.py` | anonyme Verbindung, fremde Origin, globale Schreibkanäle, Snapshot-Inhalt, Restore-Verhalten | Praxisbefunde 1, 2, 16 |
| `bridge_default_protocol.py` | Snapshot und Standardprotokoll (`EPICS_DEFAULT_PROTOCOL`) | Praxisbefund 21, Zeile „Protokolltrennung“ |
| `api_snapshot_checks.py` | Rechte, ID-Kollision und Pfadkollision der Snapshot-API | Praxisbefunde 17, 18 |
| `bridge_message_size.py` | Größe eines Skalar-Updates (Grundlage der 200-Byte-Annahme) | Abschnitt „Leistung und Skalierung“ |

Jede Prüfung gibt `[BESTÄTIGT]` aus, wenn das beschriebene Verhalten auftritt, sonst `[NICHT BESTÄTIGT]`. Die Skripte
dokumentieren den Ist-Zustand des geprüften Standes. Nach Korrekturen im Upstream sind andere Ergebnisse zu erwarten.
Exit-Code 0 heißt: Der Lauf war vollständig. Bei fehlender Verbindung brechen sie mit einer Fehlermeldung ab.

## Voraussetzungen

Ein Rechner, von dem aus `localhost:8080` (Brücke) und `localhost:8000` (API) erreichbar sind. Unter macOS mit Podman-VM
ist das nicht der Fall, die Brücke läuft im Netz der VM. Dann auf einem Linux-Host oder in der VM ausführen.

```sh
python3 -m venv ~/weiss-check && ~/weiss-check/bin/pip install websockets httpx
```

Komponenten (Befehle wie in der [README](../README.md); die API braucht hier das Demo-Login und ein Volume):

```sh
podman run -d --name weiss-softioc --network host localhost/weiss-softioc:latest
podman run -d --name weiss-epicsws --network host --env-file ~/.config/weiss/weiss.env localhost/weiss-epicsws:latest
podman run -d --name weiss-api -p 8000:8000 --env-file ~/.config/weiss/weiss.env \
  -v ~/.config/weiss/roles.toml:/config/roles.toml:ro -e ROLES_CONFIG_PATH=/config/roles.toml \
  -v weiss-storage:/app/storage localhost/weiss-api:latest
```

In `~/.config/weiss/weiss.env` muss `DEMO_MODE=true` stehen (für `api_snapshot_checks.py`) und `EPICS_DEFAULT_PROTOCOL=ca`.

## Ausführen

```sh
PY=~/weiss-check/bin/python
$PY tests/bridge_checks.py --yes
$PY tests/bridge_message_size.py --yes
$PY tests/api_snapshot_checks.py --yes
$PY tests/bridge_default_protocol.py --yes          # Lauf 1: Standardprotokoll ca, erwartet 3 PVs im Snapshot
```

Für Lauf 2 der Providerprüfung die Brücke mit Standardprotokoll `pva` neu starten und das Skript wiederholen
(erwartet laut Befund: 0 PVs im Snapshot):

```sh
sed 's/^EPICS_DEFAULT_PROTOCOL=.*/EPICS_DEFAULT_PROTOCOL=pva/' ~/.config/weiss/weiss.env > /tmp/weiss-pva.env
podman rm -f weiss-epicsws
podman run -d --name weiss-epicsws --network host --env-file /tmp/weiss-pva.env localhost/weiss-epicsws:latest
$PY tests/bridge_default_protocol.py --yes
```

Danach die Brücke wieder mit der normalen `weiss.env` starten. Mit anderen Adressen: `--ws ws://HOST:8080`,
`--api http://HOST:8000` oder die Umgebungsvariablen `WS_URL` und `API_URL`.

Die API legt je OPI-Pfad einen Ordner im Snapshot-Speicher an und entfernt ihn nicht. Nach `api_snapshot_checks.py` bleiben
leere Ordner `tests_api-check_*` im Volume.

## Lauflog

[`results/2026-10-23_sandbox.txt`](results/2026-10-23_sandbox.txt) enthält die Ausgabe eines Laufs vom 23. Oktober 2026.
Er stammt aus einer Sandbox und **nicht** aus dem Podman-Deployment, und zwar vom Autor der Ausgangsfassung, ist also
keine unabhängige Wiederholung:

- WEISS-Commit `850afe2` (API und Brücke), EPICS Base R7.0.9 nativ gebaut, `softIoc` mit `softioc/test.db`.
- Die Sandbox hat kein IPv6. Dort startet der PVA-Client (`p4p`) der Brücke nicht. Für den Lauf wurde in `epicsWS.py`
  nur diese eine Zeile durch eine Attrappe ersetzt. Channel Access, Snapshot und Restore laufen unverändert:

```python
class _StubPVA:  # nur für Umgebungen ohne IPv6
    _latest_value = {}
    def subscribe(self, *a, **k): pass
    def unsubscribe(self, *a, **k): pass
    def unsubscribe_all(self, *a, **k): pass
    def write_to_pv(self, *a, **k): pass
    def close(self): pass
clients[PVA_PROVIDER_KEY] = _StubPVA()      # statt PVAClient(pva_callback, pva_disconnect_callback)
```

Ein unabhängiger Lauf im Podman-Deployment steht aus.
