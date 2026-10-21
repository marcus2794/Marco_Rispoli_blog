# -*- coding: utf-8 -*-
"""Definizione degli indicatori della dashboard "Una lente sul territorio piombinese".

Ogni indicatore è un rapporto num/den * k calcolato sui dati grezzi di un comune.
Per Toscana, Italia e provincia il valore è il rapporto delle somme (cioè il valore
dell'area nel suo insieme). Per gli indicatori già in percentuale forniti dall'ISTAT
(indice di fragilità, registri statistici) si usa la media ponderata con la popolazione.

pol: +1 = più alto è meglio, -1 = più alto è peggio, 0 = né meglio né peggio (solo descrittivo)
zero: True se l'assenza del dato per un comune significa zero (per es. nessun museo)
"""

TEMI = [
    ("pop", "Popolazione", "Quanti siamo, quanto invecchiamo, chi arriva e chi parte"),
    ("red", "Redditi e risparmio", "Quanto si guadagna, chi vive di pensione, banche e depositi"),
    ("lav", "Lavoro e imprese", "Quante imprese, quanti addetti, in quali settori"),
    ("agr", "Agricoltura", "Aziende agricole, terra coltivata, agriturismi e prodotti tipici"),
    ("cul", "Cultura e turismo", "Musei, biblioteche e posti letto turistici"),
    ("ser", "Salute e servizi", "Ospedali, istruzione e fragilità del territorio"),
    ("mob", "Mobilità e strade", "Automobili, inquinamento delle auto, incidenti"),
    ("amb", "Ambiente e territorio", "Acqua, rifiuti, suolo, frane e aree protette"),
]


def g(r, k):
    v = r.get(k)
    return None if v in (None, "") else float(v)


def s(r, *ks):
    vals = [g(r, k) for k in ks]
    if all(v is None for v in vals):
        return None
    return sum(v or 0 for v in vals)


POP = lambda r: g(r, "pop_JAN")
POP24 = lambda r: g(r, "carta_JAN")
POP22 = POP24
ADD23 = lambda r: g(r, "ul_add_tot")


def I(id, tema, nome, num, den, k=1, unit="", dec=1, pol=0, anno="", fonte="", desc="", zero=(), kind="ratio", fmt="num"):
    return dict(id=id, tema=tema, nome=nome, num=num, den=den, k=k, unit=unit, dec=dec, pol=pol,
                anno=anno, fonte=fonte, desc=desc, zero=zero, kind=kind, fmt=fmt)


