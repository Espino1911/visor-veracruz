"""ETL Visor Geoelectoral Veracruz.
Uso: python3 -I build.py RAW_DIR OUT_DIR
Lee cartografía INE (SECCION, DISTRITO_FEDERAL, DISTRITO_LOCAL, MUNICIPIO) y bases PREP/cómputos por casilla,
agrega casilla -> sección y escribe JSON compactos para el visor.
Reglas: solo actas contabilizadas (CONTABILIZADA == '1'); se excluyen casillas especiales (S) y voto anticipado (A),
que no pertenecen a la votación de una sección; la lista nominal se toma de las actas contabilizadas.
"""
import sys, io, json, os
import pandas as pd, numpy as np

RAW, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)

def load(path):
    import re
    raw = open(path, 'rb').read().decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    raw = re.sub(r"(^|,)'", r"\1", raw[raw.index('CLAVE_CASILLA'):], flags=re.M)  # PREP 2025 antepone apóstrofo
    df = pd.read_csv(io.StringIO(raw), dtype=str, low_memory=False, keep_default_na=False)
    df = df.rename(columns={'MOR': 'MORENA'})
    return df[df.ID_ENTIDAD.str.strip() == '30'].copy()

# Partidos y bloques. Cada bloque suma votos por partido + combinaciones de coalición.
PARTIES = ['PAN', 'PRI', 'PRD', 'PVEM', 'PT', 'MORENA', 'MC', 'FXMV']
ELECTIONS = {
    'PRES24': dict(file='PRES_2024.csv', name='Presidencia 2024', short='Pres 24', ambito='federal',
                   blocks={'SHH': ['PVEM', 'PT', 'MORENA', 'PVEM_PT_MORENA', 'PVEM_PT', 'PVEM_MORENA', 'PT_MORENA'],
                           'FCV': ['PAN', 'PRI', 'PRD', 'PAN-PRI-PRD', 'PAN-PRI', 'PAN-PRD', 'PRI-PRD'],
                           'MC': ['MC']}),
    'GUB24': dict(file='VER_GUB_2024.csv', name='Gubernatura 2024', short='Gub 24', ambito='local',
                  blocks={'SHH': ['PVEM', 'PT', 'MORENA', 'FXMV', 'C_PVEM_PT_MORENA_FXMV', 'C_PVEM_PT_MORENA', 'C_PVEM_PT_FXMV',
                                  'C_PVEM_MORENA_FXMV', 'C_PT_MORENA_FXMV', 'C_PVEM_PT', 'C_PVEM_MORENA', 'C_PVEM_FXMV',
                                  'C_PT_MORENA', 'C_PT_FXMV', 'C_MORENA_FXMV'],
                          'FCV': ['PAN', 'PRI', 'PRD', 'C_PAN_PRI_PRD', 'C_PAN_PRI', 'C_PAN_PRD', 'C_PRI_PRD'],
                          'MC': ['MC']}),
    'DL24': dict(file='VER_DIP_LOC_2024.csv', name='Diputaciones locales 2024', short='DL 24', ambito='local',
                 blocks={'SHH': ['PVEM', 'PT', 'MORENA', 'C_PVEM_PT_MORENA', 'C_PVEM_PT', 'C_PVEM_MORENA', 'C_PT_MORENA'],
                         'FCV': ['PAN', 'PRI', 'PRD', 'C_PAN_PRI_PRD', 'C_PAN_PRI', 'C_PAN_PRD', 'C_PRI_PRD'],
                         'MC': ['MC'], 'FXMV': ['FXMV']},
                 note='En los distritos locales 04 y 16 PVEM, PT y MORENA compitieron por separado; el bloque suma sus votos.'),
    'DF24': dict(file='DIP_FED_2024.csv', name='Diputaciones federales 2024', short='DF 24', ambito='federal',
                 blocks={'SHH': ['PVEM', 'PT', 'MORENA', 'PVEM_PT_MORENA', 'PVEM_PT', 'PVEM_MORENA', 'PT_MORENA'],
                         'FCV': ['PAN', 'PRI', 'PRD', 'PAN-PRI-PRD', 'PAN-PRI', 'PAN-PRD', 'PRI-PRD'],
                         'MC': ['MC']}),
    'AYU25': dict(file='VER_AYUN_2025.csv', name='Ayuntamientos 2025', short='Ayu 25', ambito='local',
                  blocks={'SHH': ['MORENA', 'PVEM', 'PT', 'C_PVEM_MOR'], 'FCV': ['PAN', 'PRI'], 'MC': ['MC'],
                          'IND': ['CAND_IND_1', 'CAND_IND_2']},
                  note='En 2025 PVEM y MORENA fueron en coalición en 167 municipios; PT compitió solo; PAN y PRI fueron por separado y aquí se suman como bloque; hubo candidaturas independientes en 15 municipios.'),
}

