#!/usr/bin/env python3
"""Costruisce la dashboard "I redditi del territorio piombinese" (2000-oggi).

Fonte: Dipartimento delle Finanze, statistiche sulle dichiarazioni IRPEF su base comunale.
Deflatore: indice ISTAT dei prezzi al consumo per le famiglie di operai e impiegati (FOI) senza tabacchi.

Uso:  python3 tools/redditi/build_redditi.py
"""
import csv, json, os, sys, datetime, statistics, collections

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
LENTE = os.path.join(REPO, "tools", "lente")
OUTPUTS = [os.path.join(REPO, "redditi", "index.html"), os.path.join(REPO, "docs", "redditi", "index.html")]
FOCUS = "049012"
TOSP = {"AR", "FI", "GR", "LI", "LU", "MS", "PI", "PO", "PT", "SI"}

CLASSI = [("rc_le0", None, 0), ("rc_0_10", 0, 10000), ("rc_10_15", 10000, 15000), ("rc_15_26", 15000, 26000),
          ("rc_26_55", 26000, 55000), ("rc_55_75", 55000, 75000), ("rc_75_120", 75000, 120000), ("rc_120", 120000, None)]
SOGLIA_BASSA, SOGLIA_ALTA = 15000, 55000   # in euro dell'ultimo anno


def num(v):
    return None if v in ("", None) else float(v)


def load_foi(years):
    var = {int(r["anno"]): float(r["variazione_media_annua"]) for r in csv.DictReader(open(os.path.join(RAW, "foi.csv"), encoding="utf-8"), delimiter=";")}
    idx = {min(years): 100.0}
    for y in range(min(years) + 1, max(years) + 1):
        idx[y] = idx[y - 1] * (1 + var[y] / 100)
    last = max(years)
    return {y: idx[last] / idx[y] for y in years}   # moltiplica gli euro dell'anno y per avere euro dell'ultimo anno


# ---------- stime sulla distribuzione (dalle fasce di reddito) ----------
def fasce(r):
    out = []
    for k, a, b in CLASSI:
        out.append((a, b, num(r[k + "_f"]), num(r[k + "_a"])))
    return out


def fasce_complete(F):
    return all(n is not None for a, b, n, s in F[1:])


def pareto_sopra(F, target):
    """Reddito dei 'target' contribuenti più ricchi, con interpolazione di Pareto (Atkinson)."""
    Nab = Sab = 0.0
    for a, b, n, s in reversed(F):
        if a is None:
            break
        if Nab + n >= target and a > 0:
            Nk, Sk = Nab + n, Sab + s
            beta = (Sk / Nk) / a
            if beta <= 1:
                return None
            al = beta / (beta - 1)
            y = a * (target / Nk) ** (-1 / al)
            return target * beta * y
        Nab += n; Sab += s
    return None


def quota_sotto(F, soglia):
    """Quota di contribuenti con reddito complessivo inferiore alla soglia (densità uniforme nella fascia)."""
    N = sum(n or 0 for a, b, n, s in F)
    cum = 0.0
    for a, b, n, s in F:
        n = n or 0
        if a is None:
            cum += n; continue
        top = b if b is not None else float("inf")
        if soglia >= top:
            cum += n; continue
        if soglia <= a:
            break
        if b is None:   # fascia aperta: Pareto
            mean = (s / n) if n else a
            beta = mean / a
            al = beta / (beta - 1) if beta > 1 else 3
            cum += n * (1 - (soglia / a) ** (-al))
        else:
            cum += n * (soglia - a) / (b - a)
        break
    return cum / N if N else None


def quota_sopra(F, soglia):
    """Quota di contribuenti sopra la soglia (Pareto nelle fasce alte)."""
    N = sum(n or 0 for a, b, n, s in F)
    Nab = Sab = 0.0
    for a, b, n, s in reversed(F):
        if a is None:
            return None
        Nab += n; Sab += s
        if a <= soglia:
            beta = (Sab / Nab) / a if a > 0 else None
            if not beta or beta <= 1:
                return None
            al = beta / (beta - 1)
            return Nab * (soglia / a) ** (-al) / N
    return None


def completa_fasce(r):
    """Se una sola fascia è oscurata (segreto statistico) ma il totale è noto, la ricava per differenza."""
    F = fasce(r)
    miss = [i for i, (a, b, n, s) in enumerate(F) if i > 0 and n is None]
    rcf, rca = num(r.get("rc_f")), num(r.get("rc_a"))
    if len(miss) == 1 and rcf and rca:
        i = miss[0]
        n = rcf - sum(x[2] or 0 for j, x in enumerate(F) if j != i)
        s = rca - sum(x[3] or 0 for j, x in enumerate(F) if j != i)
        if n > 0 and s > 0:
            a, b, _, _ = F[i]
            F[i] = (a, b, n, s)
    return F


