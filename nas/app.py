#!/usr/bin/env python3
import json, os, sqlite3, subprocess, sys, threading, time
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, urlsplit

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.getenv("TVBOX_DATA","/data"))
OUTPUT=Path(os.getenv("TVBOX_OUTPUT","/output"))
CONFIG=Path(os.getenv("TVBOX_CONFIG","/config"))
LOGS=Path(os.getenv("TVBOX_LOGS","/logs"))
PORT=int(os.getenv("TVBOX_PORT","8080"))
INTERVAL=int(os.getenv("TVBOX_INTERVAL_HOURS","12"))*3600
AUTO_RUN=os.getenv("TVBOX_AUTO_RUN","1").lower() not in ("0","false","no")
DB=DATA/"nas.db"
UPSTREAM_CFG=CONFIG/"upstreams.json"
RUN_LOCK=threading.Lock()

for p in (DATA,OUTPUT,CONFIG,LOGS): p.mkdir(parents=True,exist_ok=True)

def ensure_persistent_state():
    target=DATA/"state"; target.mkdir(parents=True,exist_ok=True)
    state=ROOT/"state"
    if state.is_symlink():
        return
    # First boot: preserve shipped seed state, then replace /app/state with a symlink.
    if state.exists():
        for src in state.iterdir():
            dst=target/src.name
            if src.is_file() and not dst.exists():
                dst.write_bytes(src.read_bytes())
        import shutil
        shutil.rmtree(state)
    state.symlink_to(target, target_is_directory=True)

ensure_persistent_state()

def db():
    c=sqlite3.connect(DB)
    c.execute("""create table if not exists runs(id integer primary key, started text, finished text, ok integer, message text)""")
    c.execute("""create table if not exists upstreams(id integer primary key, url text unique, name text, enabled integer default 1, source text default 'manual', created text)""")
    c.commit(); return c

def valid_url(v):
    try:
        u=urlparse(v); return u.scheme in ("http","https") and bool(u.netloc)
    except Exception: return False

def _upstream_doc():
    try:
        d=json.loads(UPSTREAM_CFG.read_text(encoding="utf-8"))
        if isinstance(d,dict) and isinstance(d.get("upstreams"),list): return d
    except (OSError,ValueError): pass
    # Seed from repository config on first boot.
    seed=ROOT/"config"/"upstreams.json"
    try:
        d=json.loads(seed.read_text(encoding="utf-8"))
        if isinstance(d,dict) and isinstance(d.get("upstreams"),list): return d
    except (OSError,ValueError): pass
    return {"version":1,"upstreams":[]}

def _save_upstream_doc(d):
    tmp=UPSTREAM_CFG.with_suffix(".tmp")
    tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(UPSTREAM_CFG)

def add_upstream(url,name="",source="manual"):
    if not valid_url(url): raise ValueError("invalid http/https URL")
    d=_upstream_doc()
    if any(x.get("url")==url for x in d["upstreams"]): return
    stamp=datetime.now(timezone.utc).date().isoformat()
    d["upstreams"].append({"name":name or ("nas-"+str(len(d["upstreams"])+1)),"url":url,"type":"vod","priority":50,"enabled":True,"added_at":stamp,"source":source,"format":"json"})
    _save_upstream_doc(d)

def upstreams():
    return [{"id":i+1,"url":x.get("url"),"name":x.get("name"),"enabled":x.get("enabled",True),"source":x.get("source","seed")}
            for i,x in enumerate(_upstream_doc().get("upstreams",[])) if x.get("url")]

CURRENT={"step":"","log":""}

def latest_log_tail(lines=120):
    logs=sorted(LOGS.glob("run_*.log"),reverse=True)
    if not logs: return ""
    try:
        return "\n".join(logs[0].read_text(encoding="utf-8",errors="replace").splitlines()[-lines:])
    except OSError: return ""

