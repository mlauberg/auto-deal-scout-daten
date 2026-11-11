#!/usr/bin/env python3
"""Marktmodell Mazda 3: neuester AutoScout24 Vollabzug aus ../daten (bis 21.000 Euro, Getriebe sicher) plus Kleinanzeigen und Autohero Zeilen aus dem ersten Bestand.
Aufruf: python3 skripte/marktmodell.py --ezmax 2022 --huber   (so wurde das Modell vom 11.11.2026 gerechnet)"""
import csv, sys, re, math, json, random, datetime, os, glob
import numpy as np
DATEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'daten')
VOLL = sorted(glob.glob(os.path.join(DATEN, 'as24_voll_*.csv')))[-1]
HEUTE = datetime.date.fromisoformat(os.path.basename(VOLL)[10:20])
BAD = re.compile(r'unfall(?!frei)|schaden|betrug|verdacht|unplausibel|defekt|bastler|export|lock', re.I)
LINIEN = ['prime', 'selection', 'exclusive', 'sports', 'homura', 'nagisa', 'center', 'signature', 'kizoku', 'edition', 'takumi']
def variante(kw, ez):
    kw = int(kw)
    if kw == 88: return 'BN120' if ez <= '2019-06' else None
    return {121: 'BN165', 90: 'BP122', 110: 'BP150', 132: 'X180', 137: 'X186'}.get(kw)
def key(ez, km, kw, plz): return '%s|%d|%s' % (ez, round(int(km), -3), kw)   # ohne PLZ: Autohero listet dasselbe Auto an mehreren Orten
recs, seen_id, seen_key = [], set(), set()
def addrec(r):
    if r['id'] and r['id'] in seen_id: return
    k = key(r['ez'], r['km'], r['kw'], r['plz'])
    if k in seen_key: return
    seen_id.add(r['id']); seen_key.add(k); recs.append(r)
neu = list(csv.DictReader(open(VOLL, encoding='utf-8')))
for x in neu:
    try:
        ez = x['ez'][:7]; km = int(x['km']); p = int(x['preis']); kw = int(x['kw'])
    except (ValueError, KeyError): continue
    addrec(dict(id=x['id'], quelle='AS24', ez=ez, km=km, kw=kw, preis=p, getriebe=x['getriebe'] or '?',
                haendler=0 if x['verkaeufer'].strip() == 'P' else 1, plz=x.get('plz', ''), text=x.get('titel', '')))
gear = {x['id']: x['getriebe'] for x in neu if x['id']}
alt_as24 = 0
for x in csv.DictReader(open(os.path.join(DATEN, 'bestand_seed_2026-11-08.csv'), encoding='utf-8')):
    if x['quelle'] == 'AS24':
        if x['id'] not in gear: alt_as24 += 1
        continue   # AS24 kommt komplett aus dem frischen Vollabzug
    g = x['getriebe'] if x['getriebe'] in ('AT', 'MT') else ('AT' if 'AT' in x['ausstattung'].split() else '?')
    addrec(dict(id=x['id'], quelle=x['quelle'], ez=x['ez'], km=int(float(x['km'])), kw=int(x['kw']), preis=int(float(x['preis_jetzt'])),
                getriebe=g, haendler=1 if x['verkaeufer'].startswith('H') else 0, plz=x['plz'], text=(x['linie'] or '') + ' ' + (x['bemerkung'] or '')))
use_linie = '--linie' in sys.argv
EZMAX = int(sys.argv[sys.argv.index('--ezmax') + 1]) if '--ezmax' in sys.argv else 2023
KNICK = '--knick' in sys.argv; QUAD = '--quad' in sys.argv; HUBER = '--huber' in sys.argv; ATBP = '--atbp' in sys.argv
pmax = int(sys.argv[sys.argv.index('--max') + 1]) if '--max' in sys.argv else 10**9
NAMES = ['basis', 'km', 'alter', 'bp', 'alter_bp', 'km_bp', 'BN165', 'BP150', 'X180', 'X186', 'automatik', 'getriebe_offen', 'haendler']
LN = [l for l in LINIEN] if use_linie else []
def feats(r):
    v = variante(r['kw'], r['ez'])
    if v is None: return None
    y, m = int(r['ez'][:4]), int(r['ez'][5:7])
    if not 2017 <= y <= EZMAX: return None
    age = HEUTE.year - y + (HEUTE.month - m) / 12; km = r['km'] / 1e4; bp = 0 if v.startswith('BN') else 1
    f = [1, km, age, bp, age * bp, km * bp] + [1 if v == t else 0 for t in ('BN165', 'BP150', 'X180', 'X186')] + \
        [1 if r['getriebe'] == 'AT' else 0, 1 if r['getriebe'] == '?' else 0, r['haendler']]
    t = r['text'].lower()
    if KNICK: f += [max(0.0, km - 9.0), max(0.0, km - 9.0) * bp]
    if QUAD: f += [age * age, km * km, age * km]
    if ATBP: f += [bp * (1 if r['getriebe'] == 'AT' else 0)]
    return f + [1 if l in t else 0 for l in LN]
