#!/usr/bin/env python3
"""
Dashboard turismo Toscana — scarica, pulisce e genera la pagina.

Fonte: Regione Toscana, open data (dati.toscana.it), dataset annuali
"Movimento dei clienti e struttura dell'offerta ricettiva" (arrivi, presenze,
italiani/stranieri per comune) e "Consistenza media" (esercizi, camere, letti).

Uso:
    python3 build_dashboard.py            # scarica gli anni nuovi/recenti e rigenera
    python3 build_dashboard.py --offline  # usa solo i CSV già in raw/

Nessuna dipendenza esterna: solo la libreria standard di Python 3.9+.
"""
import argparse, collections, csv, datetime, io, json, os, re, sys, unicodedata
import urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUTPUTS = [
    os.path.join(REPO, "turismo", "index.html"),          # sorgente: il render del sito la copia in docs/
    os.path.join(REPO, "docs", "turismo", "index.html"),  # pagina pubblicata da GitHub Pages
]
CKAN = "https://dati.toscana.it/api/3/action/package_search"
FIRST_YEAR = 2012

# Fusioni di comuni: codice vecchio -> codice attuale (serie storiche continue)
FUSIONI = {
    "046012": "046036", "046032": "046036",                       # Fabbriche di Vergemoli (2014)
    "046016": "046037", "046029": "046037",                       # Sillano Giuncugnano (2015)
    "047001": "047023", "047004": "047023",                       # Abetone Cutigliano (2017)
    "047015": "047024", "047019": "047024",                       # San Marcello Piteglio (2017)
    "048003": "048054", "048045": "048054",                       # Barberino Tavarnelle (2019)
    "048016": "048052", "048023": "048052",                       # Figline e Incisa Valdarno (2014)
    "048040": "048053", "048042": "048053",                       # Scarperia e San Piero (2014)
    "049015": "049021", "049016": "049021",                       # Rio (2018)
    "050007": "050040", "050017": "050040",                       # Casciana Terme Lari (2014)
    "050013": "050041", "050018": "050041",                       # Crespina Lorenzana (2014)
    "051009": "051040", "051029": "051040",                       # Castelfranco Piandiscò (2014)
    "051019": "051042", "051028": "051042",                       # Laterina Pergine Valdarno (2018)
    "051032": "051041", "051036": "051041",                       # Pratovecchio Stia (2014)
    "052014": "052037", "052029": "052037",                       # Montalcino (2017)
}


# ----------------------------------------------------------------------------- download
def fetch_raw(force_years=2):
    """Trova i dataset annuali sul portale e scarica i CSV mancanti.
    Riscarica sempre gli ultimi `force_years` anni (la Regione li aggiorna)."""
    os.makedirs(RAW, exist_ok=True)
    found = {}
    for q in ["movimento clienti offerta ricettiva", "movimento turistico per comune",
              "consistenza media comune", "struttura offerta ricettiva comune", "movimento clienti esercizi ricettivi"]:
        url = CKAN + "?" + urllib.parse.urlencode({"q": q, "rows": 200})
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mind-walker-dashboard"}), timeout=60) as r:
            res = json.load(r)["result"]["results"]
        select_resources(res, found)
    _download(found, force_years)


def select_resources(res, found):
    """Sceglie, tra i risultati CKAN, i CSV annuali regionali di movimento e consistenza."""
    for p in res:
        title = p.get("title", "")
        if not re.search(r"turist|clienti|ricettiv", title, re.I):
            continue
        if re.search(r"Firenze|Pisa|Siena|Cascina", title) and "Toscana" not in title:
            continue
        m = re.search(r"(20\d\d)\s*$", title.strip()) or re.search(r"Anno\s+(20\d\d)", title)
        if not m or "trimestre" in title or "bimestre" in title:
            continue
        year = int(m.group(1))
        for x in p.get("resources", []):
            if "csv" not in (x.get("format") or "").lower():
                continue
            label = ((x.get("name") or "") + " " + (x.get("url") or "")).lower()
            if "consisten" in label or "struttura-offerta" in label:
                kind = "con"
            elif "moviment" in label or "arrivi e presenze" in label:
                kind = "mov"
            else:
                continue
            found.setdefault((kind, year), x["url"])
    return found


def _download(found, force_years):
    if not found:
        raise SystemExit("Nessun dataset trovato sul portale: interrompo senza toccare la dashboard.")
    last = max(y for _, y in found)
    for (kind, year), url in sorted(found.items()):
        path = os.path.join(RAW, f"{kind}{year}.csv")
        if os.path.exists(path) and year <= last - force_years:
            continue
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mind-walker-dashboard"}), timeout=120) as r:
            b = r.read()
        try:
            t = b.decode("utf-8-sig")
        except UnicodeDecodeError:
            t = b.decode("cp1252")
        with open(path, "w", encoding="utf-8") as f:
            f.write(t)
        print(f"  scaricato {kind}{year}.csv ({len(t)//1024} KB)")



# ----------------------------------------------------------------------------- aggiornamento dalla banca dati regionale
BD_PAGE = "https://www.regione.toscana.it/statistiche/banca-dati-turismo"
UA = {"User-Agent": "Mozilla/5.0 (mind-walker-dashboard)"}


