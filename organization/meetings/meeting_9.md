# Meeting — 2026-06-22

**Moderator:** Abdelrahman
**Note-taker:** Nils
**Attendees:** Abdelrahman, Nils, Andreas, Waleed, Adrian, Johannes

## Agenda
1. Statusrunde (Fortschritt seit dem letzten Meeting)
2. Datensammlung: Umfang, Aufgabenzuschnitt, Lever-Positionen, Labeling
3. Inferenz-Ausführung: Action-Horizon vs. Queue
4. Frontend/Web-UI: Datendownload, Movement-Integration, Model-Auswahl
5. Kalibrierung/Homing
6. CI/CD-Status

## Discussion

**Frontend / Web-UI**
- Umbau läuft, sodass Daten direkt vom Pi heruntergeladen werden können, statt sie erst lokal zu speichern und dann zu ziehen. Ziel: bis Mittwoch fertig.
- Idee, ein Skript einzubauen, das ein ganzes Directory direkt auf den Server hochlädt; kurzfristig wird das manuelle Kopieren als Zwischenlösung akzeptiert.
- Perspektivisch: Model-Selection im Frontend (Dropdown zwischen Base und den finetuneten Modellen), erfordert aber Modellwechsel auf der GPU — als aufwändiger eingeschätzt, zunächst zurückgestellt.
- Echtzeit-Kamerabild-Vorschau im Frontend als Validierungshilfe genannt.

**Finetuning (Abdelrahman)**
- Letzte Woche Finetuning durchgeführt; in der Präsentation gut aufgenommen.
- Mit verschiedenen Hyperparametern getestet; Beobachtung: Modell overfittet wegen zu kleinem Datensatz. Die Seed-Varianz liegt höher als der Unterschied zwischen den besten Hyperparametern → Schlussfolgerung: mehr Daten sammeln.
- Bash-Skript geschrieben, das das Finetuning auf der GPU startet (Docker-Environment wird mit hochgefahren).
- USB-Kamera-Problem bei der Inferenz gelöst; Inferenz läuft jetzt mit beiden Kameras. Inferenz wurde außerdem mit den Finetuning-Scripts verknüpft.

**CI/CD (Abdelrahman)**
- Docker-basierte Pipeline eingerichtet: bei einer Änderung im Backend wird das Image automatisch gebaut, verifiziert und auf der GPU deployt.

**Kalibrierung / Homing / manuelle Steuerung**
- Versuch, den Controller zu integrieren (manuelle Kalibrierung aktuell nicht optimal, da nach jedem Durchlauf neu gestartet werden muss).
- Homing-Funktion in Arbeit; Anpassungen im Frontend stehen noch aus.
- Idee, alles nach ROS2 umzuwandeln — als nicht notwendig eingestuft, aber als Option offengehalten.

**Datensammlung**
- Am Mittwoch mehrere Stunden Daten gesammelt, ca. 32 Beispiele aufgenommen; am Folgetag nachbereitet.
- Bug entdeckt: an einer Stelle war ein Default gesetzt, der alle Labels überschrieben hat (alle Beispiele wurden gleich gelabelt) — behoben.
- Skript geschrieben, das die ersten Bilder jeder Aufnahme ausgibt, um zu sehen, in welche Richtung der Hebel liegt (bei gemischten Lever-Orientierungen sonst unklar).
- Umstellung: die End-Position wird jetzt direkt berechnet statt am Ende aus den aufgezeichneten Werten — Performance soll noch getestet werden.

**Aufgabenzuschnitt für den großen Datensatz**
- Vorschlag, die Aufgabe für die erste Version eng zu fassen: Hebel nur in einer Richtung umlegen (immer vom Roboter weg), Hebel aber an verschiedenen Positionen platzieren. Grundbewegung bleibt gleich → für das Modell besser lernbar.
- Schwierige Richtungen (auch für Menschen schwer) zunächst komplett weglassen.
- Diskussion, ob der Roboter beim Datensammeln nichts außer dem Hebel sehen sollte (früher teils eine LEGO-Platte im Bild, damit das Modell lernt, sie zu ignorieren — evtl. zu viel für das kleine Modell).
- Idee, dieselbe Lever-Position mehrfach aufzunehmen (statt nach jeder Aufnahme die Position zu wechseln), damit die Bewegung verlässlicher gelernt wird.
- Label/Language-Instruction: rot→grün und grün→rot auseinanderhalten; Sorge, dass das Modell bei bloßem "Flip" die Richtung falsch lernt. Vorschlag, mehrere Formulierungs-Varianten (z.B. per Button, zufällig aus ~10 Varianten) statt freien Text.
- Frage, wie viele Demos für den großen Datensatz nötig sind — Orientierung am Paper (Größenordnung 100).