IND = [
    # ---------------- popolazione
    I("p_res", "pop", "Residenti", POP, lambda r: 1, unit="", dec=0, anno="1/1/{pop}", fonte="ISTAT, popolazione residente",
      desc="Persone residenti al 1° gennaio.", kind="size"),
    I("p_var", "pop", "Variazione dei residenti dal {carta0}", lambda r: POP(r) - g(r, "carta0_JAN") if POP(r) and g(r, "carta0_JAN") else None,
      lambda r: g(r, "carta0_JAN"), k=100, unit="%", dec=1, anno="{carta0}–{pop}", fonte="ISTAT, popolazione residente",
      desc="Di quanto è cambiata la popolazione dal 2002 a oggi.", fmt="signed"),
    I("p_dens", "pop", "Abitanti per km²", POP, lambda r: g(r, "carta_AREA"), dec=0, anno="{pop}",
      fonte="ISTAT, popolazione e superficie", desc="Quanto è densamente abitato il territorio."),
    I("p_age", "pop", "Età media", lambda r: g(r, "eta_agesum"), lambda r: s(r, "eta_a014", "eta_a1564", "eta_a65"), unit=" anni", dec=1,
      anno="1/1/{eta}", fonte="ISTAT, popolazione per età", desc="Età media dei residenti."),
    I("p_vec", "pop", "Anziani ogni 100 ragazzi", lambda r: g(r, "eta_a65"), lambda r: g(r, "eta_a014"), k=100, dec=0, anno="1/1/{eta}",
      fonte="ISTAT, popolazione per età", desc="Indice di vecchiaia: residenti con 65 anni e più ogni 100 con meno di 15 anni."),
    I("p_65", "pop", "Quota di over 65", lambda r: g(r, "eta_a65"), lambda r: s(r, "eta_a014", "eta_a1564", "eta_a65"), k=100, unit="%", dec=1,
      anno="1/1/{eta}", fonte="ISTAT, popolazione per età", desc="Residenti con 65 anni e più sul totale."),
    I("p_nat", "pop", "Nati ogni 1.000 abitanti", lambda r: g(r, "bil3_LBIRTH"), lambda r: g(r, "bil3_DEC_CP"), k=1000, dec=1,
      pol=1, anno="media {bil3}", fonte="ISTAT, bilancio demografico", desc="Tasso di natalità, media di tre anni."),
    I("p_mor", "pop", "Morti ogni 1.000 abitanti", lambda r: g(r, "bil3_DEATH"), lambda r: g(r, "bil3_DEC_CP"), k=1000, dec=1,
      anno="media {bil3}", fonte="ISTAT, bilancio demografico", desc="Tasso di mortalità, media di tre anni (dipende molto dall'età della popolazione)."),
    I("p_mig", "pop", "Saldo migratorio ogni 1.000 abitanti", lambda r: s(r, "bil3_INTNETMIGR_REGOF", "bil3_INTERTNMIG_REGOF"),
      lambda r: g(r, "bil3_DEC_CP"), k=1000, dec=1, pol=1, anno="media {bil3}", fonte="ISTAT, bilancio demografico",
      desc="Iscritti meno cancellati (da altri comuni e dall'estero) ogni 1.000 abitanti: sopra zero arrivano più persone di quante partono.",
      fmt="signed"),
    I("p_str", "pop", "Stranieri ogni 100 residenti", lambda r: g(r, "stra_JAN"), lambda r: g(r, "carta_JAN"), k=100, dec=1,
      anno="1/1/{stra}", fonte="ISTAT, stranieri residenti", desc="Cittadini stranieri residenti ogni 100 abitanti.", zero=("stra_JAN",)),
    I("p_fam", "pop", "Persone per famiglia", lambda r: g(r, "bil1_DEC_CP"), lambda r: g(r, "bil1_NUMPRHO_CP"), dec=2,
      anno="{bil1}", fonte="ISTAT, bilancio demografico", desc="Residenti diviso numero di famiglie: famiglie sempre più piccole sono un segno di invecchiamento."),

    # ---------------- redditi
    I("r_med", "red", "Reddito imponibile medio", lambda r: g(r, "irpef_TAXABINCR"), lambda r: g(r, "irpef_TAXABINCF"),
      unit=" €", dec=0, pol=1, anno="redditi {irpef}", fonte="MEF, dichiarazioni IRPEF", desc="Reddito imponibile medio per contribuente."),
    I("r_pc", "red", "Reddito imponibile per abitante", lambda r: g(r, "irpef_TAXABINCR"), POP24, unit=" €", dec=0, pol=1,
      anno="redditi {irpef}", fonte="MEF, dichiarazioni IRPEF", desc="Reddito imponibile totale diviso tutti i residenti, bambini compresi."),
    I("r_var", "red", "Crescita del reddito medio dal {irpef0}",
      lambda r: g(r, "irpef_TAXABINCR") / g(r, "irpef_TAXABINCF") - g(r, "irpef0_TAXABINCR") / g(r, "irpef0_TAXABINCF")
      if g(r, "irpef_TAXABINCF") and g(r, "irpef0_TAXABINCF") else None,
      lambda r: g(r, "irpef0_TAXABINCR") / g(r, "irpef0_TAXABINCF") if g(r, "irpef0_TAXABINCF") else None,
      k=100, unit="%", dec=1, pol=1, anno="{irpef0}–{irpef}", fonte="MEF, dichiarazioni IRPEF",
      desc="Variazione del reddito imponibile medio in dieci anni, a prezzi correnti (senza togliere l'inflazione, che tra il 2013 e il 2023 è stata di quasi il 20%).",
      kind="growth", fmt="signed"),
    I("r_low", "red", "Contribuenti sotto i 10 mila euro", lambda r: s(r, "irpef_AGGINCF_E_UN0", "irpef_AGGINCF_E0-10000"),
      lambda r: g(r, "irpef_NTAXP"), k=100, unit="%", dec=1, pol=-1, anno="redditi {irpef}", fonte="MEF, dichiarazioni IRPEF",
      desc="Quota di contribuenti con un reddito complessivo fino a 10.000 euro l'anno."),
    I("r_pen", "red", "Quota del reddito da pensioni", lambda r: g(r, "irpef_PENSINCR"), lambda r: g(r, "irpef_TAXABINCR"),
      k=100, unit="%", dec=1, anno="redditi {irpef}", fonte="MEF, dichiarazioni IRPEF", desc="Redditi da pensione rispetto al reddito imponibile totale."),
    I("r_dip", "red", "Quota del reddito da lavoro dipendente", lambda r: g(r, "irpef_SUBEMPTRINCR"), lambda r: g(r, "irpef_TAXABINCR"),
      k=100, unit="%", dec=1, anno="redditi {irpef}", fonte="MEF, dichiarazioni IRPEF", desc="Redditi da lavoro dipendente rispetto al reddito imponibile totale."),
    I("b_dep", "red", "Depositi bancari per abitante", lambda r: g(r, "bank_BANK_DEP"), POP22, k=1000, unit=" €", dec=0, pol=1,
      anno="{bank}", fonte="Banca d'Italia", desc="Depositi presso le banche del comune (famiglie e imprese) diviso i residenti.", zero=("bank_BANK_DEP",)),
    I("b_spo", "red", "Sportelli bancari ogni 10.000 abitanti", lambda r: g(r, "bank_BANK_BRN"), POP22, k=10000, dec=1, pol=1,
      anno="{bank}", fonte="Banca d'Italia", desc="Filiali di banca aperte nel comune.", zero=("bank_BANK_BRN",)),
    I("b_spov", "red", "Variazione degli sportelli bancari dal {bank0}", lambda r: (g(r, "bank_BANK_BRN") or 0) - (g(r, "bank0_BANK_BRN") or 0) if (g(r, "bank0_BANK_BRN") or 0) > 0 else None,
      lambda r: g(r, "bank0_BANK_BRN"), k=100, unit="%", dec=0, pol=1, anno="{bank0}–{bank}", fonte="Banca d'Italia",
      desc="Variazione del numero di sportelli bancari.", kind="growth", fmt="signed"),

    # ---------------- lavoro
    I("l_ul", "lav", "Sedi di imprese ogni 1.000 abitanti", lambda r: g(r, "ul_lu_tot"), POP24, k=1000, dec=1, pol=1, anno="{ul}",
      fonte="ISTAT, archivio ASIA", desc="Unità locali delle imprese (negozi, uffici, stabilimenti) ogni 1.000 residenti. Esclusi agricoltura e pubblica amministrazione."),
    I("l_add", "lav", "Addetti ogni 100 abitanti", ADD23, POP24, k=100, dec=1, pol=1, anno="{ul}", fonte="ISTAT, archivio ASIA",
      desc="Persone che lavorano nelle imprese del comune (dipendenti e indipendenti) ogni 100 residenti."),
    I("l_var", "lav", "Variazione degli addetti dal {ul0}", lambda r: ADD23(r) - g(r, "ul0_add_tot") if ADD23(r) is not None and g(r, "ul0_add_tot") else None,
      lambda r: g(r, "ul0_add_tot"), k=100, unit="%", dec=1, pol=1, anno="{ul0}–{ul}", fonte="ISTAT, archivio ASIA",
      desc="Quanti posti di lavoro nelle imprese si sono creati o persi.", fmt="signed"),
    I("l_dim", "lav", "Addetti per sede d'impresa", ADD23, lambda r: g(r, "ul_lu_tot"), dec=1, anno="{ul}", fonte="ISTAT, archivio ASIA",
      desc="Dimensione media delle unità locali: valori bassi indicano un tessuto di piccole attività."),
    I("l_ind", "lav", "Addetti nell'industria", lambda r: g(r, "ul_add_ind"), ADD23, k=100, unit="%", dec=1, anno="{ul}",
      fonte="ISTAT, archivio ASIA", desc="Quota di addetti in manifattura, energia, acqua e rifiuti, estrazione."),
    I("l_tur", "lav", "Addetti in alloggio e ristorazione", lambda r: g(r, "ul_add_tur"), ADD23, k=100, unit="%", dec=1, anno="{ul}",
      fonte="ISTAT, archivio ASIA", desc="Quota di addetti in alberghi, campeggi, ristoranti e bar."),
    I("l_com", "lav", "Addetti nel commercio", lambda r: g(r, "ul_add_com"), ADD23, k=100, unit="%", dec=1, anno="{ul}",
      fonte="ISTAT, archivio ASIA", desc="Quota di addetti nel commercio all'ingrosso e al dettaglio."),
    I("l_kn", "lav", "Addetti nei servizi avanzati", lambda r: g(r, "ul_add_kn"), ADD23, k=100, unit="%", dec=1, anno="{ul}",
      fonte="ISTAT, archivio ASIA", desc="Quota di addetti in informatica e comunicazione, finanza, immobiliare, professioni e servizi alle imprese."),
    I("l_occ", "lav", "Tasso di occupazione 20–64 anni", lambda r: g(r, "mfi_EMPL_RATE_20_64") * POP24(r) if g(r, "mfi_EMPL_RATE_20_64") is not None and POP24(r) else None,
      POP24, unit="%", dec=1, pol=1, anno="{mfi}", fonte="ISTAT, indice di fragilità comunale",
      desc="Occupati ogni 100 persone tra 20 e 64 anni.", kind="wmean"),
    I("l_micro", "lav", "Addetti in microimprese", lambda r: g(r, "dips_AOIN_9EPEXPE_PE_SH_PCT") * POP24(r) if g(r, "dips_AOIN_9EPEXPE_PE_SH_PCT") is not None and POP24(r) else None,
      POP24, unit="%", dec=1, anno="{dips}", fonte="ISTAT, registri statistici", desc="Quota di addetti in imprese con meno di 10 addetti.", kind="wmean"),
    I("l_ht", "lav", "Addetti in settori ad alta conoscenza", lambda r: g(r, "dips_AOIN_HTPEXPE_PE_SH_PCT") * POP24(r) if g(r, "dips_AOIN_HTPEXPE_PE_SH_PCT") is not None and POP24(r) else None,
      POP24, unit="%", dec=1, pol=1, anno="{dips}", fonte="ISTAT, registri statistici", desc="Quota di addetti in imprese ad alta tecnologia e servizi ad alta intensità di conoscenza.", kind="wmean"),
    I("l_lau", "lav", "Laureati tra gli addetti", lambda r: g(r, "dips_AOIN_TEDPEXPE_PEA_SH_PCT") * POP24(r) if g(r, "dips_AOIN_TEDPEXPE_PEA_SH_PCT") is not None and POP24(r) else None,
      POP24, unit="%", dec=1, pol=1, anno="{dips}", fonte="ISTAT, registri statistici", desc="Addetti con laurea ogni 100 addetti tra 25 e 64 anni.", kind="wmean"),
    I("l_don", "lav", "Donne tra gli addetti", lambda r: g(r, "dips_AOIN_PEFXPE_PE_SH_PCT") * POP24(r) if g(r, "dips_AOIN_PEFXPE_PE_SH_PCT") is not None and POP24(r) else None,
      POP24, unit="%", dec=1, pol=1, anno="{dips}", fonte="ISTAT, registri statistici", desc="Donne ogni 100 addetti delle imprese.", kind="wmean"),

    # ---------------- agricoltura
    I("a_az", "agr", "Aziende agricole ogni 1.000 abitanti", lambda r: g(r, "agr_HO"), POP24, k=1000, dec=1, anno="{agr}",
      fonte="ISTAT, censimento dell'agricoltura", desc="Numero di aziende agricole ogni 1.000 residenti.", zero=("agr_HO",)),
    I("a_sau", "agr", "Terra coltivata sulla superficie del comune", lambda r: g(r, "agr_ARU"), lambda r: g(r, "carta_AREA") * 100 if g(r, "carta_AREA") else None,
      k=100, unit="%", dec=1, anno="{agr}", fonte="ISTAT, censimento dell'agricoltura",
      desc="Superficie agricola utilizzata (SAU) delle aziende con sede nel comune, rispetto alla superficie comunale.", zero=("agr_ARU",)),
    I("a_saum", "agr", "Ettari coltivati per azienda", lambda r: g(r, "agr_ARU"), lambda r: g(r, "agr_HO"), unit=" ha", dec=1,
      anno="{agr}", fonte="ISTAT, censimento dell'agricoltura", desc="Superficie agricola utilizzata media per azienda."),
    I("a_conn", "agr", "Aziende con attività connesse", lambda r: g(r, "agr_GAIN"), lambda r: g(r, "agr_HO"), k=100, unit="%", dec=1,
      pol=1, anno="{agr}", fonte="ISTAT, censimento dell'agricoltura",
      desc="Aziende che oltre a coltivare trasformano prodotti, producono energia, fanno contoterzismo, ecc.", zero=("agr_GAIN",)),
    I("a_gg", "agr", "Giornate di lavoro per azienda", lambda r: g(r, "agr_SWD"), lambda r: g(r, "agr_HO"), dec=0,
      anno="{agr}", fonte="ISTAT, censimento dell'agricoltura", desc="Giornate di lavoro standard in un anno per azienda: misura quanto sono 'vere' imprese."),
    I("a_agr", "agr", "Agriturismi ogni 10.000 abitanti", lambda r: g(r, "agritur_ALL"), POP24, k=10000, dec=1, anno="{agritur}",
      fonte="ISTAT, indagine sugli agriturismi", desc="Aziende agrituristiche autorizzate.", zero=("agritur_ALL",)),
    I("a_agrv", "agr", "Crescita degli agriturismi dal {agritur0}", lambda r: (g(r, "agritur_ALL") or 0) - (g(r, "agritur0_ALL") or 0) if (g(r, "agritur0_ALL") or 0) >= 5 else None,
      lambda r: g(r, "agritur0_ALL"), k=100, unit="%", dec=0, anno="{agritur0}–{agritur}", fonte="ISTAT, indagine sugli agriturismi",
      desc="Variazione del numero di agriturismi (solo comuni che all'inizio ne avevano almeno 5).", kind="growth", fmt="signed"),
    I("a_dop", "agr", "Produttori DOP e IGP ogni 10.000 abitanti", lambda r: g(r, "dop_PROD_PDOPGI"), POP24, k=10000, dec=1, anno="{dop}",
      fonte="ISTAT, prodotti di qualità", desc="Aziende che producono prodotti a denominazione d'origine (olio, vino escluso, formaggi…).", zero=("dop_PROD_PDOPGI",)),

    # ---------------- cultura e turismo
    I("c_mus", "cul", "Musei e luoghi della cultura ogni 10.000 abitanti", lambda r: g(r, "mus_M001"), POP22, k=10000, dec=1, pol=1,
      anno="{mus}", fonte="ISTAT, indagine sui musei", desc="Musei, gallerie, aree archeologiche e monumenti aperti al pubblico.", zero=("mus_M001",)),
    I("c_vis", "cul", "Visitatori dei musei per abitante", lambda r: g(r, "mus_M024"), POP22, dec=2, pol=1, anno="{mus}",
      fonte="ISTAT, indagine sui musei", desc="Ingressi nei musei del comune diviso i residenti.", zero=("mus_M024",)),
    I("c_bib", "cul", "Biblioteche ogni 10.000 abitanti", lambda r: g(r, "bib_B001"), POP22, k=10000, dec=1, pol=1, anno="{bib}",
      fonte="ISTAT, indagine sulle biblioteche", desc="Biblioteche pubbliche e private aperte al pubblico.", zero=("bib_B001",)),
    I("c_let", "cul", "Posti di lettura in biblioteca ogni 1.000 abitanti", lambda r: g(r, "bib_B010"), POP22, k=1000, dec=1, pol=1, anno="{bib}",
      fonte="ISTAT, indagine sulle biblioteche", desc="Posti a sedere per leggere e studiare.", zero=("bib_B010",)),
    I("t_let", "cul", "Posti letto turistici ogni 100 abitanti", lambda r: g(r, "cap_BEDS"), POP22, k=100, dec=1,
      anno="{cap}", fonte="ISTAT, capacità degli esercizi ricettivi", desc="Posti letto in alberghi, campeggi, agriturismi, B&B e case vacanze.",
      zero=("cap_BEDS",)),
    I("t_es", "cul", "Strutture ricettive ogni 1.000 abitanti", lambda r: g(r, "cap_NUM_EST"), POP22, k=1000, dec=1,
      anno="{cap}", fonte="ISTAT, capacità degli esercizi ricettivi", desc="Numero di esercizi ricettivi.", zero=("cap_NUM_EST",)),

    # ---------------- salute e servizi
    I("s_let", "ser", "Posti letto in ospedale ogni 1.000 abitanti", lambda r: s(r, "osp_19", "osp_28"), POP24, k=1000, dec=1,
      anno="{osp}", fonte="Ministero della Salute", desc="Posti letto ordinari e di day hospital negli ospedali che si trovano nel comune. Un ospedale serve anche i comuni vicini.",
      zero=("osp_19", "osp_28")),
    I("s_ifc", "ser", "Indice di fragilità comunale", lambda r: g(r, "mfi_COMP_FRAG_INDEX_DECILE"), lambda r: 1, dec=0, pol=-1, anno="{mfi}",
      fonte="ISTAT, indice di fragilità comunale",
      desc="Da 1 (comuni meno fragili d'Italia) a 10 (più fragili). Combina dodici aspetti: demografia, lavoro, istruzione, servizi, ambiente.",
      kind="median"),
    I("s_ist", "ser", "Adulti con al massimo la licenza media", lambda r: g(r, "mfi_POP_25_64_UNDER_DIP_LOW_SEC_EDU") * POP24(r) if g(r, "mfi_POP_25_64_UNDER_DIP_LOW_SEC_EDU") is not None and POP24(r) else None,
      POP24, unit="%", dec=1, pol=-1, anno="{mfi}", fonte="ISTAT, indice di fragilità comunale", desc="Persone tra 25 e 64 anni senza diploma.", kind="wmean"),

    # ---------------- mobilità
    I("m_auto", "mob", "Automobili ogni 1.000 abitanti", lambda r: g(r, "veh_1"), POP24, k=1000, dec=0, anno="{veh}",
      fonte="ACI, pubblico registro automobilistico", desc="Autovetture iscritte al PRA."),
    I("m_old", "mob", "Auto più inquinanti (Euro 0–3)", lambda r: s(r, "veh_13", "veh_14", "veh_15", "veh_16"), lambda r: g(r, "veh_1"),
      k=100, unit="%", dec=1, pol=-1, anno="{veh}", fonte="ACI, pubblico registro automobilistico", desc="Quota di auto con classe di emissione Euro 0, 1, 2 o 3."),
    I("m_e6", "mob", "Auto Euro 6", lambda r: g(r, "veh_19"), lambda r: g(r, "veh_1"), k=100, unit="%", dec=1, pol=1, anno="{veh}",
      fonte="ACI, pubblico registro automobilistico", desc="Quota di auto della classe di emissione più recente."),
    I("m_inc", "mob", "Incidenti con feriti ogni 10.000 abitanti", lambda r: g(r, "inc3_ROADACC_9"), lambda r: g(r, "bil3_DEC_CP"), k=10000, dec=1,
      pol=-1, anno="media {inc3}", fonte="ISTAT, incidenti stradali", desc="Incidenti stradali con morti o feriti avvenuti nel comune, media annua.",
      zero=("inc3_ROADACC_9",)),
    I("m_mor", "mob", "Morti sulle strade ogni 100.000 abitanti", lambda r: g(r, "inc3_KILLINJ_M"), lambda r: g(r, "bil3_DEC_CP"), k=100000, dec=1,
      pol=-1, anno="media {inc3}", fonte="ISTAT, incidenti stradali", desc="Morti in incidenti stradali avvenuti nel comune, media annua.",
      zero=("inc3_KILLINJ_M",)),

    # ---------------- ambiente
    I("w_erog", "amb", "Acqua erogata per abitante al giorno", lambda r: g(r, "acqua_ACQ_EROG"), lambda r: g(r, "carta_JAN") * 365 / 1e6 if g(r, "carta_JAN") else None,
      unit=" litri", dec=0, anno="{acqua}", fonte="ISTAT, censimento delle acque",
      desc="Acqua potabile consegnata agli utenti (famiglie, negozi, scuole…), in litri per residente al giorno."),
    I("w_perd", "amb", "Perdite della rete idrica", lambda r: g(r, "acqua_ACQ_IMM") - g(r, "acqua_ACQ_EROG") if g(r, "acqua_ACQ_IMM") and g(r, "acqua_ACQ_EROG") is not None else None,
      lambda r: g(r, "acqua_ACQ_IMM"), k=100, unit="%", dec=1, pol=-1, anno="{acqua}", fonte="ISTAT, censimento delle acque",
      desc="Quota dell'acqua immessa in rete che non arriva agli utenti."),
    I("e_rif", "amb", "Rifiuti indifferenziati per abitante", lambda r: g(r, "mfi_UNDIF_COLL_URBAN_WASTE") * POP24(r) if g(r, "mfi_UNDIF_COLL_URBAN_WASTE") is not None and POP24(r) else None,
      POP24, unit=" kg", dec=0, pol=-1, anno="{mfi}", fonte="ISTAT, indice di fragilità comunale (dati ISPRA)", desc="Rifiuti urbani non differenziati, kg per abitante in un anno. Nei comuni turistici il valore è gonfiato dai rifiuti prodotti dai visitatori.", kind="wmean"),
    I("e_suo", "amb", "Suolo consumato", lambda r: g(r, "mfi_LAND_CONSUMPTION") * g(r, "carta_AREA") if g(r, "mfi_LAND_CONSUMPTION") is not None and g(r, "carta_AREA") else None,
      lambda r: g(r, "carta_AREA"), unit="%", dec=1, pol=-1, anno="{mfi}", fonte="ISTAT, indice di fragilità comunale (dati ISPRA)",
      desc="Quota del territorio coperta da edifici, strade, piazzali e altre superfici artificiali.", kind="wmean"),
    I("e_fra", "amb", "Territorio a rischio frane", lambda r: g(r, "mfi_LANDSLIDE_HAZARD_ZONES") * g(r, "carta_AREA") if g(r, "mfi_LANDSLIDE_HAZARD_ZONES") is not None and g(r, "carta_AREA") else None,
      lambda r: g(r, "carta_AREA"), unit="%", dec=1, pol=-1, anno="{mfi}", fonte="ISTAT, indice di fragilità comunale (dati ISPRA)",
      desc="Quota del territorio in aree a pericolosità da frana elevata o molto elevata.", kind="wmean"),
    I("e_pro", "amb", "Aree naturali protette", lambda r: g(r, "mfi_PROTECTED_NAT_AREAS") * g(r, "carta_AREA") if g(r, "mfi_PROTECTED_NAT_AREAS") is not None and g(r, "carta_AREA") else None,
      lambda r: g(r, "carta_AREA"), unit="%", dec=1, pol=1, anno="{mfi}", fonte="ISTAT, indice di fragilità comunale",
      desc="Quota del territorio in parchi, riserve e siti Natura 2000.", kind="wmean"),
]
