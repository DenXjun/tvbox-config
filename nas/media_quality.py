#!/usr/bin/env python3
"""NAS VOD quality history: bounded media sampling + 7/30 day stability scoring."""
import json, os, sqlite3, time, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA=Path(os.getenv("TVBOX_DATA","/data")); DB=DATA/"nas.db"
UA={"User-Agent":"Mozilla/5.0","Range":"bytes=0-524287"}
TIMEOUT=int(os.getenv("MEDIA_PROBE_TIMEOUT","10"))
MAX_BYTES=int(os.getenv("MEDIA_PROBE_BYTES","524288"))

def init(c):
    c.execute("""create table if not exists media_checks(
      id integer primary key, site_key text, url text, checked text,
      ok integer, first_byte_ms integer, bytes integer, kbps real, error text)""")
    c.execute("create index if not exists ix_media_site_time on media_checks(site_key,checked)")
    c.commit()

def probe(url):
    t=time.time(); first=None; total=0
    try:
        req=urllib.request.Request(url,headers=UA)
        with urllib.request.urlopen(req,timeout=TIMEOUT) as r:
            while total<MAX_BYTES:
                b=r.read(min(65536,MAX_BYTES-total))
                if not b: break
                if first is None: first=int((time.time()-t)*1000)
                total+=len(b)
        elapsed=max(time.time()-t,.001)
        return {"ok":total>0,"first_byte_ms":first or int(elapsed*1000),"bytes":total,"kbps":round(total/1024/elapsed,1),"error":""}
    except Exception as e:
        return {"ok":False,"first_byte_ms":None,"bytes":total,"kbps":0,"error":str(e)[:240]}

def record(site_key,url):
    r=probe(url); now=datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB) as c:
        init(c); c.execute("insert into media_checks(site_key,url,checked,ok,first_byte_ms,bytes,kbps,error) values(?,?,?,?,?,?,?,?)",
          (site_key,url,now,int(r["ok"]),r["first_byte_ms"],r["bytes"],r["kbps"],r["error"]))
    return r

def stats(site_key):
    now=datetime.now(timezone.utc)
    with sqlite3.connect(DB) as c:
        init(c); rows=c.execute("select checked,ok,first_byte_ms,kbps from media_checks where site_key=? and checked>=? order by checked desc",
          (site_key,(now-timedelta(days=30)).isoformat())).fetchall()
    def win(days):
        cut=now-timedelta(days=days); x=[r for r in rows if datetime.fromisoformat(r[0])>=cut]
        if not x:return {"samples":0,"success_rate":None,"avg_kbps":None,"avg_first_byte_ms":None}
        good=[r for r in x if r[1]]
        return {"samples":len(x),"success_rate":round(len(good)/len(x),3),
          "avg_kbps":round(sum(r[3] or 0 for r in good)/len(good),1) if good else 0,
          "avg_first_byte_ms":round(sum(r[2] or 0 for r in good)/len(good)) if good else None}
    return {"d7":win(7),"d30":win(30)}

def score(site_key):
    s=stats(site_key); w=s["d7"] if s["d7"]["samples"]>=3 else s["d30"]
    if not w["samples"]: return None
    stability=(w["success_rate"] or 0)*70
    speed=min((w["avg_kbps"] or 0)/2048,1)*20
    latency=max(0,1-min((w["avg_first_byte_ms"] or 5000)/5000,1))*10
    return round(stability+speed+latency,1)

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("site_key"); ap.add_argument("url"); a=ap.parse_args()
    r=record(a.site_key,a.url); print(json.dumps({"probe":r,"history":stats(a.site_key),"score":score(a.site_key)},ensure_ascii=False))


def ingest_probe_file(path, limit=40):
    """Sample L3 media URLs from sites_probe.json. Bounded to protect NAS/network."""
    p=Path(path)
    if not p.exists(): return {"tested":0,"ok":0}
    doc=json.loads(p.read_text(encoding="utf-8"))
    candidates=[]
    for x in doc.get("sites") or []:
        l3=x.get("l3") or {}; u=l3.get("play_url")
        if x.get("level")=="L3" and l3.get("ok") and isinstance(u,str) and u.startswith(("http://","https://")):
            candidates.append((x.get("key") or x.get("name") or u,u))
    # Stable bounded rotation by day so large pools are covered over time.
    if candidates:
        off=(datetime.now(timezone.utc).toordinal()*max(limit,1))%len(candidates)
        candidates=(candidates[off:]+candidates[:off])[:limit]
    good=0
    for key,u in candidates:
        if record(str(key),u)["ok"]: good+=1
    return {"tested":len(candidates),"ok":good}

def export_scores(path):
    with sqlite3.connect(DB) as c:
        init(c); keys=[r[0] for r in c.execute("select distinct site_key from media_checks")]
    out={k:{"score":score(k),**stats(k)} for k in keys}
    Path(path).write_text(json.dumps({"generated_at":datetime.now(timezone.utc).isoformat(),"items":out},ensure_ascii=False,indent=2),encoding="utf-8")
    return out
