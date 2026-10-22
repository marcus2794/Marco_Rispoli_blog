#!/usr/bin/env python3
"""Scarica le statistiche IRPEF su base comunale del Dipartimento delle Finanze per gli anni
non ancora presenti in raw/irpef_comuni.csv, e aggiorna l'indice dei prezzi FOI.

Se il sito non risponde o un anno non è ancora pubblicato, i dati esistenti restano invariati.
Uso:  python3 tools/redditi/aggiorna_redditi.py [--tutti]
"""
import csv, io, json, os, re, sys, zipfile, urllib.request, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
URL = ("https://www1.finanze.gov.it/finanze/analisi_stat/public/v_4_0_0/contenuti/"
       "Redditi_e_principali_variabili_IRPEF_su_base_comunale_CSV_{y}.zip")
FOI_URL = "https://www.rivaluta.it/download/inflazione/dati-medi-anno-foi-senza-tabacchi.csv"
UA = {"User-Agent": "Mozilla/5.0 (dashboard I redditi del territorio piombinese)"}
TOSP = {"AR", "FI", "GR", "LI", "LU", "MS", "PI", "PO", "PT", "SI"}

KEYS = [("contrib", r"^Numero contribuenti"), ("fab", r"^Reddito da fabbricati"),
        ("dippen", r"^Reddito da lavoro dipendente e pensione"), ("dip", r"^Reddito da lavoro\s+dipendente"),
        ("pen", r"^Reddito da pensione"), ("aut", r"lavoro\s+autonomo"),
        ("ord", r"(imprenditore|spettanza).*ordinaria"), ("sem", r"(imprenditore|spettanza).*semplificata"),
        ("par", r"^Reddito da partecipazione"), ("imp", r"^Reddito imponibile\s*-"), ("net", r"^Imposta netta"),
        ("bon", r"^(Bonus|Trattamento) spettante"), ("radd", r"^Reddito imponibile addizionale"),
        ("reg", r"^Addizionale regionale"), ("com", r"^Addizionale comunale"),
        ("rc_le0", r"^Reddito complessivo minore"), ("rc_0_10", r"da 0 a 10000"), ("rc_10_15", r"da 10000 a 15000"),
        ("rc_15_26", r"da 15000 a 26000"), ("rc_26_55", r"da 26000 a 55000"), ("rc_55_75", r"da 55000 a 75000"),
        ("rc_75_120", r"da 75000 a 120000"), ("rc_120", r"oltre 120000"), ("rc", r"^Reddito complessivo\s*-")]
FIELDS = [k for k, _ in KEYS[1:]]
COLS = ["contrib"] + [f"{f}_{k}" for f in FIELDS for k in ("f", "a")]


def scarica(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def testo(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("windows-1252")


def normalizza(anno, txt, peers):
    """Dal CSV del Ministero alle colonne standard; tiene i comuni toscani e quelli dei gruppi di confronto,
    più i totali di Italia, Toscana e provincia di Livorno."""
    righe = [l.replace('"', "") for l in txt.splitlines() if l.strip()]
    H = [h.strip() for h in righe[0].split(";")]
    mp, autx = {}, []
    for i, h in enumerate(H):
        if re.match(r"^Codice Istat( Comune)?$", h): mp["codice"] = i
        if h == "Sigla Provincia": mp["sigla"] = i
        kind = "f" if h.endswith("Frequenza") else "a" if "Ammontare" in h else None
        for k, rx in KEYS:
            if re.search(rx, h):
                if k == "contrib":
                    mp["contrib"] = i
                elif kind:
                    key = f"{k}_{kind}"
                    if key not in mp: mp[key] = i
                    elif k == "aut": autx.append((key, i))
                break
    if "codice" not in mp or "contrib" not in mp:
        raise ValueError(f"{anno}: intestazione non riconosciuta")
    out, AG = [], {a: {} for a in ("ITA", "TOS", "PLI")}
    for l in righe[1:]:
        c = l.split(";")
        cod = (c[mp["codice"]] if mp["codice"] < len(c) else "").strip()
        if not cod.isdigit():
            continue
        cod = cod.zfill(6); sg = c[mp["sigla"]].strip()
        v = {"contrib": float(c[mp["contrib"]] or 0)}
        for col in COLS[1:]:
            i = mp.get(col)
            s = c[i].strip() if i is not None and i < len(c) else ""
            v[col] = float(s) if s not in ("",) else None
        for key, i in autx:
            v[key] = (v[key] or 0) + float(c[i] or 0)
        for ag, ok in (("ITA", True), ("TOS", sg in TOSP), ("PLI", sg == "LI")):
            if ok:
                for k in COLS:
                    if v[k] is not None: AG[ag][k] = AG[ag].get(k, 0) + v[k]
        if cod in peers or sg in TOSP:
            out.append([anno, cod, sg] + ["" if v[k] is None else f"{v[k]:.0f}" for k in COLS])
    for ag in ("ITA", "TOS", "PLI"):
        out.append([anno, ag, ""] + ["" if k not in AG[ag] else f"{AG[ag][k]:.0f}" for k in COLS])
    return out


def aggiorna_foi():
    try:
        t = testo(scarica(FOI_URL)).lstrip("﻿")
        righe = [l.split(";") for l in t.splitlines() if re.match(r"^\d{4};", l)]
        if len(righe) < 20:
            return
        with open(os.path.join(RAW, "foi.csv"), "w", encoding="utf-8") as f:
            f.write("anno;variazione_media_annua\n")
            for a, v in sorted(righe):
                if int(a) >= 2000: f.write(f"{a};{v}\n")
        print("  indice FOI aggiornato")
    except Exception as e:
        print("  indice FOI non aggiornato:", e)


def main():
    tutti = "--tutti" in sys.argv
    path = os.path.join(RAW, "irpef_comuni.csv")
    righe = list(csv.reader(open(path, encoding="utf-8")))
    head, dati = righe[0], righe[1:]
    presenti = {int(r[0]) for r in dati}
    gruppi = json.load(open(os.path.join(HERE, "..", "lente", "gruppi.json"), encoding="utf-8"))
    peers = set(gruppi["prov"]) | set(gruppi["cost"]) | set(gruppi["simi"])
    anni = range(2000, datetime.date.today().year) if tutti else [y for y in range(max(presenti) + 1, datetime.date.today().year)]
    nuovi = {}
    for y in anni:
        try:
            z = zipfile.ZipFile(io.BytesIO(scarica(URL.format(y=y))))
            nome = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
            nuovi[y] = normalizza(str(y), testo(z.read(nome)), peers)
            print(f"  {y}: {len(nuovi[y])} righe")
        except Exception as e:
            print(f"  {y}: non disponibile ({e})")
    if nuovi:
        dati = [r for r in dati if int(r[0]) not in nuovi] + [r for y in sorted(nuovi) for r in nuovi[y]]
        dati.sort(key=lambda r: int(r[0]))
        tmp = path + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(head); w.writerows(dati)
        os.replace(tmp, path)
    aggiorna_foi()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ATTENZIONE: redditi non aggiornati, restano i dati precedenti:", e)