class Saiku:
    """Interroga la banca dati turismo pubblica della Regione (Pentaho/Saiku).
    L'indirizzo d'accesso pubblico viene letto ogni volta dalla pagina della Regione."""

    def __init__(self, page=BD_PAGE, pattern="TurismoSaiku", catalog="BD_TURISMO"):
        import http.cookiejar
        self.catalog = catalog
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        html = self._get(page).decode("utf-8", "ignore")
        m = re.search(r'href="(https?://web\.regione\.toscana\.it/pentaho/[^"]*' + pattern + r'[^"]*)"', html)
        if not m:
            raise RuntimeError("link alla banca dati non trovato nella pagina della Regione")
        link = m.group(1).replace("&amp;", "&").replace("http://", "https://")
        q = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
        self.user = (q.get("userid") or ["TURISMORO"])[0]
        self._get(link)  # apre la sessione, come farebbe un browser
        self.base = "https://web.regione.toscana.it/pentaho/plugin/saiku/api/" + self.user

    def _get(self, url, data=None, timeout=120):
        req = urllib.request.Request(url, data=data, headers=dict(UA, **({"Content-Type": "application/x-www-form-urlencoded"} if data else {})))
        with self.opener.open(req, timeout=timeout) as r:
            return r.read()

    def query(self, cube, mdx, tries=3):
        name = "q" + str(abs(hash(mdx)) % 10**8)
        self._get(f"{self.base}/query/{name}", urllib.parse.urlencode(
            {"connection": self.catalog, "catalog": self.catalog, "schema": self.catalog, "cube": cube}).encode())
        last = None
        for _ in range(tries):
            j = json.loads(self._get(f"{self.base}/query/{name}/result/flattened",
                                     urllib.parse.urlencode({"mdx": mdx}).encode(), timeout=600))
            if j.get("error"):
                last = j["error"]
                if "timed out" in last.lower():
                    continue
                raise RuntimeError(last)
            out = []
            for row in j["cellset"]:
                out.append([(None if c["properties"].get("raw") in (None, "") else float(c["properties"]["raw"]))
                            if c["type"] == "DATA_CELL" else c["value"] for c in row])
            return out
        raise RuntimeError(last or "nessuna risposta")


def fetch_saiku(last_year, recent=2):
    """Aggiorna raw_saiku/: tipi di struttura (tutti gli anni), provenienze e trimestri (ultimi anni)."""
    os.makedirs(SAIKU, exist_ok=True)
    sk = Saiku()
    # 1. posti letto ed esercizi per comune e tipo di struttura
    cs = sk.query("Consistenza", "SELECT NON EMPTY CrossJoin([Anno].[Anno].Members, {[Measures].[Letti (valori medi)],[Measures].[Esercizi (valori medi)]}) ON COLUMNS, "
                  "NON EMPTY CrossJoin([Territorio].[Codici comunali Istat].Members, [Tipo struttura.Tipologia].[Classificazione micro].Members) ON ROWS FROM [Consistenza]")
    yrs = [cs[0][i] for i in range(2, len(cs[0]), 2)]
    types = []
    for r in cs[2:]:
        if r[1] not in types: types.append(r[1])
    f = lambda v: "" if v is None else str(round(v * 10) / 10).rstrip("0").rstrip(".") if v != int(v) else str(int(v))
    lines = ["#years=" + ",".join(yrs), "#types=" + "|".join(types)]
    code = ""
    for r in cs[2:]:
        if r[0] and r[0] != "null": code = r[0]
        L = [f(r[2 + 2 * i]) for i in range(len(yrs))]
        E = [f(r[3 + 2 * i]) for i in range(len(yrs))]
        lines.append(f"{code};{types.index(r[1])};{','.join(L)};{','.join(E)}")
    if len(lines) > 1000:
        open(os.path.join(SAIKU, "consistenza_tipi.txt"), "w", encoding="utf-8").write("\n".join(lines))
        print(f"  banca dati: tipi di struttura {yrs[0]}-{yrs[-1]}")
    # anni da aggiornare per provenienze e trimestri
    years = list(range(max(2012, last_year - recent + 1), last_year + 1))
    # 2. provenienze per comune
    path = os.path.join(SAIKU, "provenienze_comuni.txt")
    old = open(path, encoding="utf-8").read().split("\n") if os.path.exists(path) else []
    data = collections.defaultdict(dict)   # (code, origin) -> {year: (a, p)}
    oy, oo = [], []
    if old:
        oy = [int(y) for y in old[0].split("=")[1].split(",")]; oo = old[1].split("=", 1)[1].split("|")
        n = len(oy)
        for l in old[2:]:
            if not l.strip(): continue
            c, k, v = l.split(";"); v = v.split(",")
            for i, y in enumerate(oy):
                data[(c, oo[int(k)])][y] = (v[i], v[n + i])
    for y in years:
        rows = sk.query("Movimento2", "SELECT {[Measures].[Arrivi],[Measures].[Presenze]} ON COLUMNS, NON EMPTY CrossJoin([Territorio].[Codici comunali Istat].Members,"
                        f"[Provenienza dei clienti].[Paese di provenienza].Members) ON ROWS FROM [Movimento2] WHERE [Anno].[{y}]")
        for key in data: data[key].pop(y, None)
        c = ""
        for r in rows[1:]:
            if r[0] and r[0] != "null": c = r[0]
            a, p = int(r[2] or 0), int(r[3] or 0)
            if a or p: data[(c, r[1])][y] = (str(a), str(p))
        print(f"  banca dati: provenienze {y}")
    allY = sorted(set(oy) | set(years)); allO = list(oo)
    for (_, o) in data:
        if o not in allO: allO.append(o)
    out = ["#years=" + ",".join(map(str, allY)), "#origins=" + "|".join(allO)]
    for (c, o), d in data.items():
        if not d: continue
        A = [d.get(y, ("0", "0"))[0] for y in allY]; P = [d.get(y, ("0", "0"))[1] for y in allY]
        out.append(f"{c};{allO.index(o)};{','.join(A + P)}")
    open(path, "w", encoding="utf-8").write("\n".join(out))
    # 3. presenze per trimestre
    path = os.path.join(SAIKU, "presenze_trimestri.csv")
    keep = []
    if os.path.exists(path):
        keep = [l for l in open(path, encoding="utf-8").read().split("\n")[1:] if l.strip() and int(l.split(";")[1]) not in years]
    new = []
    for y in years:
        rows = sk.query("Movimento2", f"SELECT NON EMPTY [Anno].[{y}].Children ON COLUMNS, NON EMPTY [Territorio].[Codici comunali Istat].Members ON ROWS FROM [Movimento2] WHERE [Measures].[Presenze]")
        h = rows[0]; idx = [h.index(q) if q in h else -1 for q in ["I Trimestre", "II Trimestre", "III Trimestre", "IV Trimestre"]]
        for r in rows[1:]:
            new.append(";".join([r[0], str(y)] + [str(int(r[k] or 0)) if k >= 0 else "0" for k in idx]))
        print(f"  banca dati: trimestri {y}")
    open(path, "w", encoding="utf-8").write("\n".join(["codice;anno;q1;q2;q3;q4"] + sorted(keep + new, key=lambda l: (l.split(";")[1], l.split(";")[0]))) + "\n")


