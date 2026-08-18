"""Parse Valais romand 'plan de scolarite' PDFs via colored vector rects.
blue/yellow fill = school day ; orange fill = jour ferie cantonal ;
white (no fill) weekday during term = vacances/conge scolaire.
Returns a per-date classification DataFrame."""
import pdfplumber, pandas as pd
from datetime import date

MONTHS=["AOÛT","SEPTEMBRE","OCTOBRE","NOVEMBRE","DECEMBRE","JANVIER","FEVRIER","MARS","AVRIL","MAI","JUIN"]
MONTH_NUM={"AOÛT":8,"SEPTEMBRE":9,"OCTOBRE":10,"NOVEMBRE":11,"DECEMBRE":12,"JANVIER":1,"FEVRIER":2,"MARS":3,"AVRIL":4,"MAI":5,"JUIN":6}
BLUE=(0.0,0.439,0.753); YELLOW=(1.0,1.0,0.0); ORANGE=(0.886,0.42,0.0392)
def cls(c):
    if c is None: return None
    if not isinstance(c,(list,tuple)) or len(c)!=3: return None
    r,g,b=c
    def near(a,b): return abs(a[0]-b[0])<0.06 and abs(a[1]-b[1])<0.06 and abs(a[2]-b[2])<0.06
    if near((r,g,b),BLUE): return "blue"
    if near((r,g,b),YELLOW): return "yellow"
    if near((r,g,b),ORANGE): return "orange"
    return None

def parse_page(p, year1, year2):
    words=p.extract_words()
    headers=[w for w in words if w['text'] in MONTHS]
    # band tops (unique header tops)
    band_tops=sorted({round(w['top'],0) for w in headers})
    # month center per (band_top, x)
    month_anchors=[]  # (top, xcenter, monthname)
    for w in headers:
        month_anchors.append((round(w['top'],0),(w['x0']+w['x1'])/2,w['text']))
    # weekday row centers per band
    wd=[w for w in words if w['text'] in ["Lu","Ma","Me","Je","Ve","Sa","Di"]]
    rows_by_band={}
    for bt in band_tops:
        band_rows=[(w['text'],(w['top']+w['bottom'])/2) for w in wd if bt < w['top'] < bt+120]
        rows_by_band[bt]=band_rows
    rects=[r for r in p.rects if cls(r.get('non_stroking_color'))]
    def color_at(cx,cy):
        for r in rects:
            if r['x0']-1<=cx<=r['x0']+r['width']+1 and r['top']-1<=cy<=r['top']+r['height']+1:
                return cls(r['non_stroking_color'])
        return None
    import calendar as _cal
    WD=["Lu","Ma","Me","Je","Ve","Sa","Di"]
    # 1) collect digit cells with (month, row_label, x) — IGNORING printed value (robust to source typos)
    cells=[]
    for w in words:
        t=w['text']
        if not t.isdigit(): continue
        if not (1<=int(t)<=31): continue
        cx=(w['x0']+w['x1'])/2; cy=(w['top']+w['bottom'])/2
        bt=None
        for b in band_tops:
            if b+8 < w['top'] < b+120: bt=b;break
        if bt is None: continue
        cand=sorted([(abs(xc-cx),mn) for (bb,xc,mn) in month_anchors if bb==bt])
        if not cand or cand[0][0]>70: continue
        month=cand[0][1]
        wdname,wdcenter=min(rows_by_band[bt],key=lambda r:abs(r[1]-cy))
        if abs(cy-wdcenter)>6.5: continue  # drop footer '* total' numbers below the Di row
        cells.append({"month":month,"row":wdname,"cx":cx,"cy":cy,"printed":int(t)})
    # 2) per (month,row) sort by x and map to the k-th occurrence of that weekday in the month
    out=[]; warnings=[]
    for month in MONTH_NUM:
        mnum=MONTH_NUM[month]; yr=year1 if mnum>=8 else year2
        for ri,wd in enumerate(WD):
            row=sorted([c for c in cells if c["month"]==month and c["row"]==wd],key=lambda c:c["cx"])
            # calendar dates for this weekday in the month
            ndays=_cal.monthrange(yr,mnum)[1]
            occ=[d for d in range(1,ndays+1) if date(yr,mnum,d).weekday()==ri]
            if len(row)!=len(occ):
                warnings.append(f"{yr}-{mnum:02d} {wd}: {len(row)} cells vs {len(occ)} expected")
            for cell,d in zip(row,occ):
                dt=date(yr,mnum,d)
                out.append({"date":dt,"day":d,"month":month,"row_label":wd,
                            "true_wd":WD[dt.weekday()],"printed":cell["printed"],
                            "color":color_at(cell["cx"],cell["cy"])})
    df=pd.DataFrame(out).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    df.attrs["warnings"]=warnings
    return df

if __name__=="__main__":
    import sys
    f="data/external/vacances_scolaires_valais/DEF-PlanDeScolarite2021-2022.pdf"
    with pdfplumber.open(f) as doc:
        df=parse_page(doc.pages[0],2021,2022)
    # sanity: row_label vs true_wd mismatches
    mm=df[df.row_label!=df.true_wd]
    print("row/weekday mismatches:",len(mm))
    if len(mm): print(mm.head(20).to_string())
    print("n days parsed:",len(df), df.date.min(),"->",df.date.max())
    # orange = feries
    print("\nORANGE (feries) dates:")
    print(df[df.color=='orange'].date.tolist())
    # weekday white (vacances/conge): weekday Mon-Fri, color None
    wk=df[(df.true_wd.isin(["Lu","Ma","Me","Je","Ve"]))]
    print("\nWhite weekday (conge/vacances) dates:")
    print(wk[wk.color.isna()].date.tolist())