def disuguaglianza(r):
    F = completa_fasce(r)
    if not fasce_complete(F):
        return None
    N = sum(n or 0 for a, b, n, s in F); S = sum(s or 0 for a, b, n, s in F)
    if N < 2000 or S <= 0:
        return None
    out = {}
    for k, p in (("t10", .10), ("t1", .01), ("t01", .001)):
        v = pareto_sopra(F, p * N)
        out[k] = None if v is None else v / S
    # curva di Lorenz sui punti delle fasce -> Gini (stima per difetto) e quota del 50% più povero
    pts = [(0.0, 0.0)]; cn = cs = 0.0
    for a, b, n, s in F:
        if not n:
            continue
        cn += n; cs += s
        pts.append((cn / N, cs / S))
    area = sum((x2 - x1) * (y1 + y2) / 2 for (x1, y1), (x2, y2) in zip(pts, pts[1:]))
    out["gini"] = 1 - 2 * area
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if x1 <= .5 <= x2:
            out["b50"] = y1 + (y2 - y1) * (.5 - x1) / (x2 - x1)
            break
    if out.get("t01") is not None and N < 15000:   # troppo pochi contribuenti per lo 0,1%
        out["t01"] = None
    return out


# ---------- caricamento ----------
def main():
    rows = list(csv.DictReader(open(os.path.join(RAW, "irpef_comuni.csv"), encoding="utf-8")))
    nomi = {}
    for l in open(os.path.join(RAW, "nomi.csv"), encoding="utf-8").read().splitlines()[1:]:
        if ";" in l:
            c, n = l.split(";", 1)
            nomi[c] = n.strip()
    years = sorted({int(r["anno"]) for r in rows})
    Y = years[-1]
    defl = load_foi(years)

    # gruppi di confronto: gli stessi della dashboard "Piombino in numeri"
    lente = json.load(open(os.path.join(LENTE, "gruppi.json"), encoding="utf-8"))
    by = collections.defaultdict(dict)
    sig = {}
    for r in rows:
        by[r["codice"]][int(r["anno"])] = r
        if r["sigla"]:
            sig[r["codice"]] = r["sigla"]

    def serie(cod):
        """Per ogni anno: [c, rc, imp, net, reg, com, dip_f, dip_a, pen_f, pen_a, aut_a, impr_a, par_a, fab_a, low, high, t10, t1, t01, gini, b50, rcIncompleto]"""
        out = []
        for y in years:
            r = by[cod].get(y)
            if not r:
                out.append(None); continue
            F = completa_fasce(r)
            c = num(r["contrib"])
            rc = num(r["rc_a"])
            inc = 0
            if rc is None:
                if fasce_complete(F):
                    rc = sum(s or 0 for a, b, n, s in F)
                else:
                    inc = 1
            comp = [num(r[k]) for k in ("dip_f", "dip_a", "pen_f", "pen_a", "aut_a")]
            impr = (num(r["ord_a"]) or 0) + (num(r["sem_a"]) or 0)
            low = high = None
            if fasce_complete(F):
                low = quota_sotto(F, SOGLIA_BASSA / defl[y])
                high = quota_sopra(F, SOGLIA_ALTA / defl[y])
            d = disuguaglianza(r) or {}
            v = [c, rc, num(r["imp_a"]), num(r["net_a"]), num(r["reg_a"]), num(r["com_a"]), *comp, impr, num(r["par_a"]), num(r["fab_a"]),
                 low, high, d.get("t10"), d.get("t1"), d.get("t01"), d.get("gini"), d.get("b50"), inc]
            out.append([None if x is None else (round(x, 4) if isinstance(x, float) and abs(x) < 10 else round(x)) for x in v])
        return out

    keys = sorted(set(lente["prov"]) | set(lente["cost"]) | set(lente["simi"]) | {FOCUS})
    keys = [k for k in keys if k in by and Y in by[k]]
    data = {
        "updated": datetime.date.today().isoformat(),
        "focus": FOCUS, "years": years, "last": Y,
        "defl": [round(defl[y], 5) for y in years],
        "soglie": [SOGLIA_BASSA, SOGLIA_ALTA],
        "units": [{"id": k, "n": nomi.get(k, k).title() if nomi.get(k, "").isupper() else nomi.get(k, k), "p": sig.get(k, ""),
                   "lit": 1 if k in set(lente["cost"]) else 0} for k in keys],
        "groups": {g: [k for k in lente[g] if k in set(keys)] for g in ("prov", "cost", "simi")},
        "v": {k: serie(k) for k in keys},
        "agg": {a: serie(a) for a in ("PLI", "TOS", "ITA")},
    }
    # nomi propri dei comuni (dalla dashboard "lente", che li ha in forma corretta)
    for u in data["units"]:
        if u["id"] in lente["nomi"]:
            u["n"] = lente["nomi"][u["id"]]
    # controlli
    pio = data["v"][FOCUS][-1]
    assert 20000 < pio[0] < 30000, pio[0]
    assert 300e6 < pio[1] < 900e6, pio[1]
    return data


def write_html(data):
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    for out in OUTPUTS:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w", encoding="utf-8").write(html)
        print("scritto", os.path.relpath(out, REPO), len(html) // 1024, "KB")


if __name__ == "__main__":
    d = main()
    write_html(d)