def num(s):
    return pd.to_numeric(s, errors='coerce')

# ---------- Cartografía ----------
import geopandas as gpd
C = os.path.join(RAW, 'carto', '30')
sec = gpd.read_file(f'{C}/SECCION.shp')
mun = gpd.read_file(f'{C}/MUNICIPIO.shp')
munname = dict(zip(mun.municipio.astype(int), mun.nombre))
sec['seccion'] = sec.seccion.astype(int)
sec = sec.sort_values('seccion').reset_index(drop=True)
assert sec.seccion.is_unique, 'secciones duplicadas en cartografía'
catalog = {'sec': sec.seccion.tolist(), 'df': sec.distrito_f.astype(int).tolist(), 'dl': sec.distrito_l.astype(int).tolist(),
           'mun': sec.municipio.astype(int).tolist(), 'tipo': sec.tipo.astype(int).tolist(),
           'munName': {str(k): v for k, v in sorted(munname.items())}}
# ---------- Equivalencias por reseccionamiento ----------
# Secciones que existen en los resultados pero ya no en la cartografía vigente se agregan como entradas "virtuales"
# (sin polígono propio); sus secciones hijas actuales se pintan con el resultado de la sección de origen.
OLD_SHP = sys.argv[3] if len(sys.argv) > 3 else None
secs_by_e = {}
for k, E in ELECTIONS.items():
    d0 = load(os.path.join(RAW, E['file']))
    secs_by_e[k] = {int(s) for s in d0.SECCION.str.strip() if s.isdigit()}
result_secs = set().union(*secs_by_e.values())
orphans = sorted(result_secs - set(catalog['sec']))
# Las hijas se buscan entre secciones vigentes sin votación propia en las elecciones donde existió la sección de origen
orphan_elecs = [k for k, ss in secs_by_e.items() if ss & set(orphans)]
had_votes = set().union(*(secs_by_e[k] for k in orphan_elecs)) if orphan_elecs else set()
catalog['parent'] = [None] * len(catalog['sec'])
catalog['virtual'] = {}
if orphans and OLD_SHP:
    o = gpd.read_file(OLD_SHP)
    o['old'] = o.SECCION.astype(int)
    o = o[o.old.isin(orphans)].to_crs(sec.crs)
    parts = []
    for old in orphans:
        # hijas: secciones vigentes sin votación propia en las elecciones donde votó la sección de origen
        elecs = [k for k, ss in secs_by_e.items() if old in ss]
        voted = set().union(*(secs_by_e[k] for k in elecs))
        cand = sec[~sec.seccion.isin(voted)][['seccion', 'geometry']]
        xo = gpd.overlay(cand, o[o.old == old][['old', 'geometry']], how='intersection')
        if len(xo):
            xo['a'] = xo.area
            parts.append(xo)
    x = pd.concat(parts)
    x = x.sort_values('a').groupby('seccion').last()
    allc = sec.set_index('seccion').area
    x['share'] = x.a / allc.reindex(x.index)
    x = x[x.share >= 0.5]
    catalog['virtualElec'] = {}
    for old in orphans:
        kids = sorted(int(k) for k in x.index[x.old == old])
        if not kids:
            continue
        ki = [catalog['sec'].index(k) for k in kids]
        mode = lambda f: max(set(catalog[f][i] for i in ki), key=[catalog[f][i] for i in ki].count)
        vi = len(catalog['sec'])
        for f in ['df', 'dl', 'mun', 'tipo']:
            catalog[f].append(mode(f))
        catalog['sec'].append(old)
        catalog['parent'].append(None)
        for i in ki:
            catalog['parent'][i] = vi
        catalog['virtual'][str(old)] = kids
        catalog['virtualElec'][str(old)] = [k for k, ss in secs_by_e.items() if old in ss]
    x.reset_index()[['seccion', 'old', 'share']].to_csv(f'{OUT}/equivalencias_reseccionamiento.csv', index=False)
idx = {s: i for i, s in enumerate(catalog['sec'])}
report = {'cartografia': {'secciones': len(sec), 'distritos_federales': int(sec.distrito_f.nunique()),
                          'distritos_locales': int(sec.distrito_l.nunique()), 'municipios': int(sec.municipio.nunique())},
          'elecciones': {}}

