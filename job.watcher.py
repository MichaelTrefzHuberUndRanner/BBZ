import os
import sqlite3
from bs4 import BeautifulSoup
import re
import time

def parse_html_datei(dateipfad):
    with open(dateipfad, 'r', encoding='cp1252') as f:
        soup = BeautifulSoup(f, 'html.parser')

    daten = {}

    # Tabelle 1: Jobdaten
    tabelle1 = soup.find_all('table')[0]
    for tr in tabelle1.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) >= 2:
            feld = tds[0].get_text(strip=True)
            wert = tds[1].get_text(strip=True)
            if len(feld) > 30:
                continue  # Zeilen mit ungewöhnlich langen Feldnamen überspringen
            daten[feld] = wert

    # Tabelle 2: Gewichtsangaben (komplett)
    tabelle2 = soup.find_all('table')[1]
    for tr in tabelle2.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) >= 2:
            feld = tds[0].get_text(strip=True)
            wert = tds[1].get_text(strip=True)
            daten[feld] = wert

    # Tabelle 9: Job-Zuschnittdaten (Dimensionen und Anzahl)
    tabelle9 = soup.find_all('table')[8]
    for tr in tabelle9.find_all('tr')[1:]:  # erste Zeile Kopfzeile überspringen
        tds = tr.find_all('td')
        if len(tds) >= 4:
            dimension = tds[2].get_text(strip=True)
            anzahl = tds[3].get_text(strip=True)
            match = re.search(r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)', dimension)
            if match:
                norm_dimension = f"{match.group(1).replace('.0','')}x{match.group(2).replace('.0','')}"
                daten[norm_dimension] = anzahl

    return daten

def lese_kundennummern_aus_part_dat(pfad_zum_datenordner):
    kunden_map = {}  # ordnername -> liste von kunden
    for unterordner in os.listdir(pfad_zum_datenordner):
        unterordner_pfad = os.path.join(pfad_zum_datenordner, unterordner)
        if not os.path.isdir(unterordner_pfad):
            continue
        kundenliste = []
        for dateiname in os.listdir(unterordner_pfad):
            if dateiname.lower().startswith('part_') and dateiname.lower().endswith('.dat'):
                vollpfad = os.path.join(unterordner_pfad, dateiname)
                try:
                    with open(vollpfad, 'r', encoding='cp1252', errors='ignore') as f:
                        for zeile in f:
                            if 'PART_REMARK_2' in zeile:
                                match = re.search(r'PART_REMARK_2\s*=\s*(\w+)', zeile)
                                if match:
                                    rohwert = match.group(1)
                                    if len(rohwert) >= 10:
                                        formatierter_kunde = f"{rohwert[0:2]} {rohwert[2:6]} {rohwert[6]} {rohwert[7:]}"
                                        if formatierter_kunde not in kundenliste:
                                            kundenliste.append(formatierter_kunde)
                except Exception as e:
                    print(f"Fehler beim Lesen von {vollpfad}: {e}")
        if kundenliste:
            kunden_map[unterordner] = kundenliste
    return kunden_map

def speichere_kunden_db(kunden_map):
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS kunden')
    cursor.execute('CREATE TABLE kunden (ordner TEXT, kunde TEXT)')
    zaehler = 0
    for ordner, kunden in kunden_map.items():
        for kunde in kunden:
            cursor.execute('INSERT INTO kunden (ordner, kunde) VALUES (?, ?)', (ordner, kunde))
            zaehler += 1
    conn.commit()
    conn.close()
    print(f"{zaehler} eindeutige Kunden in der Tabelle \"kunden\" gespeichert.")

def verarbeite_jobs():
    ordner = './daten'

    alle_dateien = []
    for unterordner in os.listdir(ordner):
        dateipfad = os.path.join(ordner, unterordner, 'JOB.HTM')
        if os.path.isfile(dateipfad):
            alle_dateien.append(dateipfad)

    daten_aller_dateien = []
    alle_felder = set()

    for dateipfad in alle_dateien:
        daten = parse_html_datei(dateipfad)
        daten['datei'] = os.path.basename(dateipfad)
        daten['ordner'] = os.path.basename(os.path.dirname(dateipfad))
        daten_aller_dateien.append(daten)
        alle_felder.update(daten.keys())

    festgelegte_felder = [
        'Job Nummer', 'Material', 'Blechdicke', 'Bearbeitungs Zeit'
    ]
    feste_dimensionen = [
        '3000x1500', '2500x1250', '2590x1500', '2390x1500', '2190x1500',
        '1990x1500', '1790x1500'
    ]
    nachgestellte_felder = ['Nutzen', 'Datum', 'datei']

    kunden_map = lese_kundennummern_aus_part_dat(ordner)
    max_kunden_pro_job = max((len(kunden) for kunden in kunden_map.values()), default=0)
    kunden_spalten = [f'Kunde {i+1}' for i in range(max_kunden_pro_job)]

    spalten_reihenfolge = festgelegte_felder + feste_dimensionen + nachgestellte_felder + kunden_spalten

    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()

    spalten_def = ', '.join([f'"{sp}" TEXT' for sp in spalten_reihenfolge])
    cursor.execute('DROP TABLE IF EXISTS jobs')
    cursor.execute(f'CREATE TABLE jobs ({spalten_def})')

    placeholders = ', '.join(['?' for _ in spalten_reihenfolge])
    sql_insert = 'INSERT INTO jobs ({}) VALUES ({})'.format(
        ', '.join(f'"{sp}"' for sp in spalten_reihenfolge),
        placeholders
    )

    for daten in daten_aller_dateien:
        ordnername = daten.get('ordner')
        kunden = kunden_map.get(ordnername, [])
        kunden_padded = kunden + [None] * (max_kunden_pro_job - len(kunden))
        werte = [daten.get(sp, None) for sp in (festgelegte_felder + feste_dimensionen + nachgestellte_felder)] + kunden_padded
        cursor.execute(sql_insert, werte)

    conn.commit()
    conn.close()

    print(f'{len(alle_dateien)} JOB.HTM-Dateien verarbeitet.')
    speichere_kunden_db(kunden_map)

def main():
    while True:
        verarbeite_jobs()
        print("Warte 60 Sekunden auf neue Daten...")
        time.sleep(60)

if __name__ == '__main__':
    main()
