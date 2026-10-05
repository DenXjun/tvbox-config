# fetch_merge.py 拆分方案（基于 AST 真实分析）

> 结论先行：**不建议做一次性机械拆分**。本文记录已实测的拆分尝试与失败原因，
> 并给出安全的分阶段路线。所有数据来自对 `scripts/fetch_merge.py`（6198 行）的 AST 分析。

## 一、规模与结构（真实数据）

- 顶层函数 **134 个**（另有 1 个重定义），模块级全局变量 **141 个**。
- **函数级调用图无环**（严格 DAG）——这是机械拆分看起来可行的原因。

| 事实 | 值 | 对拆分的影响 |
|---|---|---|
| 顶层函数 | 134 | 切割单位 |
| 重定义函数 | `classify_site`（行 960 被行 1043 覆盖，生效=1043） | 按函数名索引会取错版本，必须按 `(name, lineno)` |
| 模块级全局变量 | 141 | 主要是只读配置/路径/关键词表 |
| 用 `global` 重绑定全局的函数 | 仅 2 个：`_merge_upstream_config`（5 个上游列表）、`main`（`DOMAIN_MAP`/`RAW_VOD_VERIFY_ACTIVE`） | 这 7 个全局是**核心可变状态** |

## 二、机械拆分为何失败（已实测，非推测）

把 6198 行按函数边界切成 8 个 part 放入包后，import 链依次暴露三层问题：

1. **模块级调用时机错位**：`__init__` 里 `_MIRROR_ROUNDS = _load_mirror_rounds()` 在
   `from ._partN import ...` 之前执行 → `NameError: _load_mirror_rounds`。
   修法：import 段在前、模块级调用段在后。
2. **模块级常量未分发**：`_load_mirror_rounds` 引用全局 `MIRROR_RANKING_FILE`，
   但该常量只在包 `__init__` 命名空间、函数所在的 `_part1` 看不到 →
   `NameError: MIRROR_RANKING_FILE`。修法：把 141 个全局抽到独立 `_globals` 模块。
3. **块级循环导入**：函数级无环 ≠ 块级无环。`_part1 ↔ _part4` 双向跨块调用
   （`part1` 的函数调 `part4` 的 `http_get`，`part4` 的函数调 `part1` 的 `dep_classify`），
   顶部 `import` 形成循环 → `ImportError: partially initialized module`。
   修法：按**块级强连通分量**合并（实测 8 块合并为 6 块）。
4. **核心可变全局仍会分裂**：合并掉所有块级环之后，剩下的根本障碍是那 7 个被
   `global` 重绑定的核心全局（`UPSTREAMS` 等上游列表被大量函数读取）。
   一旦 `_merge_upstream_config` 与读取方分处不同模块，`global X; X = new` 只重绑当前模块，
   读取方仍看到旧值 → 状态分裂。要避免就必须把这些读取方与它同块，
   而它被**几乎全文件**的函数引用 → 退化成「一个大块 + 零散小块」，拆分收益归零。

**净结论**：函数级 DAG 不足以支撑机械拆分；本文件的真正耦合是**模块级可变全局**。

## 三、安全分阶段路线（按收益/风险排序）

- **阶段 1（✅ 已完成 2026-10-05）**：只读全局抽到 `scripts/fm_config.py`，
  `fetch_merge.py` 用 `from fm_config import *`。实测 141 个全局中**仅 35 个**同时满足
  「顶层赋值 + 右侧无函数调用 + 不引用项目函数/可变全局 + 依赖闭包自洽」→ 抽出，
  `fetch_merge.py` **6198 → 6069 行**（`1f1555e2` 补回显式导入 8 行、删死代码 −1 行），
  AST 校验 33 个存活常量全部在 `fetch_merge` 可达、顶层无重名（`_VALID_PARSE_TYPES`
  经 AST 确认为全仓无引用的死代码，已删）。
  - 98 个含函数调用的全局（多为 `os.environ.get(...)`/`int(...)`）**刻意留存**，
    它们虽是配置但含调用，需在放宽判定后另做一档；7 个 `global` 重绑定的可变运行时状态永不抽出。
  - 机械搬移构造保证值等价；后续若要继续放宽（把 `os.environ` 类也迁入 fm_config），
    需先确认这些常量在 import 期求值时机不变（当前是 fetch_merge import 时求值）。
  - 判定「只读」：顶层赋值、右侧无函数调用、且名字不在那 7 个 `global` 重绑定名单里。
  - 就地修改（如 `LIST.append(...)`）的全局仍可安全抽出——导入的是同一对象引用；
    只有 `global X; X = new` 这种**重新绑定**才会分裂。
  - 收益：fetch_merge 瘦几百行，配置集中可审计；行为等价（常量只读）。
  - **踩坑（已修 `1f1555e2`）**：`from fm_config import *` 按 Python 规范**跳过下划线开头的
    名字**，`_LOOPBACK_HOSTS` / `_IDNA_CACHE` / `_STATUS_RANK` /
    `_DEP_DOMAIN_SEMAPHORES` / `_git_probe_cache` 这 5 个活跃符号因此在 `fetch_merge`
    里查不到定义，跑到第 1289 行才 `NameError`。**`import` 冒烟测不出来**——
    报错发生在函数体执行时。修法：这 5 个改为显式 `from fm_config import (...)`。
    → 阶段 2/3 教训：**验证必须执行到函数体**，不能只 import；
    若源模块有下划线私有符号，要么显式导入，要么在源模块写 `__all__`。
- **阶段 2（低风险）**：抽**叶子纯函数**（无全局依赖、只依赖参数与标准库）到
  `scripts/fm_util.py`，如 `_split_gh_prefix`、`_sanitize_seg`、`sha12`、`md5_of` 等。
- **阶段 3（需先解耦，谨慎）**：把 7 个核心可变全局收敛成**单一状态容器对象**
  （如 `STATE.upstreams`），消除 `global` 重绑定；之后才可按职责
  （镜像/合并/成人/分类/依赖/探针/编排）真正切分。

## 四、维护约定

- 任何重定义函数必须按 `(name, lineno)` 定位，**不能按函数名**（`classify_site` 是现成教训）。
- 新增顶层全局前先问：它会被 `global` 重绑定吗？会 → 别放进可抽出的只读配置模块。
- 阶段 1/2 不改变任何行为，可随时验证回滚；阶段 3 需配套回归（本地 `run_all.py` 或观察一次 daily）。
- **验证准则（阶段 1 血泪教训）**：`python -c "import fetch_merge"` 通过**不等于**没问题。
  阶段 1 首次提交就带着一个 `import` 能过、跑到第 1289 行必崩的 `NameError`。
  每次搬符号后至少做三件事：① AST 列出源模块顶层常量，断言全部在目标模块可 `hasattr`；
  ② **真实调用**至少一条用到新符号的函数；③ 跑一遍所有 `import fetch_merge` 的下游脚本。
