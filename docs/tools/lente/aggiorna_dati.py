#!/usr/bin/env python3
"""Scarica i dati dell'Atlante statistico dei comuni ISTAT (aster.istat.it) e la
classificazione dei comuni costieri (SITUAS) per la dashboard "Una lente sul territorio piombinese".

Per ogni fonte prende l'anno più recente disponibile (o gli ultimi tre anni, per i dati
che conviene mediare), quindi la dashboard si aggiorna da sola quando l'ISTAT pubblica
dati nuovi. Se una fonte non risponde, i dati già presenti in raw/ restano quelli di prima.

Uso:  python3 aggiorna_dati.py
"""
import csv, json, os, sys, time, datetime, urllib.request, collections

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
API = "https://aster.istat.it/api/core/nodes/3/datasets/{ds}/data"
SITUAS = "https://situas-servizi.istat.it/publish/reportspooljson?pfun=73&pdata={data}"
PIOMBINO = "049012"
UA = {"User-Agent": "Mozilla/5.0 (dashboard Una lente sul territorio piombinese)", "Content-Type": "application/json",
      "Accept": "application/json"}

GRUPPI_ATECO = {"B": "ind", "C": "ind", "D": "ind", "E": "ind", "F": "cos", "G": "com", "H": "tra", "I": "tur",
                "J": "kn", "K": "kn", "L": "kn", "M": "kn", "N": "kn", "P": "soc", "Q": "soc", "R": "soc", "S": "soc"}


def CV(dim, vals):
    return {"id": dim, "type": "CodeValues", "filterValues": vals}


def TR(a, b=None):
    return {"id": "TIME_PERIOD", "type": "TimeRange", "from": f"{a}-01-01", "to": f"{b or a}-12-31"}


def post(ds, filters, tries=3):
    body = json.dumps(filters).encode()
    for k in range(tries):
        try:
            req = urllib.request.Request(API.format(ds=ds), data=body, headers=UA, method="POST")
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))


def rows_of(j):
    """JSON-stat -> (dizionario delle dimensioni, valore)."""
    ids, size = j["id"], j["size"]
    cats = []
    for d in ids:
        idx = j["dimension"][d]["category"]["index"]
        cats.append(idx if isinstance(idx, list) else [k for k, _ in sorted(idx.items(), key=lambda e: e[1])])
    for k, v in (j.get("value") or {}).items():
        n = int(k); c = [None] * len(ids)
        for i in range(len(ids) - 1, -1, -1):
            c[i] = cats[i][n % size[i]]; n //= size[i]
        yield dict(zip(ids, c)), v


def anni_disponibili(ds, filtri):
    """Anni con dati per Piombino (serve a capire qual è l'ultimo anno pubblicato)."""
    j = post(ds, [CV("TERRITORIO", [PIOMBINO])] + filtri + [TR(1990, 2100)])
    return sorted({int(o["TIME_PERIOD"][:4]) for o, v in rows_of(j) if isinstance(v, (int, float))})


