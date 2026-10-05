#!/usr/bin/env python3
import json, os, sqlite3, subprocess, sys, threading, time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.getenv("TVBOX_DATA","/data"))
OUTPUT=Path(os.getenv("TVBOX_OUTPUT","/output"))
CONFIG=Path(os.getenv("TVBOX_CONFIG","/config"))
LOGS=Path(os.getenv("TVBOX_LOGS","/logs"))
PORT=int(os.getenv("TVBOX_PORT","8080"))
INTERVAL=int(os.getenv("TVBOX_INTERVAL_HOURS","12"))*3600
DB=DATA/"nas.db"
RUN_LOCK=threading.Lock()

for p in (DATA,OUTPUT,CONFIG,LOGS): p.mkdir(parents=True,exist_ok=True)

def db():
    c=sqlite3.connect(DB)
    c.execute("""create table if not exists runs(id integer primary key, started text, finished text, ok integer, message text)""")
    c.execute("""create table if not exists upstreams(id integer primary key, url text unique, name text, enabled integer default 1, source text default 'manual', created text)""")
    c.commit(); return c

def valid_url(v):
    try:
        u=urlparse(v); return u.scheme in ("http","https") and bool(u.netloc)
    except Exception: return False

def add_upstream(url,name="",source="manual"):
    if not valid_url(url): raise ValueError("invalid http/https URL")
    with db() as c:
        c.execute("insert or ignore into upstreams(url,name,source,created) values(?,?,?,?)",
                  (url,name or url,source,datetime.now(timezone.utc).isoformat()))

def upstreams():
    with db() as c:
        return [{"id":r[0],"url":r[1],"name":r[2],"enabled":bool(r[3]),"source":r[4]}
                for r in c.execute("select id,url,name,enabled,source from upstreams order by id desc")]

def run_pipeline():
    if not RUN_LOCK.acquire(blocking=False): return False,"already running"
    started=datetime.now(timezone.utc).isoformat(); ok=False; msg=""
    try:
        env=os.environ.copy()
        manual=[x["url"] for x in upstreams() if x["enabled"]]
        if manual: env["NAS_EXTRA_UPSTREAMS"]="\n".join(manual)
        cmds=[
          [sys.executable,"scripts/mirror_probe.py"],
          [sys.executable,"scripts/discover_upstreams.py","--pages","1"],
          [sys.executable,"scripts/evaluate_candidates.py","--min-unique","3","--write-canary"],
          [sys.executable,"scripts/fetch_merge.py"],
          [sys.executable,"scripts/probe_sites.py","--only","http","--concurrency","16"],
          [sys.executable,"nas/media_quality.py","--batch","probe/sites_probe.json"],
          [sys.executable,"scripts/dedup_mirrors.py"],
          [sys.executable,"scripts/drpy_probe.py","--workers","3"],
          [sys.executable,"scripts/store.py","--ingest-sites","tvbox.json","--ingest-probes","probe/sites_probe.json","probe/drpy_probe.json","--prune","--stats"],
          [sys.executable,"scripts/export_healthy.py"],
        ]
        log=LOGS/("run_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".log")
        with log.open("w",encoding="utf-8") as f:
            for cmd in cmds:
                p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=3600)
                if p.returncode and cmd[1].endswith("fetch_merge.py"):
                    raise RuntimeError("fetch_merge failed")
        for src in ("tvbox.json","tvbox_recommended.json"):
            p=ROOT/src
            if p.exists(): (OUTPUT/src).write_bytes(p.read_bytes())
        healthy=ROOT/"exports"/"healthy.json"
        if healthy.exists(): (OUTPUT/"healthy.json").write_bytes(healthy.read_bytes())
        ok=True; msg="completed"
    except Exception as e: msg=str(e)
    finally:
        finished=datetime.now(timezone.utc).isoformat()
        with db() as c: c.execute("insert into runs(started,finished,ok,message) values(?,?,?,?)",(started,finished,int(ok),msg))
        RUN_LOCK.release()
    return ok,msg

def scheduler():
    time.sleep(15)
    while True:
        run_pipeline(); time.sleep(max(INTERVAL,3600))

class H(SimpleHTTPRequestHandler):
    def _json(self,obj,status=200):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path=="/api/status":
            with db() as c:
                r=c.execute("select started,finished,ok,message from runs order by id desc limit 1").fetchone()
            return self._json({"running":RUN_LOCK.locked(),"last_run":dict(zip(("started","finished","ok","message"),r)) if r else None,"upstreams":len(upstreams())})
        if self.path=="/api/upstreams": return self._json(upstreams())
        if self.path in ("/","/index.html"):
            p=ROOT/"nas"/"index.html"; b=p.read_bytes(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); return self.wfile.write(b)
        name=self.path.lstrip("/")
        if name in ("tvbox.json","tvbox_recommended.json","healthy.json"):
            p=OUTPUT/name
            if p.exists():
                b=p.read_bytes(); self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); return self.wfile.write(b)
        self.send_error(404)
    def do_POST(self):
        n=int(self.headers.get("Content-Length","0")); body=json.loads(self.rfile.read(n) or b"{}")
        if self.path=="/api/upstreams":
            try: add_upstream(body.get("url",""),body.get("name","")); return self._json({"ok":True})
            except Exception as e: return self._json({"ok":False,"error":str(e)},400)
        if self.path=="/api/run":
            threading.Thread(target=run_pipeline,daemon=True).start(); return self._json({"ok":True})
        self.send_error(404)
    def log_message(self,fmt,*args): print("[web]",fmt%args,flush=True)

if __name__=="__main__":
    db().close()
    threading.Thread(target=scheduler,daemon=True).start()
    print(f"TVBox NAS manager listening on :{PORT}",flush=True)
    ThreadingHTTPServer(("0.0.0.0",PORT),H).serve_forever()