X, y, meta = [], [], []
for r in recs:
    if BAD.search(r['text']) or not (5000 < r['preis'] <= pmax): continue
    f = feats(r)
    if f is None: continue
    X.append(f); y.append(r['preis']); meta.append(r)
X, y = np.array(X, float), np.array(y, float); yl = np.log(y)
def ols(A, b, w=None):
    if w is None: w = np.ones(len(b))
    Aw = A * w[:, None]
    return np.linalg.solve(A.T @ Aw + 1e-3 * np.eye(A.shape[1]), Aw.T @ b)
def fit(A, b):
    be = ols(A, b)
    if not HUBER: return be
    for _ in range(20):
        r = b - A @ be; s_ = np.median(np.abs(r - np.median(r))) * 1.4826; c = 1.345 * s_
        w = np.where(np.abs(r) <= c, 1.0, c / np.maximum(np.abs(r), 1e-9)); be = ols(A, b, w)
    return be
b0 = fit(X, yl); r0 = yl - X @ b0; mad = np.median(np.abs(r0 - np.median(r0))) * 1.4826; keepm = np.abs(r0) < 3 * mad
X, y, yl = X[keepm], y[keepm], yl[keepm]; meta = [m for m, k in zip(meta, keepm) if k]
idx = list(range(len(y))); random.seed(1); random.shuffle(idx); pred = np.zeros(len(y))
for k in range(5):
    te = idx[k::5]; tes = set(te); tr = [i for i in idx if i not in tes]
    pred[te] = np.exp(X[te] @ fit(X[tr], yl[tr]))
e = pred - y; beta = fit(X, yl)
def err(mask, name):
    if mask.sum() < 5: return
    print('  %-34s n=%3d  RMSE %5.0f  Median %4.0f  Bias %+5.0f' % (name, mask.sum(), np.sqrt((e[mask] ** 2).mean()), np.median(np.abs(e[mask])), e[mask].mean()))
print('Daten: AS24 neu %d Zeilen, im Modell n=%d (entfernt %d), alte AS24 Seed Zeilen nicht mehr gefunden: %d' % (len(neu), len(y), (~keepm).sum(), alt_as24))
print('Getriebe im Modell:', {g: sum(1 for m in meta if m['getriebe'] == g) for g in ('AT', 'MT', '?')})
var = np.array([variante(m['kw'], m['ez']) for m in meta]); pr = y
err(np.ones(len(y), bool), 'alle')
err(pr <= 16500, 'Preis bis 16.500')
err((pr > 11000) & (pr <= 15000), 'Preis 11.000 bis 15.000')
err(pred <= 16500, 'Modellwert bis 16.500')
for v in ('BN120', 'BN165', 'BP122', 'BP150', 'X180', 'X186'): err(var == v, v)
err(np.array([m['getriebe'] == 'AT' for m in meta]), 'Automatik')
kmv = np.array([m['km'] for m in meta]); bpm = np.array([not str(v).startswith('BN') for v in var]); atm = np.array([m['getriebe'] == 'AT' for m in meta])
for lo, hi in ((0, 60000), (60000, 80000), (80000, 95000), (95000, 131000)):
    err(bpm & (kmv >= lo) & (kmv < hi), 'BP km %d bis %d' % (lo, hi)); err(~bpm & (kmv >= lo) & (kmv < hi), 'BN km %d bis %d' % (lo, hi))
err(bpm & atm & (kmv >= 90000), 'BP Automatik ab 90.000 km'); err(bpm & ~atm & (kmv >= 90000), 'BP Schalter ab 90.000 km')
allnames = NAMES + (['km_ueber_90', 'km_ueber_90_bp'] if KNICK else []) + (['alter2', 'km2', 'alter_km'] if QUAD else []) + (['automatik_bp'] if ATBP else []) + LN
print('Koeffizienten (Prozent):', {n: round((math.exp(v) - 1) * 100, 1) for n, v in zip(allnames[1:], beta[1:])})
print('BP je Jahr: %.1f %%, BP je 10.000 km: %.1f %%' % ((math.exp(beta[2] + beta[4]) - 1) * 100, (math.exp(beta[1] + beta[5]) - 1) * 100))
K = {n: round(float(v), 5) for n, v in zip(allnames, beta)}
print('K =', json.dumps(K))
