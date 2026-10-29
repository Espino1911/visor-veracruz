"""Lista nominal vigente por sección (INE, Datos Abiertos DERFE: padrón y lista nominal por entidad de origen).
Uso: python3 -I lista_nominal.py XLSX CATALOGO_JSON RESULTADOS_JSON OUT_JSON FECHA(YYYY-MM-DD)
La lista nominal de cada sección es la suma de todas las columnas LN_* (electores por entidad de nacimiento).
Secciones creadas después de la cartografía se reasignan a la sección de la que provienen, por municipio y distrito.
"""
import sys, json
import pandas as pd

XLSX, CATF, RESF, OUT, FECHA = sys.argv[1:6]
d = pd.read_excel(XLSX)
d.columns = [c.replace('\n', ' ') for c in d.columns]
v = d[d['CLAVE ENTIDAD'] == 30].copy()
v['LN'] = v[[c for c in v.columns if c.startswith('LN')]].sum(axis=1).astype(int)
v['PAD'] = v[[c for c in v.columns if c.startswith('PAD')]].sum(axis=1).astype(int)
v['NAC_VER'] = v['LN_VERACRUZ'].astype(int)
v['SECCION'] = v.SECCION.astype(int)

cat = json.load(open(CATF))
res = json.load(open(RESF))
nreal = len(cat['sec']) - len(cat.get('virtual', {}))
real = {cat['sec'][i]: i for i in range(nreal)}
ext = v[v.SECCION == 0]
v = v[v.SECCION > 0]
known = v[v.SECCION.isin(real)]
new = v[~v.SECCION.isin(real)]
gone = [s for s in real if s not in set(v.SECCION)]

N = len(cat['sec'])
ln = [None] * N; pad = [None] * N; nac = [None] * N
for r in known.itertuples():
    i = real[r.SECCION]; ln[i] = int(r.LN); pad[i] = int(r.PAD); nac[i] = int(r.NAC_VER)

# Reasignación de secciones nuevas a las desaparecidas del mismo municipio y distrito federal
asign = []
for (m, df), grp in new.groupby(['CLAVE MUNICIPIO', 'CLAVE DISTRITO']):
    targets = [s for s in gone if cat['mun'][real[s]] == m and cat['df'][real[s]] == df]
    if not targets:
        asign.append({'nuevas': grp.SECCION.tolist(), 'origen': None, 'nota': 'sin sección de origen identificable'})
        continue
    # Reparto proporcional a la lista nominal de la elección más reciente con datos
    def base(s):
        i = real[s]
        for e in ['AYU25', 'PRES24', 'GUB24', 'DL24', 'DF24']:
            if e in res and res[e]['ln'][i]:
                return res[e]['ln'][i]
        return 1
    w = {s: base(s) for s in targets}; tw = sum(w.values())
    for col, arr in [('LN', ln), ('PAD', pad), ('NAC_VER', nac)]:
        tot = int(grp[col].sum())
        for s in targets:
            arr[real[s]] = round(tot * w[s] / tw)
    asign.append({'nuevas': grp.SECCION.tolist(), 'origen': targets, 'reparto': 'proporcional' if len(targets) > 1 else 'directo'})
sin = [s for s in gone if ln[real[s]] is None]

# Entradas virtuales (secciones de origen de reseccionamientos previos): suma de sus hijas
for old, kids in cat.get('virtual', {}).items():
    vi = cat['sec'].index(int(old))
    for arr in (ln, pad, nac):
        vals = [arr[real[k]] for k in kids if arr[real[k]] is not None]
        arr[vi] = sum(vals) if vals else None

out = {'fecha': FECHA, 'fuente': 'INE, Datos Abiertos DERFE, padrón y lista nominal por entidad de origen',
       'total': int(v.LN.sum()), 'padron': int(v.PAD.sum()), 'extranjero': int(ext.LN.sum()),
       'ln': ln, 'pad': pad, 'nacVer': nac,
       'reasignadas': asign, 'sinLista': sin}
json.dump(out, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
print(json.dumps({k: out[k] for k in ['fecha', 'total', 'padron', 'extranjero', 'reasignadas', 'sinLista']}, ensure_ascii=False, indent=1))
print('secciones con lista:', sum(1 for x in ln[:nreal] if x is not None), 'de', nreal)
