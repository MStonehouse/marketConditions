#!/usr/bin/env python3
from urllib.request import Request,urlopen
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import csv,io,json,math,statistics
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data'/'dashboard.json';FRED='https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}'
ECON={'M2SL':('Money & Liquidity','M2 money stock',15,'growth',24),'TOTBKCR':('Bank Credit','Total bank credit',10,'growth',9),'BUSLOANS':('Business Lending','Commercial & industrial loans',5,'growth',9),'CPATAX':('Corporate Health','Corporate profits after tax',15,'growth',65),'INDPRO':('Real Economic Activity','Industrial production',15,'growth',18),'PAYEMS':('Employment','Total nonfarm payrolls',10,'growth',8),'RSAFS':('Consumer Activity','Retail & food services sales',5,'growth',17),'DSPIC96':('Consumer Income','Real disposable personal income',5,'growth',32),'CPIAUCSL':('Inflation Environment','CPI inflation',10,'inflation',15),'DGORDER':('Business Investment','Durable goods new orders',5,'growth',28),'FEDFUNDS':('Monetary Policy','Effective federal funds rate',5,'policy',2)}
SENT={'VIXCLS':('Implied Volatility','CBOE VIX',30,'inverse'),'BAMLH0A0HYM2':('Risk Appetite','High-yield option-adjusted spread',25,'inverse'),'STLFSI4':('Financial Stress','St. Louis Fed Financial Stress Index',20,'inverse'),'SP500':('Market Momentum','S&P 500 short-term momentum',15,'momentum'),'NASDAQCOM':('Growth-Risk Appetite','NASDAQ short-term momentum',10,'momentum')}
def fetch(sid):
 raw=urlopen(Request(FRED.format(sid=sid),headers={'User-Agent':'MarketConditionsDashboard/1.0'}),timeout=30).read().decode('utf-8-sig');rd=csv.DictReader(io.StringIO(raw));col=[c for c in rd.fieldnames if c!='observation_date'][0];o=[]
 for r in rd:
  try:
   if r[col] and r[col]!='.':o.append((date.fromisoformat(r['observation_date']),float(r[col])))
  except:pass
 return sorted(o)
def last(rows,d):
 x=None
 for item in rows:
  if item[0]<=d:x=item
  else:break
 return x
def clamp(x,a,b):return max(a,min(b,x))
def logistic(z):return 100/(1+math.exp(-1.12*clamp(z,-4,4)))
def robust(v):
 v=[x for x in v if x is not None and math.isfinite(x)]
 if len(v)<8:return 0,1
 m=statistics.median(v);mad=statistics.median(abs(x-m) for x in v);return m,max(1.4826*mad,statistics.pstdev(v) or 1,1e-6)
def yoy(rows,item):
 if not item:return None
 p=last(rows,item[0]-timedelta(days=365));return None if not p or p[1]==0 else (item[1]/p[1]-1)*100
def econ_comp(sid,asof,rows):
 name,detail,w,kind,lag=ECON[sid];cur=last(rows,asof-timedelta(days=lag));prev=last(rows,asof-timedelta(days=lag+92))
 if not cur:return None
 if kind=='growth':
  g,pg=yoy(rows,cur),yoy(rows,prev);hist=[yoy(rows,i) for i in rows if asof-timedelta(days=3650)<=i[0]<=cur[0]];med,sc=robust(hist);level=logistic(((g if g is not None else med)-med)/max(sc,.25));acc=50 if g is None or pg is None else logistic((g-pg)/max(sc*.5,.35));score=.68*level+.32*acc;eps=max(sc*.12,.15);direction='→' if g is None or pg is None or abs(g-pg)<=eps else ('↑' if g>pg else '↓')
 elif kind=='inflation':
  g,pg=yoy(rows,cur),yoy(rows,prev)
  if g is None:return None
  dist=abs(g-2);level=100-clamp(dist/5*100,0,100);old=abs((pg if pg is not None else g)-2);score=.72*level+.28*logistic((old-dist)/.45);direction='↑' if dist<old-.08 else '↓' if dist>old+.08 else '→'
 else:
  rate=cur[1];pr=prev[1] if prev else rate;score=.7*logistic((2.5-rate)/1.8)+.3*logistic((pr-rate)/.65);direction='↑' if rate<pr-.1 else '↓' if rate>pr+.1 else '→'
 return {'name':name,'detail':detail,'weight':w,'score':round(clamp(score,0,100),1),'direction':direction}
