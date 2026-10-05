# -*- coding: utf-8 -*-
"""fetch_merge 只读配置常量（阶段1 自动抽取）。

只含纯字面量 / 常量容器：无函数调用、不引用项目函数或可变全局、依赖闭包自洽。
fetch_merge.py 通过 `from fm_config import *` 引入，行为等价。
可变运行时状态（UPSTREAMS 等 7 个 global 重绑定）刻意留在 fetch_merge.py。
"""

UA = {"User-Agent": "okhttp/3.15", "Accept": "*/*"}

FETCH_TIMEOUT = 15          # 单次拉取超时（秒，旧合并超时，保留兼容）

UA_POOL_VOD = [
    {"User-Agent": "okhttp/3.15", "X-Requested-With": "com.iptvbox.tvbox"},
    {"User-Agent": "okhttp/4.9.3", "X-Requested-With": "com.iptvbox.tvbox"},
    {"User-Agent": "TVBox/1.0.0", "X-Requested-With": "com.github.tvbox.osc"},
    {"User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; Pixel 3 XL Build/SQ1A.220205.002)", "X-Requested-With": "com.iptvbox.tvbox"},
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", "X-Requested-With": ""},
    {"User-Agent": "okhttp/3.12.0", "X-Requested-With": "com.box.tvbox"},
]

TEST_TIMEOUT = 6            # 站点验活单次超时（秒）

MAX_BODY = 4096             # 验活最多读取字节数

GH_MIRRORS_DEFAULT = (
    "https://gh.halonice.com/,https://30006000.xyz/,https://githubproxy.cc/,"
    "https://proxy.vvvv.ee/,https://gh.padao.fun/,https://github.cnxiaobai.com/,"
    "https://fastgit.cc/,https://gh.zwy.one/,https://ghproxy.cxkpro.top/,"
    "https://v6.gh-proxy.org/,https://gh-proxy.com/,https://ghproxy.net/,"
    "https://gh.acmsz.top/"
)

REPO_RAW = "https://raw.githubusercontent.com/hebijunge/tvbox-config/main"

SHORT_KEYWORDS = [
    "短剧", "微短剧", "短剧场",   # 中文
    "duanju", "duanjucat", "duanjumao", "shortplay", "short_play",  # 拼音/英文
    "七猫", "河马", "围观", "好看", "星芽", "果果", "红果", "黄果", "黄豆",
    "锦鲤", "偷乐", "上头", "聚合短剧",
]

ADULT_LIVE_SOURCES = [
    # fish2018/lib 成人直播/成人影片（每个都在 sandbox 实测过 http 200 + 至少一条流抽样通过）
    ("18+合集",   "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/18+.txt",        10679),
    ("live18",     "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/live18.txt",    8917),
    ("pron",       "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/pron.m3u",         64),
    ("国产传媒",   "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/几个传媒.txt",   3331),
    ("成人传媒",   "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/成人传媒.txt",   2980),
    ("成人电影",   "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/成人电影.txt",  14873),
    ("18资源丰富", "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/18资源丰富.txt", 5564),
    ("花活",       "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/花活.txt",        2540),
    ("天美传媒816", "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/天美传媒816.txt", 23),
    ("果冻传媒816", "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/果冻传媒816.txt", 63),
    ("精东影业816", "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/精东影业816.txt", 24),
    ("麻豆传媒816", "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/麻豆传媒816.txt", 12),
    ("星空传媒816", "https://ghproxy.net/https://raw.githubusercontent.com/fish2018/lib/main/txt/星空传媒816.txt", 46),
]

ADULT_KEYWORDS = [
    # 明确成人/色情关键词（收紧：去除通用资源站误匹配）
    "成人", "18+", "porn", "麻豆", "果冻", "天美", "精东", "色播", "传媒",
    "花活", "丝袜", "美腿", "hsck", "jav", "1024", "91porn", "91md", "91panta", "91splt", "91bobo", "91精品",
    "色花糖", "朱古力", "Missav", "missav",
    # 注：2026-09-26 用户裁定「玩偶」移出成人词表——玩偶(wogg)系 4K 网盘影视站，
    # 非成人站；此前因 feishu-sync 上游含真成人站被上游投票连带误收进 adult.json。
    "Xojav", "JavBus", "JavDb", "涩涩", "Websites",
    # 扩张：常见成人站点标志词
    "xvideos", "pornhub", "xhamster", "hdsemj", "tokyo-hot",
    # 限定形容词（"敏感词"语义强）— 仅作为最后防线
    "裸聊", "裸播", "黄播", "黄网", "瑟瑟情",
    # 2026-09-21 点播+容错线：高置信词 ×10 增量（来源：实读 ccAzy separate_sources.py
    # 词表后人工挑选，走本表关键词匹配而非其删除式过滤；均为社区普遍使用的成人
    # 站名/黑话，误匹配风险低）
    "探花", "蜜桃", "糖心", "海角", "含羞草", "草榴", "秋霞", "番号", "无码", "里番",
]

STRONG_ADULT_TOKENS = [
    # 上游/官方标记
    "🔞",
    # 国际化成人平台（品牌词，零误匹配风险）
    "pornhub", "xvideos", "xhamster", "tokyo-hot",
    "javbus", "javdb", "xojav", "missav",
    "91porn", "91md", "hdsemj",
    # 明确成人 api 域名（社区共识的成人 CMS 后端）
    "souavzy", "pgxdy", "dadiapi", "lbapi9", "xrbsp", "jcspcj8",
    "caiji25", "sdszyapi", "hsck",
    # 明确站点标志词（带数字/连字符变体）
    "18av", "4kav", "4k-av", "cableav", "netflav", "owoav", "souav", "黄av",
    # 明确中文成人站点品牌
    "麻豆", "果冻传媒", "天美传媒", "精东传媒",
]