# ---------- Resultados ----------
elections_out = {}
for key, E in ELECTIONS.items():
    d = load(os.path.join(RAW, E['file']))
    n0 = len(d)
    r = {'actas_estatales': n0}
    r['excluidas_especiales'] = int(d.TIPO_CASILLA.isin(['S', 'A', 'P']).sum())
    r['excluidas_anticipado_o_sin_seccion'] = int((~d.SECCION.str.strip().str.isdigit()).sum())
    d = d[~d.TIPO_CASILLA.isin(['S', 'A', 'P']) & d.SECCION.str.strip().str.isdigit()].copy()
    d['sec'] = d.SECCION.astype(int)
    d['counted'] = d.CONTABILIZADA.str.strip() == '1'
    exp = d.groupby('sec').size()
    r['actas_seccionales'] = len(d)
    r['actas_no_contabilizadas'] = int((~d.counted).sum())
    d = d[d.counted]
    cols = sorted(set(PARTIES + sum(E['blocks'].values(), [])) | {'NULOS', 'NO_REGISTRADAS', 'TOTAL_VOTOS_CALCULADO', 'LISTA_NOMINAL'})
    cols = [c for c in cols if c in d.columns]
    for c in cols:
        d[c] = num(d[c])
    r['celdas_ilegibles_o_vacias'] = int(d[cols].isna().sum().sum())
    d[cols] = d[cols].fillna(0)
    g = d.groupby('sec')[cols].sum()
    g['actas'] = d.groupby('sec').size()
    g['esperadas'] = exp.reindex(g.index)
    # Validación
    over = g[g.TOTAL_VOTOS_CALCULADO > g.LISTA_NOMINAL * 1.0]
    r['secciones_votacion_mayor_LN'] = over.index.tolist()[:50]
    nocarto = [s for s in g.index if s not in idx]
    r['secciones_sin_cartografia'] = nocarto
    g = g[g.index.isin(idx.keys())]
    r['secciones_con_datos'] = len(g)
    r['secciones_cartografia_sin_datos'] = len(idx) - len(g)
    # Arreglos alineados al catálogo
    N = len(idx)
    def arr(series):
        a = [None] * N
        for s, v in series.items():
            a[idx[s]] = int(v)
        return a
    out = {'name': E['name'], 'short': E['short'], 'ambito': E['ambito'], 'note': E.get('note', ''),
           'ln': arr(g.LISTA_NOMINAL), 'total': arr(g.TOTAL_VOTOS_CALCULADO), 'nulos': arr(g.NULOS),
           'nr': arr(g.NO_REGISTRADAS), 'actas': arr(g.actas), 'esperadas': arr(g.esperadas),
           'blocks': {}, 'parties': {}}
    for b, members in E['blocks'].items():
        out['blocks'][b] = arr(g[[m for m in members if m in g.columns]].sum(axis=1))
    for p in PARTIES:
        if p in g.columns:
            out['parties'][p] = arr(g[p])
    # Cuadre interno: suma de componentes vs total calculado
    comp = sum(g[[m for m in mm if m in g.columns]].sum(axis=1) for mm in E['blocks'].values()) + g.NULOS + g.NO_REGISTRADAS
    extra = [c for c in g.columns if c.startswith('CI_') and not any(c in mm for mm in E['blocks'].values())]
    if extra:
        comp = comp + g[extra].sum(axis=1)
    diff = (comp - g.TOTAL_VOTOS_CALCULADO).abs()
    r['secciones_con_descuadre_componentes'] = int((diff > 0).sum())
    r['votos_totales'] = int(g.TOTAL_VOTOS_CALCULADO.sum())
    r['lista_nominal_contabilizada'] = int(g.LISTA_NOMINAL.sum())
    r['bloques_estatal'] = {b: int(sum(v for v in out['blocks'][b] if v)) for b in out['blocks']}
    elections_out[key] = out
    report['elecciones'][key] = r

# Nombres de cabecera distrital (tomados de las bases por casilla)
for key, field, idf in [('DF24', 'dfName', 'ID_DISTRITO_FEDERAL'), ('DL24', 'dlName', 'ID_DISTRITO_LOCAL')]:
    if key in ELECTIONS:
        d0 = load(os.path.join(RAW, ELECTIONS[key]['file']))
        name_col = idf.replace('ID_', '')
        catalog[field] = {str(int(k)): v.strip().title() for k, v in d0.groupby(idf)[name_col].first().items() if k.strip().isdigit()}
json.dump(catalog, open(f'{OUT}/catalogo.json', 'w'), separators=(',', ':'), ensure_ascii=False)
json.dump(elections_out, open(f'{OUT}/resultados.json', 'w'), separators=(',', ':'), ensure_ascii=False)
json.dump(report, open(f'{OUT}/reporte_calidad.json', 'w'), indent=1, ensure_ascii=False)

# Geometría: WGS84 para mapshaper
geo = sec[['seccion', 'geometry']].to_crs(4326)
geo.to_file(f'{OUT}/secciones_wgs84.geojson', driver='GeoJSON')
for layer, field in [('DISTRITO_FEDERAL', 'distrito_f'), ('DISTRITO_LOCAL', 'distrito_l'), ('MUNICIPIO', 'municipio')]:
    g2 = gpd.read_file(f'{C}/{layer}.shp')[[field, 'geometry']].to_crs(4326)
    g2.to_file(f'{OUT}/{layer.lower()}_wgs84.geojson', driver='GeoJSON')
print(json.dumps(report, indent=1, ensure_ascii=False))
