import importlib.util, os

def load():
    spec=importlib.util.spec_from_file_location("export_healthy","scripts/export_healthy.py")
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_nas_filters_to_http_cms_and_strips_adult_categories(monkeypatch):
    m=load(); monkeypatch.setenv("TVBOX_NAS_MODE","1")
    sites=[
      {"key":"cms","name":"正常影视","type":1,"api":"https://a.example/api","categories":["电影","擦边短剧"],"_health":"healthy","_level":"L3"},
      {"key":"drpy","name":"斗鱼直播","type":3,"api":"./deps/drpy2.min.js","ext":"./deps/live.js","_health":"healthy","_level":"D5"},
      {"key":"adult","name":"成人影视","type":1,"api":"https://adult.example/api","_health":"healthy","_level":"L3"},
    ]
    out=m._nas_filter_and_rank(sites,{})
    assert [s["key"] for s in out]==["cms"]
    assert out[0]["categories"]==["电影"]

def test_nas_build_doc_is_compatibility_first(monkeypatch):
    m=load(); monkeypatch.setenv("TVBOX_NAS_MODE","1")
    base={
      "spider":"./deps/spider.jar;md5;abc",
      "parses":[{"name":"x","type":0,"url":"https://jx.example/?url="}],
      "lives":[{"name":"live","url":"https://live.example"}],
      "wallpaper":"https://img.example/a.jpg",
      "version":"v1",
      "updated_at":"now",
      "sites":[],
    }
    sites=[{"key":"cms","name":"CMS","type":1,"api":"https://a.example/api","_health":"healthy","_source":"x"}]
    doc=m.build_doc(base,sites)
    assert set(doc)=={"wallpaper","version","updated_at","sites"}
    assert doc["sites"]==[{"key":"cms","name":"CMS","type":1,"api":"https://a.example/api"}]
    assert "spider" not in doc and "parses" not in doc and "lives" not in doc
