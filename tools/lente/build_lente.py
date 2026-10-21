#!/usr/bin/env python3
"""Costruisce la dashboard "Una lente sul territorio piombinese".

Dati: Atlante statistico dei comuni ISTAT (aster.istat.it) + caratteristiche dei comuni (SITUAS).
Uso:  python3 build_lente.py            # usa i dati in raw/ (aggiornati con aggiorna_dati.py)
"""
import csv, json, os, statistics, datetime, collections, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from indicatori import IND, TEMI  # noqa

RAW = os.path.join(HERE, "raw")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUTPUTS = [os.path.join(REPO, "lente", "index.html"), os.path.join(REPO, "docs", "lente", "index.html")]
FOCUS = "049012"          # Piombino
PROV_FOCUS = "049"        # Provincia di Livorno
TOSCANA = "09"
FASCIA = (20000, 50000)   # comuni "simili per abitanti"


def load():
    nomi = {r["codice"]: r["comune"] for r in csv.DictReader(open(os.path.join(RAW, "nomi_comuni.csv"), encoding="utf-8"))}
    car = {r["codice"]: r for r in csv.DictReader(open(os.path.join(RAW, "situas_caratteristiche.csv"), encoding="utf-8"))}
    rows = {r["codice"]: r for r in csv.DictReader(open(os.path.join(RAW, "aster_comuni.csv"), encoding="utf-8"))}
    return nomi, car, rows


def value(ind, r):
    rr = r
    if ind["zero"]:
        rr = dict(r)
        for k in ind["zero"]:
            if rr.get(k) in (None, ""):
                rr[k] = "0"
    try:
        n, d = ind["num"](rr), ind["den"](rr)
    except (TypeError, ZeroDivisionError):
        return None, None, None
    if n is None or d in (None, 0):
        return None, n, d
    return n / d * ind["k"], n, d


def aggregate(ind, rows):
    """Valore di un'area (provincia, regione, Italia) a partire dai suoi comuni."""
    if ind["kind"] == "size":
        vals = [value(ind, r)[0] for r in rows]
        return sum(v for v in vals if v is not None)
    if ind["kind"] == "median":
        vals = [value(ind, r)[0] for r in rows]
        vals = [v for v in vals if v is not None]
        return statistics.median(vals) if vals else None
    if ind["kind"] == "growth":
        # applico la formula alla somma delle componenti dei comuni che hanno il dato
        keep = [r for r in rows if value(ind, r)[0] is not None]
        if not keep:
            return None
        tot = collections.defaultdict(float)
        for r in keep:
            for k, v in r.items():
                if k != "codice" and v not in (None, ""):
                    tot[k] += float(v)
        return value(ind, {k: str(v) for k, v in tot.items()})[0]
    sn = sd = 0.0
    for r in rows:
        v, n, d = value(ind, r)
        if v is None:
            continue
        sn += n; sd += d
    return sn / sd * ind["k"] if sd else None


def main():
    nomi, car, rows = load()
    anni = json.load(open(os.path.join(RAW, "anni.json"), encoding="utf-8"))
    vivi = [c for c in nomi if c in rows and rows[c].get("pop_JAN")]
    # regione dei comuni nati dopo l'ultima classificazione: dalla provincia
    reg_prov = {}
    for c, r in car.items():
        reg_prov[c[:3]] = r["cod_reg"]
    def reg(c):
        return car[c]["cod_reg"] if c in car else reg_prov.get(c[:3], "")
    def lit(c):
        return car.get(c, {}).get("litoraneo") == "1"
    pop = {c: float(rows[c]["pop_JAN"]) for c in vivi}

    gruppi = {
        "prov": [c for c in vivi if c.startswith(PROV_FOCUS)],
        "cost": [c for c in vivi if lit(c) and FASCIA[0] <= pop[c] <= FASCIA[1]],
        "simi": [c for c in vivi if FASCIA[0] <= pop[c] <= FASCIA[1]],
    }
    units = sorted(set().union(*gruppi.values()) | {FOCUS})
    print({k: len(v) for k, v in gruppi.items()}, "comuni nella dashboard:", len(units))

    def vals_of(r):
        out = []
        for ind in IND:
            v = value(ind, r)[0]
            out.append(None if v is None else round(v, 4))
        return out

    aree = {
        "ITA": [rows[c] for c in vivi],
        "TOS": [rows[c] for c in vivi if reg(c) == TOSCANA],
        "PLI": [rows[c] for c in vivi if c.startswith(PROV_FOCUS)],
    }
    agg = {k: [None if (v := aggregate(ind, rs)) is None else round(v, 4) for ind in IND] for k, rs in aree.items()}

    # posizione di ogni comune tra tutti i comuni italiani (percentile), per ogni indicatore
    data = {
        "updated": datetime.date.today().isoformat(),
        "focus": FOCUS,
        "temi": [{"id": a, "n": b, "d": c} for a, b, c in TEMI],
        "ind": [{k: (ind[k].format(**anni) if k in ("nome", "anno") else ind[k]) for k in ("id", "tema", "nome", "unit", "dec", "pol", "anno", "fonte", "desc", "kind", "fmt")} for ind in IND],
        "anni": anni,
        "units": [{"id": c, "n": nomi[c], "p": c[:3], "r": reg(c), "lit": 1 if lit(c) else 0, "pop": int(pop[c])} for c in units],
        "groups": gruppi,
        "v": {c: vals_of(rows[c]) for c in units},
        "agg": agg,
        "fascia": FASCIA,
    }
    # controlli di qualità
    pio = dict(zip([i["id"] for i in IND], data["v"][FOCUS]))
    assert 30000 < pio["p_res"] < 35000, pio["p_res"]
    assert 15000 < pio["r_med"] < 40000, pio["r_med"]
    ita = dict(zip([i["id"] for i in IND], agg["ITA"]))
    assert 55e6 < ita["p_res"] < 62e6, ita["p_res"]
    return data


def write_html(data):
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    topo = json.load(open(os.path.join(HERE, "livorno.topo.json"), encoding="utf-8"))
    html = (tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
               .replace("/*__TOPO__*/null", json.dumps(topo, separators=(",", ":"))))
    for out in OUTPUTS:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w", encoding="utf-8").write(html)
        print("scritto", out, len(html) // 1024, "KB")


if __name__ == "__main__":
    d = main()
    ids = [i["id"] for i in d["ind"]]
    write_html(d)

