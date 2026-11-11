# auto-deal-scout-daten

Preisgeschichte für den Auto Deal Scout (Mazda 3).

- `daten/as24_voll_JJJJ-MM-TT.csv`: Vollabzug aller AutoScout24 Listen Inserate (Mazda 3, EZ ab 2017, bis 130.000 km, 7.000 bis 21.000 €), getrennt nach Getriebe abgefragt. Der Sonntagslauf legt jede Woche eine neue Datei ab.
- `daten/bestand_seed_2026-11-08.csv`: erster Bestand vom 08.11.2026 (AutoScout24 bis 17.500 €, Kleinanzeigen, Autohero).
- `skripte/marktmodell.py`: schätzt das Marktmodell aus den Daten (Aufruf im Ordner mit den CSV Dateien: `python3 marktmodell.py --ezmax 2022 --huber`).
- `skripte/rechne.py`: Rechenskript des Scouts (Score, Preisabzug, Restwert), Stand 11.11.2026.

Alle Daten liegen im Zweig `daten`.