def aggregate(asof,defs,series,compfn):
 parts=[];n=d=0
 for sid in defs:
  c=compfn(sid,asof,series[sid])
  if c:parts.append(c);n+=c['score']*c['weight'];d+=c['weight']
 return (n/d if d else None),parts
def sent_comp(sid,asof,rows):
 name,detail,w,kind=SENT[sid];cur=last(rows,asof)
 if not cur:return None
 if kind=='momentum':
  p21=last(rows,asof-timedelta(days=30));p5=last(rows,asof-timedelta(days=7))
  if not p21:return None
  r21=(cur[1]/p21[1]-1)*100;r5=(cur[1]/p5[1]-1)*100 if p5 else r21;score=logistic((.7*r21+.3*r5)/4);direction='↑' if r5>1 else '↓' if r5<-1 else '→'
 else:
  vals=[v for d,v in rows if asof-timedelta(days=3650)<=d<=asof];med,sc=robust(vals);score=100-logistic((cur[1]-med)/max(sc,.01));p=last(rows,asof-timedelta(days=30));delta=0 if not p else cur[1]-p[1];eps=max(sc*.08,.02);direction='↑' if delta<-eps else '↓' if delta>eps else '→'
 return {'name':name,'detail':detail,'weight':w,'score':round(clamp(score,0,100),1),'direction':direction}
def eclass(x):
 return 'Exceptional' if x>=80 else 'Favorable' if x>=65 else 'Moderately Favorable' if x>=55 else 'Neutral' if x>=45 else 'Moderately Unfavorable' if x>=35 else 'Unfavorable' if x>=20 else 'Severe'
def direc(a,b,eps=1.5):return '↑' if a>b+eps else '↓' if a<b-eps else '→'
def main():
 ids=set(ECON)|set(SENT);series={s:fetch(s) for s in ids};today=date.today();start=today-timedelta(days=int(365.25*10));hist=[];d=start
 while d<=today:
  if d.weekday()<5:
   e,_=aggregate(d,ECON,series,econ_comp);s,_=aggregate(d,SENT,series,sent_comp);sp=last(series['SP500'],d)
   if e is not None and s is not None:hist.append({'date':d.isoformat(),'economic':round(e,1),'sentiment':round(s,1),'sp500':None if not sp else round(sp[1],2)})
  d+=timedelta(days=1)
 e,ep=aggregate(today,ECON,series,econ_comp);e3,_=aggregate(today-timedelta(days=92),ECON,series,econ_comp);s,sparts=aggregate(today,SENT,series,sent_comp);s1,_=aggregate(today-timedelta(days=30),SENT,series,sent_comp);sp=last(series['SP500'],today);sp1=last(series['SP500'],today-timedelta(days=30));chg=None if not sp or not sp1 else (sp[1]/sp1[1]-1)*100
 payload={'generated_at':datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),'current':{'economic':{'score':round(e,1),'classification':eclass(e),'direction':direc(e,e3),'change_3m':round(e-e3,1),'components':ep},'sentiment':{'score':round(s,1),'direction':direc(s,s1),'change_1m':round(s-s1,1),'components':sparts},'sp500':{'value':None if not sp else round(sp[1],2),'change_1m':None if chg is None else round(chg,2)}},'history':hist,'meta':{'history_years':10,'economic_model_uses_market_data':False,'sentiment_model_is_separate':True,'sp500_is_display_only':True}}
 OUT.write_text(json.dumps(payload,separators=(',',':')));print('Wrote',OUT,len(hist),'rows')
if __name__=='__main__':main()