# nome, dataset, filtri, regola sugli anni, funzione che dà il nome della colonna
SPECS = [
    ("pop", "IT1,DF_22_289_COMUNISEX1,1.0", [CV("SEX", ["9"])], "last", lambda o: "pop_JAN"),
    ("carta", "IT1,DF_CARTA_IDENTITA,1.0", [], "last", lambda o: "carta_" + ("JAN" if o["DATA_TYPE_AGGR"] == "JAN" else "AREA")),
    ("carta0", "IT1,DF_CARTA_IDENTITA,1.0", [CV("DATA_TYPE_AGGR", ["JAN"])], 2002, lambda o: "carta0_JAN"),
    ("bil3", "IT1,22_315,1.0", [CV("SEX", ["9"]), CV("DATA_TYPE", ["LBIRTH", "DEATH", "INTNETMIGR_REGOF", "INTERTNMIG_REGOF", "DEC_CP"])],
     "last3", lambda o: "bil3_" + o["DATA_TYPE"]),
    ("bil1", "IT1,22_315,1.0", [CV("SEX", ["9"]), CV("DATA_TYPE", ["NUMPRHO_CP", "DEC_CP"])], "last", lambda o: "bil1_" + o["DATA_TYPE"]),
    ("stra", "IT1,29_7,1.0", [CV("SEX", ["9"]), CV("AGE", ["TOTAL"])], "last", lambda o: "stra_JAN"),
    ("irpef", "IT1,30_1008,1.0", [CV("DATA_TYPE", ["TAXABINCR", "TAXABINCF", "NTAXP", "PENSINCR", "SUBEMPTRINCR", "AGGINCF"])], "last",
     lambda o: "irpef_" + o["DATA_TYPE"] + ("_" + o["AMOUNT_CLASS"] if o["DATA_TYPE"] == "AGGINCF" else "")),
    ("irpef0", "IT1,30_1008,1.0", [CV("DATA_TYPE", ["TAXABINCR", "TAXABINCF"]), CV("AMOUNT_CLASS", ["TOTAL"])], "last-10", lambda o: "irpef0_" + o["DATA_TYPE"]),
    ("bank", "IT1,117_1035,1.0", [], "last", lambda o: "bank_" + o["DATA_TYPE"]),
    ("bank0", "IT1,117_1035,1.0", [CV("DATA_TYPE", ["BANK_BRN"])], "first", lambda o: "bank0_" + o["DATA_TYPE"]),
    ("ul", "IT1,183_285,1.0", [CV("PERS_EMPL_SIZE_CLASS", ["TOTAL"]), CV("ECON_ACTIVITY_NACE_2007", list(GRUPPI_ATECO))], "last", None),
    ("ul0", "IT1,183_285,1.0", [CV("PERS_EMPL_SIZE_CLASS", ["TOTAL"]), CV("ECON_ACTIVITY_NACE_2007", list(GRUPPI_ATECO))], "first", None),
    ("dips", "IT1,DF_DIPS_SIR_IND_TERR_DRT_OCC,1.0", [CV("SEX", ["T"]), CV("DATA_TYPE", ["AOIN_9EPEXPE_PE_SH_PCT", "AOIN_HTPEXPE_PE_SH_PCT", "AOIN_PEFXPE_PE_SH_PCT", "AOIN_TEDPEXPE_PEA_SH_PCT"])],
     "last", lambda o: "dips_" + o["DATA_TYPE"]),
    ("mfi", "IT1,DF_COMP_FRA_IND_MUNICIPAL,1.0", [CV("DATA_TYPE", ["COMP_FRAG_INDEX_DECILE", "EMPL_RATE_20_64", "LANDSLIDE_HAZARD_ZONES", "LAND_CONSUMPTION", "POP_25_64_UNDER_DIP_LOW_SEC_EDU", "PROTECTED_NAT_AREAS", "UNDIF_COLL_URBAN_WASTE"])],
     "last", lambda o: "mfi_" + o["DATA_TYPE"]),
    ("agr", "IT1,DF_DCAT_CENSAGRIC2020_SURF_ALL,1.0", [CV("DATA_TYPE", ["HO", "ARU"])], "last", lambda o: "agr_" + o["DATA_TYPE"]),
    ("agr_g", "IT1,DF_DCAT_CENSAGRIC2020_GAIN,1.0", [CV("GAINFUL_ACTIVITIES", ["ALL"])], "last", lambda o: "agr_GAIN"),
    ("agr_l", "IT1,DF_DCAT_CENSAGRIC2020_LABCAT_ALL,1.0", [CV("SEX", ["9"]), CV("LABOUR_FORCE_CATEG", ["THLF"]), CV("DATA_TYPE", ["NUMB_LA_SWD"])], "last", lambda o: "agr_SWD"),
    ("agritur", "IT1,101_1039,1.0", [CV("AGRIT_AUTHORIZATION", ["ALL"])], "last", lambda o: "agritur_ALL"),
    ("agritur0", "IT1,101_1039,1.0", [CV("AGRIT_AUTHORIZATION", ["ALL"])], "last-5", lambda o: "agritur0_ALL"),
    ("dop", "IT1,101_1077,1.0", [CV("DATA_TYPE", ["PROD_PDOPGI"])], "last", lambda o: "dop_" + o["DATA_TYPE"]),
    ("osp", "IT1,43_994,1.0", [CV("HOSPITAL_TYPE", ["TOT"]), CV("CLINICAL_SPECIALTY", ["99"]), CV("DATA_TYPE", ["19", "28"])], "last", lambda o: "osp_" + o["DATA_TYPE"]),
    ("mus", "IT1,DF_MUS1,1.0", [CV("TIPO_DATO", ["M024"])], "last", lambda o: "mus_M024"),
    ("mus_n", "IT1,DF_MUS,1.0", [CV("TIPO_DATO", ["M001"])], "last", lambda o: "mus_M001"),
    ("bib", "IT1,DF_BIBLIO1,1.0", [CV("TIPO_DATO", ["B001"])], "last", lambda o: "bib_B001"),
    ("bib_p", "IT1,DF_BIBLIO2,1.0", [CV("TIPO_DATO", ["B010"])], "last", lambda o: "bib_B010"),
    ("veh", "IT1,41_993,1.0", [CV("VEHICLE_TYPE", ["1", "13", "14", "15", "16", "19"])], "last", lambda o: "veh_" + o["VEHICLE_TYPE"]),
    ("inc3", "IT1,41_983,1.0", [], "last3", lambda o: "inc3_" + o["DATA_TYPE"] + "_" + o["RESULT"]),
    ("cap", "IT1,DF_TURISMO_CAP,1.0", [CV("DATA_TYPE", ["BEDS", "NUM_EST"]), CV("TYPE_ACCOMMODATION", ["ALL"]), CV("LOCALITY_TYPE", ["ALL"]),
                                       CV("URBANIZ_DEGREE", ["ALL"]), CV("COASTAL_AREA", ["ALL"]), CV("SIZE_BY_NUMBER_ROOMS", ["TOT"]), CV("ECON_ACTIVITY_NACE_2007", ["551_553"])], "last",
     lambda o: "cap_" + o["DATA_TYPE"]),
    ("acqua", "IT1,DF_DCCV_CONSACQUA_12_60,1.0", [], "last", lambda o: "acqua_" + o["DATA_TYPE"]),
]
# chiave dell'anno mostrato in pagina per ciascuna fonte
CHIAVE_ANNO = {"agr_g": "agr", "agr_l": "agr", "mus_n": "mus", "bib_p": "bib"}


