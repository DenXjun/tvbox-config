# Synology x86_64 NAS 版

面向群晖 Container Manager 的轻量常驻入口。原 GitHub Actions 流程保持不变，NAS 服务只编排点播相关阶段。

## 部署

在群晖中将本仓库放到 `/volume1/docker/tvbox-config`，进入 `nas` 目录执行：

```bash
docker compose up -d --build
```

打开 `http://NAS-IP:8787/`。TVBox 订阅地址为 `http://NAS-IP:8787/tvbox.json`。

持久化目录：`nas/data`、`nas/output`、`nas/config`、`nas/logs`。默认每 12 小时维护一次，也可在 Web 页面手动触发。

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