WEAK_ADULT_TOKENS = [
    "成人", "18+", "porn", "传媒", "色播", "丝袜", "美腿",
    "花活", "1024",
    "91panta", "91splt", "91bobo", "91精品",
    "色花糖", "朱古力", "涩涩",
    # 2026-09-26：「玩偶」移出——wogg 系 4K 网盘影视站，非成人站（用户裁定）
    "裸聊", "裸播", "黄播", "黄网", "瑟瑟情",
    "探花", "蜜桃", "糖心", "海角", "含羞草", "草榴", "秋霞", "番号", "无码", "里番",
    "淫水", "色屌丝", "咪咪资源", "嗨片", "吃瓜", "迷妹", "黄果", "熊猫资源",
    "果冻", "天美", "精东",
]

ADULT_FALSE_POSITIVE_KEYS = {
    "webdav", "webdav1", "webdav2", "webdav3",
    "clouddrive", "aliyundrive", "aliyundrive2",
}

ADULT_FALSE_POSITIVE_NAME_FRAGMENTS = (
    "webdav", "web dav", "clouddrive", "阿里云盘", "alist",
)

PROBE_STREAM_RANGE = (0, 2047)  # 直播抽验流 2KB（与 aa5a88d 通用做法对齐）

SEARCH_KEYWORDS = ("麻豆", "爱", "传媒")

_LOOPBACK_HOSTS = {"localhost", "0.0.0.0", "::1", "[::1]"}

DEPS_DIR = "deps"

DEP_BACKOFF_MAX_DAYS = 14

DEP_BACKOFF_DEAD_DAYS = 30

DEP_TIMEOUT = 8

DEP_TOTAL_BUDGET = 15  # 单依赖全链路(直连+镜像)总预算秒，防死URL拖慢整轮

DEP_MAX_BYTES = 8 * 1024 * 1024

_DEP_DOMAIN_SEMAPHORES = {}

_IDNA_CACHE = {}

_git_probe_cache: dict = {}

KIND_FAIL_LIMIT = {
    "timeout": 5,            # 网络抖动多，宽容 5 次才降权
    "404": 2,                # 源已删，2 次即剔除
    "connection_refused": 2, # 连接拒绝=源下线，2 次即剔除
    "5xx": 3,                # 服务端错误，3 次降权
    "empty_product": 3,      # 空内容，3 次降权
}

CATEGORY_OVERRIDE_VALUES = ("short", "adult", "vod", "cms", "pan", "csp")

CONTENT_CATEGORIES = ("short", "adult", "vod")   # 仅这些会短路 classify_site

CATEGORY_LABELS = [("cctv", "央视"), ("weishi", "卫视"), ("gangtai", "港台"), ("other", "其他")]

_STATUS_RANK = {"ok": 0, "probe": 1, "mirror": 1, "degraded": 2,
                "dead": 3, "disabled": 4, "blacklisted": 5}

ICONS = {"ok": "🟢", "degraded": "🟡", "dead": "🔴", "disabled": "⚫", "blacklisted": "🚫"}

STATUS_CN = {"ok": "可用", "degraded": "降级", "dead": "失效", "disabled": "已停用",
             "blacklisted": "黑名单", "probe": "🔵探活", "mirror": "镜像"}

PAN_CK_ENDPOINTS = [
    {"disk": "阿里云盘", "ck_field": "token / open_token", "method": "POST 中转",
     "api": "http://api.extscreen.com/aliyundrive/token",
     "note": "open_api_url 默认中转，POST 传 refresh_token 换 open_token"},
    {"disk": "夸克网盘", "ck_field": "quark_cookie", "method": "网页登录",
     "api": "https://pan.quark.cn", "note": "浏览器登录后 F12 复制 Cookie 全量"},
    {"disk": "UC网盘", "ck_field": "uc_cookie", "method": "网页登录",
     "api": "https://drive.uc.cn", "note": "浏览器登录后 F12 复制 Cookie 全量"},
    {"disk": "天翼云盘", "ck_field": "thunder_username/password + captchatoken", "method": "账密+验证码",
     "api": "https://m.cloud.189.cn/login.html", "note": "账密写入 token.json，登录需验证码"},
    {"disk": "115网盘", "ck_field": "cookie(UID/CID/SEID)", "method": "扫码",
     "api": "https://qrcodeapi.115.com/api/1.0/user/1.0/qrcode/token/", "note": "扫码拿二维码 → 轮询确认换 cookie"},
    {"disk": "PikPak", "ck_field": "pikpak_username/password", "method": "账密",
     "api": "https://user.mypikpak.com/v1/auth/token", "note": "OAuth password grant，账密直接换 token"},
    {"disk": "移动云盘", "ck_field": "yd_auth", "method": "App 抓包",
     "api": "https://passport.yun.139.com", "note": "App 登录后抓包取 auth 值"},
    {"disk": "百度网盘", "ck_field": "cookie(BDUSS)", "method": "网页登录",
     "api": "https://pan.baidu.com", "note": "浏览器登录后复制 BDUSS"},
]