def run_pipeline():
    if not RUN_LOCK.acquire(blocking=False): return False,"already running"
    started=datetime.now(timezone.utc).isoformat(); ok=False; msg=""
    try:
        env=os.environ.copy()
        env["TVBOX_NAS_MODE"]="1"
        env["LIVE_SPEEDTEST"]="0"
        env["UPSTREAM_CONFIG"]=str(UPSTREAM_CFG)
        # Point the upstream module at the persistent NAS copy.
        d=_upstream_doc(); _save_upstream_doc(d)
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
        CURRENT["log"]=log.name
        with log.open("w",encoding="utf-8") as f:
            for cmd in cmds:
                CURRENT["step"]=" ".join(cmd[1:3])
                f.write("\n===== "+CURRENT["step"]+" =====\n"); f.flush()
                p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=3600)
                if p.returncode and cmd[1].endswith("fetch_merge.py"):
                    f.flush()
                    tail=latest_log_tail(30).replace("\n"," | ")
                    raise RuntimeError(f"fetch_merge failed (exit {p.returncode}): {tail[-1800:]}")
        healthy=ROOT/"exports"/"healthy.json"
        if not healthy.exists():
            raise RuntimeError("healthy export missing")
        # Public subscription is always the validated/ranked VOD result.
        payload=healthy.read_bytes()
        (OUTPUT/"tvbox.json").write_bytes(payload)
        (OUTPUT/"healthy.json").write_bytes(payload)
        raw=ROOT/"tvbox.json"
        if raw.exists(): (OUTPUT/"tvbox_all.json").write_bytes(raw.read_bytes())
        ok=True; msg="completed"
    except Exception as e: msg=str(e)
    finally:
        finished=datetime.now(timezone.utc).isoformat()
        with db() as c: c.execute("insert into runs(started,finished,ok,message) values(?,?,?,?)",(started,finished,int(ok),msg))
        CURRENT["step"]=""
        RUN_LOCK.release()
    return ok,msg

def scheduler():
    # Give DSM time to expose the Web UI before the first heavy maintenance pass.
    if not AUTO_RUN: return
    time.sleep(int(os.getenv("TVBOX_FIRST_RUN_DELAY","120")))
    while True:
        run_pipeline(); time.sleep(max(INTERVAL,3600))

class H(SimpleHTTPRequestHandler):
    def _json(self,obj,status=200):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        path=urlsplit(self.path).path.rstrip("/") or "/"
        if path=="/api/status":
            with db() as c:
                r=c.execute("select started,finished,ok,message from runs order by id desc limit 1").fetchone()
            return self._json({"running":RUN_LOCK.locked(),"step":CURRENT["step"],"log":CURRENT["log"],"last_run":dict(zip(("started","finished","ok","message"),r)) if r else None,"upstreams":len(upstreams())})
        if path=="/api/upstreams": return self._json(upstreams())
        if path=="/api/log": return self._json({"text":latest_log_tail()})
        if path in ("/","/index.html"):
            p=ROOT/"nas"/"index.html"; b=p.read_bytes(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); return self.wfile.write(b)
        if path=="/favicon.ico":
            self.send_response(204); self.end_headers(); return
        name=path.lstrip("/")
        if name in ("tvbox.json","healthy.json","tvbox_all.json"):
            p=OUTPUT/name
            if p.exists():
                b=p.read_bytes(); self.send_response(200); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.end_headers(); return self.wfile.write(b)
        self.send_error(404)
    def do_POST(self):
        path=urlsplit(self.path).path.rstrip("/") or "/"
        n=int(self.headers.get("Content-Length","0")); body=json.loads(self.rfile.read(n) or b"{}")
        if path=="/api/upstreams":
            try: add_upstream(body.get("url",""),body.get("name","")); return self._json({"ok":True})
            except Exception as e: return self._json({"ok":False,"error":str(e)},400)
        if path=="/api/run":
            threading.Thread(target=run_pipeline,daemon=True).start(); return self._json({"ok":True})
        self.send_error(404)
    def log_message(self,fmt,*args): print("[web]",fmt%args,flush=True)

if __name__=="__main__":
    db().close()
    threading.Thread(target=scheduler,daemon=True).start()
    print(f"TVBox NAS manager listening on :{PORT}",flush=True)
    ThreadingHTTPServer(("0.0.0.0",PORT),H).serve_forever()