def _ckan(q, rows=200):
    url = CKAN + "?" + urllib.parse.urlencode({"q": q, "rows": rows})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)["result"]["results"]


def _download_text(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        b = r.read()
    try:
        return b.decode("utf-8-sig")
    except UnicodeDecodeError:
        return b.decode("cp1252")


DEMO_PAGE = "https://www.regione.toscana.it/statistiche/banca-dati-demografia/bilancio-demografico"


def fetch_pop():
    """Residenti, saldo naturale e migratorio, famiglie per comune (banca dati Demografia, bilancio demografico)."""
    sk = Saiku(DEMO_PAGE, "BilancioSaiku", "BilancioP")
    years = [r[0] for r in sk.query("Bilancio_cuboP", "SELECT {[Measures].[Residenti al 31 dicembre]} ON COLUMNS, NON EMPTY [Anno.Totale].[Anno].Members ON ROWS FROM [Bilancio_cuboP]")[1:] if r[1]]
    rows = sk.query("Bilancio_cuboP", "SELECT NON EMPTY CrossJoin({" + ",".join(f"[Anno.Totale].[{y}]" for y in years) + "}, "
                    "{[Measures].[Residenti al 31 dicembre],[Measures].[Saldo naturale],[Measures].[Saldo migratorio],[Measures].[Numero famiglie]}) ON COLUMNS, "
                    "NON EMPTY [Ambiti Territoriali.PROVINCIA].[Codice Istat Comuni].Members ON ROWS FROM [Bilancio_cuboP]")
    ys = [rows[0][i] for i in range(1, len(rows[0]), 4)]
    out = ["codice;anno;residenti;saldo_naturale;saldo_migratorio;famiglie"]
    for r in rows[2:]:
        for k, y in enumerate(ys):
            v = r[1 + 4 * k: 5 + 4 * k]
            if any(x is not None for x in v):
                out.append(";".join([r[0], str(y)] + ["" if x is None else str(int(round(x))) for x in v]))
    if len(out) > 3000:
        open(os.path.join(SAIKU, "bilancio_demografico.csv"), "w", encoding="utf-8").write("\n".join(out) + "\n")
        print(f"  popolazione {ys[0]}-{ys[-1]}")


def fetch_asia():
    """Aggiunge ad asia_addetti_comuni.csv gli anni nuovi (unità locali e addetti per settore e comune)."""
    path = os.path.join(SAIKU, "asia_addetti_comuni.csv")
    lines = open(path, encoding="utf-8").read().split("\n")
    have = {int(l.split(";")[1]) for l in lines[1:] if l.strip()}
    found = {}
    for p in _ckan("Imprese unità locali addetti Asia"):
        m = re.search(r"(20\d\d)", p.get("title", ""))
        if not m or int(m.group(1)) <= max(have): continue
        for x in p.get("resources", []):
            lab = ((x.get("name") or "") + " " + (x.get("url") or "")).lower()
            if "csv" in (x.get("format") or "").lower() and ("unitalocali" in lab or "unita_locali" in lab or "unità locali" in lab) and "settore" in lab:
                found[int(m.group(1))] = x["url"]
    G = lambda c: "ind" if re.match(r"^[BCDE]", c) else {"F": "cos", "G": "com", "H": "tra", "I": "tur"}.get(c, "alt")
    keys = ["ind", "cos", "com", "tra", "tur", "alt"]
    for y, url in sorted(found.items()):
        t = _download_text(url).lstrip("﻿")
        head, body = read_csv_text(t)
        ic = col(head, "cod"); ia = next(i for i, h in enumerate(head) if "ateco" in h and "descr" not in h)
        iu = next(i for i, h in enumerate(head) if re.search(r"unit|numero_?ul", h)); ie = len(head) - 1
        acc = collections.defaultdict(lambda: dict.fromkeys(keys + ["ul_" + k for k in keys], 0.0))
        for r in body:
            code = r[ic].strip()
            if not code.isdigit(): continue
            g = G(r[ia].replace(" ", "").upper())
            o = acc[code.zfill(6)]
            o[g] += num(r[ie]); o["ul_" + g] += num(r[iu])
        if len(acc) < 250: continue
        for code, o in acc.items():
            lines.append(";".join([code, str(y)] + [str(round(o[k], 1)) for k in keys] + [str(int(o["ul_" + k])) for k in keys]))
        print(f"  addetti ASIA {y}")
    open(path, "w", encoding="utf-8").write("\n".join(l for l in lines if l.strip()) + "\n")


def read_csv_text(t):
    first = t.splitlines()[0]
    delim = max([",", ";", "\t"], key=first.count)
    r = list(csv.reader(io.StringIO(t), delimiter=delim))
    return [x.strip().lower() for x in r[0]], [x for x in r[1:] if any(c.strip() for c in x)]

# ----------------------------------------------------------------------------- parsing
def norm(s):
    s = unicodedata.normalize("NFKD", s.replace("’", "'").replace("â€™", "'")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def read_csv(path):
    t = open(path, encoding="utf-8").read().lstrip("﻿")
    first = t.splitlines()[0]
    delim = max([",", ";", "\t"], key=first.count)
    r = list(csv.reader(io.StringIO(t), delimiter=delim))
    head = [x.strip().lower() for x in r[0]]
    body = [x for x in r[1:] if any(c.strip() for c in x) and not x[0].strip().startswith("(")]
    return head, body


def num(s, thousand_dot=False):
    s = s.strip()
    if s in ("", "-"):
        return 0.0
    if thousand_dot:
        s = s.replace(".", "")
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    return float(s)


def col(head, *keys):
    for i, c in enumerate(head):
        if any(k in c for k in keys):
            return i
    return None


def load(geo_names):
    """Ritorna righe pulite: (anno, kind, codici_membri, valori, ambito, nome_grezzo)."""
    by_name = {norm(n): c for c, n in geo_names.items()}

    def members(raw_code, name):
        raw_code = raw_code.strip()
        if raw_code.isdigit() and norm(name) == norm(geo_names.get(str(int(raw_code)).zfill(6), name)):
            return [str(int(raw_code)).zfill(6)]
        # gruppo per segreto statistico: "A e B" oppure codici "a+b"
        parts = [p for p in re.split(r"\s+e\s+", name.strip()) if p]
        codes = [by_name.get(norm(p)) for p in parts]
        if len(parts) > 1 and all(codes):
            return codes
        if "+" in raw_code:
            return [p.zfill(6)[:6] if len(p) <= 6 else p[:6] for p in raw_code.split("+")]
        if raw_code.isdigit():
            return [str(int(raw_code)).zfill(6)]
        return []

    mov, con = [], []
    for fn in sorted(os.listdir(RAW)):
        m = re.match(r"(mov|con)(\d{4})\.csv$", fn)
        if not m:
            continue
        kind, y = m.group(1), int(m.group(2))
        head, rows = read_csv(os.path.join(RAW, fn))
        ic = col(head, "cod")
        inm = col(head, "denominazione")
        inm = inm if inm is not None else [i for i, c in enumerate(head) if c == "comune"][0]
        ia = col(head, "ambito")
        if kind == "mov":
            wide = "arrivi_italiani" in head
            if wide:
                idx = [head.index(k) for k in ["arrivi_italiani", "presenze_italiane", "arrivi_stranieri", "presenze_straniere"]]
            else:
                io_, iar, ipr = col(head, "proven", "italiano-str"), col(head, "arrivi"), col(head, "presenze")
            agg = collections.OrderedDict()
            for x in rows:
                name = x[inm].strip()
                if norm(name) == "toscana" or not x[ic].strip() or x[ic].strip() == "09":
                    continue
                k = (x[ic].strip(), name)
                v = agg.setdefault(k, [[0.0] * 4, re.sub(r"\s+", " ", x[ia]).strip() if ia is not None else None])
                if wide:
                    for j in range(4):
                        v[0][j] += num(x[idx[j]])
                else:
                    o = x[io_].strip().upper()
                    if o.startswith("TOT"):
                        continue
                    off = 0 if o.startswith("IT") else 2
                    td = (y == 2016)  # nel 2016 i numeri hanno il punto delle migliaia
                    v[0][off] += num(x[iar], td)
                    v[0][off + 1] += num(x[ipr], td)
            for (code, name), (vals, amb) in agg.items():
                mov.append((y, members(code, name), vals, amb, name))
        else:
            it, ie, icm, il = col(head, "tipo"), col(head, "eserciz", "strutture"), col(head, "camere"), col(head, "letti")
            td = 2014 <= y <= 2019  # camere/letti con il punto delle migliaia
            for x in rows:
                name = x[inm].strip()
                if not x[ic].strip() or norm(name) == "toscana":
                    continue
                t = x[it].lower()
                if "tot" in t:
                    continue
                k = 2 if "extra" in t else 0
                vals = [0.0] * 4
                vals[k], vals[k + 1] = num(x[ie], td), num(x[il], td)
                con.append((y, members(x[ic], name), vals, None, name))
    return mov, con


# ----------------------------------------------------------------------------- aggregazione

# ----------------------------------------------------------------------------- dati dalla banca dati regionale
SAIKU = os.path.join(HERE, "raw_saiku")
TIPI_BREVI = {
    "Alberghi 1 e 2 stelle": "Alberghi 1–2 stelle",
    "Alberghi 3 stelle ed RTA (compresi alberghi diffusi)": "Alberghi 3 stelle e residence",
    "Alberghi 4 e 5 stelle": "Alberghi 4–5 stelle",
    "Alloggi agrituristici": "Agriturismi",
    "Campeggi e villaggi turistici": "Campeggi e villaggi",
    "Case e appartamenti per vacanze": "Case e appartamenti vacanze",
    "Affittacamere": "Affittacamere",
    "Bed & Breakfast imp": "B&B imprenditoriali",
    "Bed & Breakfast non impr.": "B&B non imprenditoriali",
    "Alloggi privati": "Alloggi privati",
    "Residenze d'Epoca": "Residenze d'epoca",
    "Altre strutture extra-alberghiere": "Altre extra-alberghiere",
}
ORDINE_TIPI = list(TIPI_BREVI)


def load_tipi(valid):
    """Posti letto ed esercizi medi per comune e tipo di struttura (cubo Consistenza)."""
    path = os.path.join(SAIKU, "consistenza_tipi.txt")
    if not os.path.exists(path):
        return None
    lines = open(path, encoding="utf-8").read().split("\n")
    years = [int(y) for y in lines[0].split("=")[1].split(",")]
    types = lines[1].split("=")[1].split("|")
    out = collections.defaultdict(lambda: [[0.0] * len(years) for _ in ORDINE_TIPI])
    ese = collections.defaultdict(lambda: [[0.0] * len(years) for _ in ORDINE_TIPI])
    for l in lines[2:]:
        if not l.strip():
            continue
        code, ti, le, es = l.split(";")
        code = FUSIONI.get(code, code)
        if code not in valid:
            continue
        k = ORDINE_TIPI.index(types[int(ti)])
        for i, v in enumerate(le.split(",")):
            if v: out[code][k][i] += float(v)
        for i, v in enumerate(es.split(",")):
            if v: ese[code][k][i] += float(v)
    rl = lambda a: [int(round(x)) for x in a]
    re_ = lambda a: [round(x, 1) for x in a]
    return {"years": years, "names": [TIPI_BREVI[t] for t in ORDINE_TIPI],
            "hotel": [i for i, t in enumerate(ORDINE_TIPI) if t.startswith("Alberghi")],
            # solo i tipi presenti nel comune: {codice: {indice_tipo: [valori per anno]}}
            "l": {c: {k: rl(a) for k, a in enumerate(v) if any(a)} for c, v in out.items()},
            "e": {c: {k: re_(a) for k, a in enumerate(v) if any(a)} for c, v in ese.items()}}


def load_demo(valid):
    """Residenti, saldi e famiglie per comune e anno (banca dati Demografia della Regione)."""
    path = os.path.join(SAIKU, "bilancio_demografico.csv")
    if not os.path.exists(path):
        return None
    rows = list(csv.DictReader(open(path, encoding="utf-8"), delimiter=";"))
    years = sorted({int(r["anno"]) for r in rows})
    acc = collections.defaultdict(lambda: [[0, 0, 0, 0] for _ in years])
    for r in rows:
        c = FUSIONI.get(r["codice"].zfill(6), r["codice"].zfill(6))
        if c not in valid: continue
        i = years.index(int(r["anno"]))
        for k, key in enumerate(["residenti", "saldo_naturale", "saldo_migratorio", "famiglie"]):
            acc[c][i][k] += int(r[key] or 0)
    eta = {}
    pe = os.path.join(SAIKU, "indicatori_eta_2024.csv")
    if os.path.exists(pe):
        for r in csv.DictReader(open(pe, encoding="utf-8"), delimiter=";"):
            c = (r.get("Codice Istat Comuni") or "").strip().zfill(6)
            if c in valid:
                f = lambda k: float((r.get(k) or "0").replace(",", ".") or 0)
                eta[c] = [round(f("Eta Media"), 1), round(f("Indice Vecchiaia")), round(f("Indice Dipendenza Anziani"), 1)]
    return {"years": years, "v": dict(acc), "eta": eta, "etaYear": 2024}


def load_pop(valid, years):
    """Popolazione residente per comune, allineata agli anni del turismo."""
    demo = os.path.join(SAIKU, "bilancio_demografico.csv")
    if os.path.exists(demo):
        rows = list(csv.DictReader(open(demo, encoding="utf-8"), delimiter=";"))
        py = sorted({int(r["anno"]) for r in rows})
        acc = collections.defaultdict(lambda: [0] * len(py))
        for r in rows:
            c = FUSIONI.get(r["codice"].zfill(6), r["codice"].zfill(6))
            if r["residenti"]: acc[c][py.index(int(r["anno"]))] += int(r["residenti"])
    else:
        path = os.path.join(SAIKU, "popolazione_comuni.csv")
        if not os.path.exists(path):
            return None
        rows = list(csv.reader(open(path, encoding="utf-8"), delimiter=";"))
        py = [int(y) for y in rows[0][1:]]
        acc = collections.defaultdict(lambda: [0] * len(py))
        for r in rows[1:]:
            if not r or not r[0]:
                continue
            c = FUSIONI.get(r[0], r[0])
            for i, v in enumerate(r[1:]):
                if v: acc[c][i] += int(v)
    out = {}
    for c in valid:
        v = acc.get(c)
        if not v:
            continue
        series = []
        for y in years:
            if y in py and v[py.index(y)]:
                series.append(v[py.index(y)])
            else:  # anno mancante: valore più vicino disponibile
                cand = [(abs(y - yy), v[i]) for i, yy in enumerate(py) if v[i]]
                series.append(min(cand)[1] if cand else None)
        out[c] = series
    return {"years": years, "lastReal": max(y for i, y in enumerate(py) if any(v[i] for v in acc.values())), "v": out}



ITALIA = {"Abruzzo", "Basilicata", "Bolzano-Bozen", "Calabria", "Campania", "Emilia-Romagna", "Friuli-V. Giulia",
          "Lazio", "Liguria", "Lombardia", "Marche", "Molise", "Piemonte", "Puglia", "Regione italiana non indicata",
          "Sardegna", "Sicilia", "Toscana", "Trento", "Umbria", "Valle d'Aosta", "Veneto"}
UE = {"Austria", "Belgio", "Bulgaria", "Cipro", "Croazia", "Danimarca", "Estonia", "Finlandia", "Francia", "Germania",
      "Grecia", "Irlanda", "Lettonia", "Lituania", "Lussemburgo", "Malta", "Paesi Bassi", "Polonia", "Portogallo",
      "Repubblica Ceca", "Romania", "Slovacchia", "Slovenia", "Spagna", "Svezia", "Ungheria"}
EUROPA_EXTRA = {"Altri Paesi Europei", "Bielorussia", "Islanda", "Liechtenstein", "Norvegia", "Regno Unito",
                "Repubblica di Moldova", "Russia", "Svizzera", "Svizzera (incluso Liechtenstein)", "Turchia", "Ucraina",
                "Albania", "Bosnia-Erzegovina", "Iugoslavia", "Macedonia", "Paese europeo non indicato"}
NOMI_PROV = {"Bolzano-Bozen": "Prov. Bolzano", "Trento": "Prov. Trento", "Friuli-V. Giulia": "Friuli-Venezia Giulia",
             "Regione italiana non indicata": "Italia, regione non indicata", "Svizzera": "Svizzera",
             "Liechtenstein": "Svizzera", "Svizzera (incluso Liechtenstein)": "Svizzera",
             "Cina (incluso Hong Kong)": "Cina", "Stati Uniti d'America": "Stati Uniti", "Iugoslavia": "Ex Jugoslavia"}


def area_of(n):
    if n in ITALIA: return "Italia"
    if n in UE: return "Unione europea"
    if n in EUROPA_EXTRA: return "Europa extra UE"
    if n.startswith("Non specificato") or n == "Paesi e territori non indicati": return "Non specificato"
    return "Resto del mondo"


def load_provenienze(valid):
    """Arrivi e presenze per comune e paese/regione di provenienza (cubo Movimento2)."""
    path = os.path.join(SAIKU, "provenienze_comuni.txt")
    if not os.path.exists(path):
        return None
    lines = open(path, encoding="utf-8").read().split("\n")
    years = [int(y) for y in lines[0].split("=")[1].split(",")]
    raw_o = lines[1].split("=", 1)[1].split("|")
    n = len(years)
    names, idx = [], {}
    def oid(raw):
        nm = NOMI_PROV.get(raw, raw)
        if nm not in idx:
            idx[nm] = len(names); names.append(nm)
        return idx[nm]
    data = collections.defaultdict(dict)
    for l in lines[2:]:
        if not l.strip():
            continue
        code, k, vals = l.split(";")
        code = FUSIONI.get(code, code)
        if code not in valid:
            continue
        o = oid(raw_o[int(k)])
        v = [int(float(x)) for x in vals.split(",")]
        cur = data[code].setdefault(o, [0] * (2 * n))
        for i in range(2 * n):
            cur[i] += v[i]
    return {"years": years, "names": names, "area": [area_of(next(r for r in raw_o if NOMI_PROV.get(r, r) == nm)) for nm in names],
            "d": {c: {str(k): v for k, v in o.items() if any(v)} for c, o in data.items()}}


SETTORI = ["Industria", "Costruzioni", "Commercio", "Trasporti", "Alloggio e ristorazione", "Altri servizi"]


def load_asia(valid):
    """Addetti delle unità locali per comune e settore (ISTAT ASIA, open data Regione Toscana)."""
    path = os.path.join(SAIKU, "asia_addetti_comuni.csv")
    if not os.path.exists(path):
        return None
    rows = list(csv.DictReader(open(path, encoding="utf-8"), delimiter=";"))
    years = sorted({int(r["anno"]) for r in rows})
    keys = ["ind", "cos", "com", "tra", "tur", "alt"]
    acc = collections.defaultdict(lambda: [[0.0] * (2 * len(keys)) for _ in years])
    for r in rows:
        c = FUSIONI.get(r["codice"], r["codice"])
        if c not in valid:
            continue
        i = years.index(int(r["anno"]))
        for k, key in enumerate(keys):
            acc[c][i][k] += float(r[key] or 0)
            acc[c][i][len(keys) + k] += float(r.get("ul_" + key) or 0)
    return {"years": years, "settori": SETTORI,
            "v": {c: [[round(x) for x in row] for row in v] for c, v in acc.items()}}


def load_trim(valid):
    """Presenze per comune e trimestre (cubo Movimento2)."""
    path = os.path.join(SAIKU, "presenze_trimestri.csv")
    if not os.path.exists(path):
        return None
    rows = list(csv.reader(open(path, encoding="utf-8"), delimiter=";"))
    years = sorted({int(r[1]) for r in rows[1:]})
    acc = collections.defaultdict(lambda: [[0] * 4 for _ in years])
    for r in rows[1:]:
        c = FUSIONI.get(r[0], r[0])
        if c not in valid:
            continue
        i = years.index(int(r[1]))
        for q in range(4):
            acc[c][i][q] += int(float(r[2 + q] or 0))
    return {"years": years, "v": dict(acc)}

def build_data(geo):
    geo_names = {f["c"]: f["n"] for f in geo}
    geo_prov = {f["c"]: f["p"] for f in geo}
    mov_rows, con_rows = load(geo_names)
    years = sorted({r[0] for r in mov_rows})
    yi = {y: i for i, y in enumerate(years)}
    cur = lambda c: FUSIONI.get(c, c)

    # ambito di ogni comune (dall'anno più recente che lo riporta)
    amb = {}
    for y, mem, _, a, _ in sorted(mov_rows, key=lambda r: r[0]):
        if a:
            a = a.replace("Val di nievole", "Valdinievole").replace("Montagna pistoiese", "Montagna Pistoiese")
            for c in mem:
                if len(mem) == 1 or cur(c) not in amb:
                    amb[cur(c)] = a
    amb_fix = {a.lower(): a for a in amb.values()}
    amb = {c: amb_fix[a.lower()] for c, a in amb.items()}

    def series(rows, decimals):
        comune = collections.defaultdict(lambda: [None] * len(years))
        hidden = collections.defaultdict(set)           # anni in cui il comune è dentro un gruppo
        reg = [[0.0] * 4 for _ in years]
        prov = collections.defaultdict(lambda: [[0.0] * 4 for _ in years])
        ambt = collections.defaultdict(lambda: [[0.0] * 4 for _ in years])
        for y, mem, vals, _, name in rows:
            if y not in yi:
                continue
            i = yi[y]
            mem = [cur(c) for c in mem]
            for j in range(4):
                reg[i][j] += vals[j]
            if mem:
                p = geo_prov.get(mem[0]); a = amb.get(mem[0])
                if p:
                    for j in range(4): prov[p][i][j] += vals[j]
                if a:
                    for j in range(4): ambt[a][i][j] += vals[j]
            if len(set(mem)) == 1:
                c = mem[0]
                if comune[c][i] is None:
                    comune[c][i] = [0.0] * 4
                for j in range(4):
                    comune[c][i][j] += vals[j]
            else:
                for c in mem:
                    hidden[c].add(i)
        for c, idx in hidden.items():
            for i in idx:
                comune[c][i] = None
        rnd = lambda v: None if v is None else [round(a, decimals) if decimals else int(round(a)) for a in v]
        return ({c: [rnd(v) for v in s] for c, s in comune.items() if c in geo_names},
                [rnd(v) for v in reg], {k: [rnd(v) for v in s] for k, s in prov.items()},
                {k: [rnd(v) for v in s] for k, s in ambt.items()})

    m_com, m_reg, m_prov, m_amb = series(mov_rows, 0)
    c_com, c_reg, c_prov, c_amb = series(con_rows, 0)
    units = [{"id": c, "n": geo_names[c], "p": geo_prov[c], "a": amb.get(c, "")} for c in sorted(geo_names, key=lambda c: geo_names[c])]
    return {
        "updated": datetime.date.today().isoformat(),
        "years": years,
        "units": units,
        "mov": m_com, "con": c_com,
        "agg": {"TOS": {"mov": m_reg, "con": c_reg},
                **{"P:" + k: {"mov": m_prov[k], "con": c_prov.get(k)} for k in m_prov},
                **{"A:" + k: {"mov": m_amb[k], "con": c_amb.get(k)} for k in m_amb}},
    }


def load_piombino():
    """Dettaglio per provenienza (solo Piombino), da piombino_provenienze.csv se presente.
    Il CSV viene da un'estrazione della banca dati turismo regionale (vedi piombino/)."""
    path = os.path.join(HERE, "piombino_provenienze.csv")
    if not os.path.exists(path):
        return None
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    years = sorted({int(r["anno"]) for r in rows})
    by = collections.OrderedDict()
    for r in rows:
        k = r["provenienza"]
        o = by.setdefault(k, {"n": k, "g": r["gruppo"], "area": r["area"], "a": [0] * len(years), "p": [0] * len(years)})
        i = years.index(int(r["anno"]))
        o["a"][i] += int(r["arrivi"]); o["p"][i] += int(r["presenze"])
    origins = [o for o in by.values() if sum(o["p"]) > 0]
    return {"years": years, "o": origins}


PROV_NOMI = {"AR": "Arezzo", "FI": "Firenze", "GR": "Grosseto", "LI": "Livorno", "LU": "Lucca", "MS": "Massa-Carrara",
             "PI": "Pisa", "PO": "Prato", "PT": "Pistoia", "SI": "Siena"}


def export_tidy(data, folder):
    """Scrive i dati in tabelle "lunghe" e pulite (CSV), comode per R, Excel o DuckDB."""
    os.makedirs(folder, exist_ok=True)
    def write(name, head, rows):
        with open(os.path.join(folder, name), "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f); w.writerow(head); w.writerows(rows)
    write("comuni.csv", ["codice", "comune", "provincia", "ambito"],
          [[u["id"], u["n"], PROV_NOMI.get(u["p"], u["p"]), u["a"]] for u in data["units"]])
    ys = data["years"]
    write("movimenti.csv", ["anno", "codice", "arrivi_italiani", "presenze_italiani", "arrivi_stranieri", "presenze_stranieri"],
          [[y, c, *v] for c, s in sorted(data["mov"].items()) for y, v in zip(ys, s) if v])
    rows = []
    for c, s in sorted(data["con"].items()):
        for y, v in zip(ys, s):
            if v: rows.append([y, c, v[0], v[1], v[2], v[3]])
    write("posti_letto.csv", ["anno", "codice", "esercizi_alberghieri", "letti_alberghieri", "esercizi_extralberghieri", "letti_extralberghieri"], rows)
    t = data.get("tipi")
    if t:
        rows = []
        for c in sorted(t["l"]):
            for k, ser in t["l"][c].items():
                es = t["e"].get(c, {}).get(k, [None] * len(ser))
                for y, l, e in zip(t["years"], ser, es):
                    if l or e: rows.append([y, c, t["names"][k], e, l])
        write("strutture_per_tipo.csv", ["anno", "codice", "tipo", "esercizi", "posti_letto"], rows)
    d = data.get("demo")
    if d:
        write("popolazione.csv", ["anno", "codice", "residenti", "saldo_naturale", "saldo_migratorio"],
              [[y, c, v[0], v[1], v[2]] for c, s in sorted(d["v"].items()) for y, v in zip(d["years"], s) if v and v[0]])
    a = data.get("asia")
    if a:
        rows = []
        for c, s in sorted(a["v"].items()):
            for y, v in zip(a["years"], s):
                if not v: continue
                for k, nome in enumerate(SETTORI):
                    rows.append([y, c, nome, round(v[k], 1), int(round(v[6 + k]))])
        write("imprese_addetti.csv", ["anno", "codice", "settore", "addetti", "unita_locali"], rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="non scaricare, usa raw/")
    args = ap.parse_args()
    problemi = []
    if not args.offline:
        print("Scarico gli open data da dati.toscana.it ...")
        fetch_raw()
        last = max(int(re.match(r"mov(\d{4})", f).group(1)) for f in os.listdir(RAW) if re.match(r"mov\d{4}\.csv$", f))
        for nome, fn in [("banca dati turismo", lambda: fetch_saiku(last)), ("popolazione", fetch_pop), ("addetti ASIA", fetch_asia)]:
            try:
                print(f"Aggiorno: {nome} ...")
                fn()
            except Exception as e:  # una fonte che non risponde non deve bloccare le altre
                problemi.append(f"{nome}: {e}")
                print(f"  ATTENZIONE, {nome} non aggiornata: {e}")
    topo = json.load(open(os.path.join(HERE, "toscana_comuni.topo.json"), encoding="utf-8"))
    geo = [g["properties"] for g in topo["objects"][next(iter(topo["objects"]))]["geometries"]]
    data = build_data(geo)
    data["pio"] = load_piombino()
    valid = set(u["id"] for u in data["units"])
    data["tipi"] = load_tipi(valid)
    data["pop"] = load_pop(valid, data["years"])
    data["asia"] = load_asia(valid)
    data["demo"] = load_demo(valid)
    data["trim"] = load_trim(valid)
    prov = load_provenienze(valid)
    data["provFile"] = "provenienze.json" if prov else None
    data["pio"] = None  # sostituito dalle provenienze di tutti i comuni
    # controlli di qualità: se qualcosa non torna, non pubblico
    last = data["agg"]["TOS"]["mov"][-1]
    assert last and last[0] + last[2] > 5_000_000, "Totale regionale anomalo nell'ultimo anno"
    assert len(data["mov"]) > 250, "Troppi pochi comuni"
    export_tidy(data, os.path.join(HERE, "dati_puliti"))
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    html = (tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
               .replace("/*__TOPO__*/null", json.dumps(topo, separators=(",", ":"))))
    for out in OUTPUTS:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        if prov:
            with open(os.path.join(os.path.dirname(out), "provenienze.json"), "w", encoding="utf-8") as f:
                json.dump(prov, f, ensure_ascii=False, separators=(",", ":"))
        print("scritto", os.path.relpath(out, REPO), f"({len(html)//1024} KB)")
    y0, y1 = data["years"][0], data["years"][-1]
    dot = lambda n: f"{n:,}".replace(",", ".")
    if problemi:
        print("Fonti non aggiornate (restano i dati precedenti): " + "; ".join(problemi))
    print(f"Anni {y0}-{y1}, {len(data['units'])} comuni. Totale Toscana {y1}: "
          f"{dot(last[0]+last[2])} arrivi, {dot(last[1]+last[3])} presenze")


if __name__ == "__main__":
    main()
