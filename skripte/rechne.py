import sys, json, math, datetime
from decimal import Decimal, ROUND_HALF_UP
# Marktmodell Mazda 3 (log Preis), Stand 11.11.2026, 342 Inserate, typischer Fehler ca. 750, in zwei Dritteln der Fälle höchstens ca. 1.100 Euro
K = {"basis": 10.03075, "km": -0.0194, "alter": -0.04146, "bp": -0.02793, "alter_bp": 0.01695, "km_bp": -0.00076, "BN165": 0.03799, "BP150": 0.02897, "X180": 0.08007, "X186": 0.05058, "automatik": 0.05013, "getriebe_offen": -0.0242, "haendler": 0.03679}
VAR = ("BN120", "BN165", "BP122", "BP150", "X180", "X186")
def r1(x): return float(Decimal(repr(round(x, 6))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
def de(x): return ("%.1f" % x).replace(".", ",")
def kurz(x): return de(x).replace(",0", "")
def zehn(x): return int(round(x / 10) * 10)
def eur(x): return "{:,}".format(zehn(x)).replace(",", ".")
def modellwert(a, heute, haendler=None):
    v = a.get("variante")
    j, m = int(a["ez"][:4]), int(a["ez"][5:7] or 6)
    if v not in VAR or not 2017 <= j <= 2022: return None
    alter = heute.year - j + (heute.month - m) / 12
    km = a["km"] / 10000
    x = K["basis"] + K["km"] * km + K["alter"] * alter + K.get(v, 0)
    if v[:2] != "BN": x += K["bp"] + K["alter_bp"] * alter + K["km_bp"] * km
    at = a.get("automatik")
    x += K["automatik"] if at is True else (K["getriebe_offen"] if at is None else 0)
    if a.get("haendler") if haendler is None else haendler: x += K["haendler"]
    w = math.exp(x)
    return w if w <= 18000 else None
def rechne(a, cfg, heute):
    preis, hin, unplausibel = a["preis"], [], False
    e = preis + a.get("zusatzkosten", 0)
    mm = modellwert(a, heute)
    n = a.get("n_vergleiche", 0)
    vm = a.get("vergleichsmedian") if n >= 3 else None
    if mm and vm:
        M = (mm + vm) / 2 if abs(mm - vm) <= 1000 else min(mm, vm)
        if abs(mm - vm) > 1000: hin.append("Marktwert unsicher (Modell %s, Vergleiche %s)" % (eur(mm), eur(vm)))
    elif mm: M = mm; hin.append("nur Modell")
    else: M = vm
    nur_modell = bool(mm) and not vm
    if M is None: P = 5.5; hin.append("dünne Basis")
    else:
        d = (M - e) / M
        if d > 0.20: P = 5.5; unplausibel = True; hin.append("prüfen: Preis unplausibel")
        else: P = min(10.0, max(0.0, 5.5 + 37.5 * d))
        if a.get("wildcard") and n < 5: P = min(P, 7.5); hin.append("dünne Basis")
        if nur_modell: P = min(P, 8.0)
    P = r1(P)
    kv, av = max(140000, a["km"] + 60000), 2030 - int(a["ez"][:4])
    W = r1(min(10.0, max(0.0, 10 - (kv - 140000) / 10000 - 0.5 * max(0, av - 10))))
    ps, v = a.get("ps") or 0, a.get("variante")
    L = 9 if v == "X180" else 10 if (ps >= 180 or v == "X186") else 8 if ps >= 160 else 7 if ps >= 140 else 5 if ps >= 126 else 3
    klein = 0.5 if a.get("kleinwagen") else 0
    vor = r1(0.40 * P + 0.15 * W + 0.20 * a["z"] + 0.15 * a["a"] + 0.10 * L - klein)
    ab = cfg["abzug_ab"]
    if preis > ab: korr = -0.3 * math.ceil((preis - ab) / 500)
    elif (ps >= 150 or v in ("X180", "X186")) and not unplausibel: korr = min(0.6, 0.2 * math.floor((ab - preis) / 500))
    else: korr = 0.0
    planb = 0.5 if a.get("wildcard") else 0
    nach = r1(min(10.0, max(0.0, vor + korr - planb)))
    teile = "P%s W%s Z%s A%s L%s" % (kurz(P), kurz(W), kurz(a["z"]), kurz(a["a"]), L)
    zus = [("Abzug %s" % kurz(-korr)) if korr < 0 else ("Bonus %s" % kurz(korr)) if korr > 0 else "Abzug 0"]
    if klein: zus.append("Kleinwagen minus 0,5")
    if planb: zus.append("Plan B minus 0,5")
    if M: zus.append("M %s" % eur(M))
    zelle = "%s → %s (%s, %s)" % (de(vor), de(nach), teile, ", ".join(zus)) + ("".join(", " + h for h in hin))
    ok = preis <= cfg["top5"] and not unplausibel
    out = {"name": a.get("name", ""), "zelle": zelle, "vor": vor, "korrektur": round(korr - planb, 1), "nach": nach,
           "modellwert": mm and zehn(mm), "M": M and zehn(M), "unter_markt_prozent": M and round((M - e) / M * 100, 1),
           "ueber_top5": preis > cfg["top5"], "meldenswert_moeglich": ok and nach >= 7.5,
           "ausreisser_moeglich": ok and nach >= 8.0 and nach >= cfg.get("massstab", 0)}
    rw = modellwert(a, heute, haendler=False)
    if rw:
        jahre = (datetime.date(2030, 4, 1) - heute).days / 365.25
        rw = rw * math.exp(-0.055 * jahre + 6 * K["km"]) * 0.93
        out["restwert_2030"] = zehn(rw)
        out["wertverlust_pro_jahr"] = zehn((a.get("zielpreis", preis) - rw) / 3)
    return out
if __name__ == "__main__":
    if sys.argv[1:] == ["test"]:
        t = rechne({"name": "Soest", "preis": 14000, "zusatzkosten": 0, "ez": "2020-10", "km": 100000, "variante": "BP150", "automatik": True, "haendler": False, "ps": 150, "z": 7.5, "a": 8, "vergleichsmedian": 16430, "n_vergleiche": 5, "wildcard": False, "kleinwagen": False}, {"abzug_ab": 13500, "top5": 15000, "massstab": 0}, datetime.date(2026, 11, 11))
        print("Test ok" if t["zelle"] == "8,6 → 8,3 (P10 W8 Z7,5 A8 L7, Abzug 0,3, M 16.630)" else "Test FEHLER: " + t["zelle"])
    else:
        cfg = json.load(open(sys.argv[1], encoding="utf-8"))
        for a in cfg["autos"]:
            print(json.dumps(rechne(a, cfg, datetime.date.today()), ensure_ascii=False))