def scegli_anni(rule, anni):
    if isinstance(rule, int):
        return [rule]
    if rule == "last":
        return [anni[-1]]
    if rule == "first":
        return [anni[0]]
    if rule == "last3":
        return anni[-3:]
    if rule.startswith("last-"):
        target = anni[-1] - int(rule[5:])
        return [max([a for a in anni if a <= target] or [anni[0]])]
    raise ValueError(rule)


def scarica():
    W = collections.defaultdict(dict)
    nomi = {}
    anni_usati = {}
    for nome, ds, filtri, rule, col in SPECS:
        # per le famiglie l'ultimo anno è quello in cui c'è il numero di famiglie
        yf = [CV("SEX", ["9"]), CV("DATA_TYPE", ["NUMPRHO_CP"])] if nome == "bil1" else filtri
        anni = anni_disponibili(ds, yf) if not isinstance(rule, int) else [rule]
        if not anni:
            raise RuntimeError(f"{nome}: nessun anno disponibile")
        scelti = scegli_anni(rule, anni)
        print(f"  {nome}: anni {scelti[0]}" + (f"–{scelti[-1]}" if len(scelti) > 1 else ""))
        j = post(ds, filtri + [TR(scelti[0], scelti[-1])])
        if nome == "pop":
            nomi = dict(j["dimension"]["TERRITORIO"]["category"]["label"])
        n = 0
        for o, v in rows_of(j):
            if not isinstance(v, (int, float)):
                continue
            c = o["TERRITORIO"]
            if nome in ("ul", "ul0"):
                p = "lu" if o["DATA_TYPE"] == "LU" else "add"
                g = GRUPPI_ATECO[o["ECON_ACTIVITY_NACE_2007"]]
                for k in (f"{nome}_{p}_tot", f"{nome}_{p}_{g}"):
                    W[c][k] = W[c].get(k, 0) + v
            else:
                k = col(o)
                W[c][k] = W[c].get(k, 0) + v
            n += 1
        if n < 1000 and nome not in ("osp",):
            raise RuntimeError(f"{nome}: troppi pochi dati ({n})")
        chiave = CHIAVE_ANNO.get(nome, nome)
        anni_usati[chiave] = str(scelti[0]) if len(scelti) == 1 else f"{scelti[0]}–{scelti[-1]}"
    # età: per non scaricare un cubo enorme, aggrego per gruppi di età in blocchi
    eta_anni = anni_disponibili("IT1,DF_22_289_COMUNIETA1,1.0", [CV("AGE", ["TOTAL"])])
    y = eta_anni[-1]
    ages = [f"Y{a}" for a in range(100)] + ["Y_GE100"]
    for i in range(0, len(ages), 20):
        j = post("IT1,DF_22_289_COMUNIETA1,1.0", [CV("AGE", ages[i:i + 20]), TR(y)])
        for o, v in rows_of(j):
            if not isinstance(v, (int, float)):
                continue
            a = 100 if o["AGE"] == "Y_GE100" else int(o["AGE"][1:])
            r = W[o["TERRITORIO"]]
            k = "eta_a014" if a < 15 else "eta_a1564" if a < 65 else "eta_a65"
            r[k] = r.get(k, 0) + v
            r["eta_agesum"] = r.get("eta_agesum", 0) + v * (a + 0.5)
    anni_usati["eta"] = str(y)
    print(f"  eta: anno {y}")
    return W, nomi, anni_usati