**Inferenz-Ausführung: Action-Horizon vs. Queue**
- Sorge, den nächsten Inferenzschritt schon zu berechnen, bevor die vorige Bewegung fertig ist → mögliche Verzögerung/Ruckeln.
- Der TA berichtet aus eigener Erfahrung: er hat teils nur einen von mehreren vorhergesagten Action-Werten ausgeführt; am Ende funktionierte es bei ihm besser, jeweils mehrere (z.B. 4) Schritte auszuführen. Beobachtung: die ersten Schritte waren konservativ, spätere hatten größere Deltas — evtl. den ersten Schritt weglassen und die folgenden ausführen.
- Diskutiert: nach N Schritten ein frisches Kamerabild holen und neu inferieren; Option, eine Queue mit Zeitstempeln zu führen und veraltete Bewegungen per Timeout zu verwerfen.
- Sorge vor schrittweisem Zittern (Stocken) und vor Rückwärtsbewegung, wenn das Kamerabild hinterherhinkt.
- Konsens-Tendenz: zunächst mit Action-Horizon sequentiell arbeiten (statt eine Queue anzusammeln); Interpolation/Smoothing als spätere Option.

**Sicherheit / PWM**
- Bewegung wird per PWM ausgeführt; PWM-Startwert steht auf 80 (als etwas hoch eingeschätzt, aber okay).
- Wichtig: die Octo-Ausführung muss dieselbe Movement-Funktion nutzen wie der Controller, damit die Safety-Limits eingehalten werden. Diese Funktion sollte tief genug integriert sein.

**Weiteres**
- Feature-Idee einer anderen Gruppe: Recordings im Dataset-Builder mit Notizen versehen (z.B. Lever-Position benennen) und ins Metadata schreiben, um später gezielt filtern zu können. Language-Instructions lassen sich aber ohnehin aus den Commands auslesen.
- VPN auf dem Pi als Möglichkeit für kabellosen Betrieb genannt (noch nicht getestet; IP-Handling zu klären).
- Präsentation liegt in Organisation (Ordner); ein Branch für die Präsentation wurde/soll erstellt werden.

## Decisions
- Mehr Daten sammeln (großer Datensatz), da der aktuelle zu klein ist (Overfitting, Seed-Varianz > Hyperparameter-Effekt).
- Aufgabe für die erste Version eng fassen: nur eine Bewegungsrichtung (vom Roboter weg), Hebel an verschiedenen Positionen; schwierige Richtungen weglassen.
- Bei der Inferenz-Ausführung zunächst mit Action-Horizon sequentiell arbeiten, keine Queue ansammeln; Smoothing/Interpolation ggf. später.
- Octo-Movement über dieselbe (limit-geprüfte) Funktion wie der Controller ausführen.
- Vor dem Aufnehmen des großen Datensatzes zuerst die kleinen Quality-of-Life-Features implementieren.
- main-Branch nehmen; einige machen Finetuning, der Rest die übrigen Aufgaben.

## Action Items

| Task | Owner | Deadline |
|------|-------|----------|
| Frontend-Datendownload vom Pi fertigstellen | Nils & Andreas| Mittwoch |
| Language-Instruction-Recording-Feature: Commands komprimieren + Instruction hinzufügen, in Branch pushen | Nils | Dienstagabend |
| Movement-Funktion (xyz-Zielkoordinate mit IK, limit-geprüft) für Octo-Nutzung bereitstellen | | Mittwoch |
| Inferenz mit Movement live testen (ohne Home-Funktion anzufassen) | Abdelrahman | |
| Controller-Inputs festschreiben | Adrian | |
| Homing-Funktion testen + Ergebnis dem Team schreiben | Waleed | Mittwoch |
| Großen Datensatz aufnehmen (nach den kleinen Features) | Team | nächste Woche(n) |
| Buttons/Instruction-Varianten fürs Frontend liefern | Andreas | |

## Next Meeting
- **Moderator:** Johannes
- **Note-taker:** Nils