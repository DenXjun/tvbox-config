import importlib.util, tempfile, os
from pathlib import Path

def load(tmp):
    os.environ["TVBOX_DATA"]=str(tmp)
    spec=importlib.util.spec_from_file_location("mq","nas/media_quality.py")
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_empty_history(tmp_path):
    m=load(tmp_path); assert m.score("missing") is None
    s=m.stats("missing"); assert s["d7"]["samples"]==0

def test_score_formula(tmp_path):
    m=load(tmp_path)
    import sqlite3
    from datetime import datetime, timezone
    with sqlite3.connect(m.DB) as c:
        m.init(c)
        now=datetime.now(timezone.utc).isoformat()
        for _ in range(3):
            c.execute("insert into media_checks(site_key,url,checked,ok,first_byte_ms,bytes,kbps,error) values(?,?,?,?,?,?,?,?)",("a","u",now,1,500,1000,4096,""))
        c.commit()
    assert m.score("a") >= 95


def test_batch_ingests_l3_only(tmp_path, monkeypatch):
    m=load(tmp_path)
    probe=tmp_path/"probe.json"
    probe.write_text(__import__("json").dumps({"sites":[
      {"key":"good","level":"L3","l3":{"ok":True,"play_url":"https://example.invalid/a.m3u8"}},
      {"key":"weak","level":"L2","l3":{"ok":False,"play_url":"https://example.invalid/b.m3u8"}}]}),encoding="utf-8")
    monkeypatch.setattr(m,"record",lambda k,u:{"ok":True})
    r=m.ingest_probe_file(probe,40)
    assert r=={"tested":1,"ok":1}


def test_hls_probe_fetches_media_segment(tmp_path, monkeypatch):
    m=load(tmp_path)
    calls=[]
    def fake_download(url, limit):
        calls.append(url)
        if url.endswith("master.m3u8"):
            return (b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nsub/index.m3u8\n", 10, 0.01, "application/vnd.apple.mpegurl", url)
        if url.endswith("sub/index.m3u8"):
            return (b"#EXTM3U\n#EXTINF:4,\nseg0001.ts\n", 12, 0.01, "application/vnd.apple.mpegurl", url)
        return (b"x"*4096, 20, 0.02, "video/mp2t", url)
    monkeypatch.setattr(m,"_download",fake_download)
    r=m.probe("https://media.example/master.m3u8")
    assert r["ok"] is True
    assert r["bytes"]==4096
    assert calls==[
      "https://media.example/master.m3u8",
      "https://media.example/sub/index.m3u8",
      "https://media.example/sub/seg0001.ts",
    ]


def test_hls_playlist_without_segment_fails(tmp_path, monkeypatch):
    m=load(tmp_path)
    monkeypatch.setattr(m,"_download",lambda url,limit:(b"#EXTM3U\n#EXT-X-ENDLIST\n",5,0.01,"application/vnd.apple.mpegurl",url))
    r=m.probe("https://media.example/empty.m3u8")
    assert r["ok"] is False
    assert "no media URI" in r["error"]