def scrivi(W, nomi, anni):
    cols = sorted({k for r in W.values() for k in r})
    tmp = os.path.join(RAW, "aster_comuni.csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["codice"] + cols)
        for c in sorted(W):
            w.writerow([c] + ["" if W[c].get(k) is None else round(W[c][k], 3) for k in cols])
    os.replace(tmp, os.path.join(RAW, "aster_comuni.csv"))
    with open(os.path.join(RAW, "nomi_comuni.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["codice", "comune"]); w.writerows(sorted(nomi.items()))
    json.dump(anni, open(os.path.join(RAW, "anni.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def aggiorna_situas():
    oggi = datetime.date.today().strftime("%d/%m/%Y")
    for data in (oggi, "31/05/2026"):
        try:
            req = urllib.request.Request(SITUAS.format(data=data), headers={"User-Agent": UA["User-Agent"], "Referer": "https://situas.istat.it/web/"})
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.loads(r.read().decode("utf-8"), strict=False)
            rows = j.get("resultset") or j.get("items") or []
            if len(rows) < 7000:
                continue
            with open(os.path.join(RAW, "situas_caratteristiche.csv"), "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["codice", "litoraneo", "isolano", "zona_alt", "degurba", "sigla", "cod_reg"])
                for x in rows:
                    w.writerow([x["PRO_COM_T"], x["COM_LIT"], x["COM_ISO"], x["ZONA_ALT"], x.get("DEGURBA_2021", ""), x["SIGLA_AUTOMOBILISTICA"], x["COD_REG"]])
            print(f"  SITUAS: {len(rows)} comuni")
            return
        except Exception as e:
            print(f"  SITUAS non disponibile ({data}): {e}")


def main():
    print("Atlante statistico dei comuni (ISTAT)...")
    W, nomi, anni = scarica()
    if len(W) < 7000 or PIOMBINO not in W:
        raise RuntimeError("dati incompleti, non sovrascrivo")
    scrivi(W, nomi, anni)
    print("Classificazione dei comuni costieri (SITUAS)...")
    aggiorna_situas()
    print("Fatto:", len(W), "comuni")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # una fonte che non risponde non deve bloccare il resto del sito
        print("ATTENZIONE: dati dell'Atlante non aggiornati, restano quelli precedenti:", e)
        sys.exit(0)
