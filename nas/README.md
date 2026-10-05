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
- 后续增量加入真实媒体测速与 7/30 日稳定性评分。
