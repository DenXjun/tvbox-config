# Synology x86_64 NAS 版

面向群晖 Container Manager 的轻量常驻入口。原 GitHub Actions 流程保持不变，NAS 服务只编排点播相关阶段。

## 群晖 Container Manager 部署

1. 下载/克隆本仓库的 `codex/synology-x86-v1` 分支到群晖，例如 `/volume1/docker/tvbox-config`。
2. Container Manager → 项目 → 新增 → 选择 `nas/docker-compose.yml` 所在项目目录并构建。
3. 项目启动后打开 `http://NAS-IP:8787/`。页面可直接查看当前维护步骤和最近日志。
4. 首次自动维护默认延迟 120 秒；也可以页面打开后直接点“立即维护”。
5. TVBox 订阅地址：`http://NAS-IP:8787/tvbox.json`。

如使用 SSH，也可以进入 `nas` 目录执行 `docker compose up -d --build`。

Container Manager 项目需要保留完整仓库目录，因为镜像构建会复用上游脚本和 DRPY sandbox。持久化目录：`nas/data`、`nas/output`、`nas/config`、`nas/logs`。默认每 12 小时维护一次，也可在 Web 页面手动触发。

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
