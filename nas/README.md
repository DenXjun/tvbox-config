# Synology x86_64 NAS 版

面向群晖 Container Manager 的轻量常驻入口。原 GitHub Actions 流程保持不变，NAS 服务只编排点播相关阶段。

## 群晖 Container Manager 部署

群晖最终部署目录只需要：

```
tvbox-nas/
├── Dockerfile
├── docker-compose.yml
├── runtime.tar.gz
├── data/
├── output/
├── config/
└── logs/
```

`runtime.tar.gz` 在开发机/仓库环境运行 `python nas/build_runtime.py` 生成。它把 NAS 所需代码、配置、依赖和种子状态合成一个文件，群晖不再需要上传完整仓库和大量小文件。

将 `nas/Dockerfile`、`nas/docker-compose.yml`、生成的 `nas/runtime.tar.gz` 放在群晖同一目录。Container Manager → 项目 → 新增，选择该目录并构建。

启动后打开 `http://NAS-IP:8787/`。首次自动维护默认延迟 120 秒，也可直接点“立即维护”。最终 TVBox 订阅为 `http://NAS-IP:8787/tvbox.json`，该地址只发布经过健康检测后的 VOD 结果。

持久化目录为 `data`、`output`、`config`、`logs`；升级镜像不会清空检测历史和手工上游。

## v1 边界

- amd64/x86_64 only。
- 保留上游的 CMS HTTP L1-L3、DRPY、发现、去重、入库和健康导出能力。
- NAS 编排不运行直播链路、成人源专项链路和 Android 真机 CSP 深检。
- Web 后台支持查看状态、添加手工上游、立即运行和读取订阅。
- 手工上游写入持久化 `nas/config/upstreams.json`，与原项目 fetch_merge 使用同一配置链。
- 每轮最多深测 160 个 CMS 候选，并轮转抽样 40 个 L3 实际播放 URL；质量历史保存在 `nas/data`。
- 已启用真实媒体测速、7/30 日稳定性评分和最终健康源质量排序。
- NAS 输出默认过滤明显成人源；不修改上游原始数据。
- `state/` 在容器启动时迁移到 `nas/data/state`，连续失败、恢复和检测历史跨容器升级保留。
