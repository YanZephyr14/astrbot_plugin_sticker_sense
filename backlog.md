# 表情感知 (Sticker Sense) - 待办拆解与开发进度追踪 (backlog.md)

## 待办事项

- [x] 梳理需求目标与架构设计（`objective.md`）
- [x] 建立插件专属 Git 仓库并同步远程配置
- [x] 编写 WebUI 配置项规范（`_conf_schema.json`）
- [x] 编写插件元数据清单（`metadata.yaml`）
- [x] 实现 QQ 经典原生表情代码与名称映射模块（`face_map.py`）
- [x] 实现图片与表情包多维检测引擎（`detector.py`）
- [x] 实现插件核心入口与生命周期管理（`main.py`）
  - [x] 实现 `@filter.on_llm_request` 钩子及动态上下文注入
  - [x] 实现纯表情/纯表情包空 Prompt 兜底保护
  - [x] 实现管理指令 `/sticker` 及 `/sticker toggle`
- [x] 编写详尽单元测试与 Mock 测试（`tests/test_sticker_sense.py`）
- [x] 执行 Ruff 代码静态检查与格式化
- [x] 验证所有单测用例全部通过
- [x] 创建 GitHub 远程仓库并完成首次推送
- [x] 更新根目录 `DEVLOG.md`
- [x] 国际化多语言支持（`.astrbot-plugin/i18n/zh-CN.json` 与 `en-US.json`）
- [x] 开源交付物建设（`README.md`、`LICENSE`、`requirements.txt`）
- [x] 增强配置持久化（KV Storage 支持跨重启保留指令切换状态）
- [x] 增强自定义追加词支持与配置联动测试（11 passed）
- [x] 同步推送规范化更新至远程仓库并在实例热部署
- [x] **v1.1.0 迭代演进与效果强化**：
  - [x] 排查实例实机聊天记录，定位九宫格出戏幻觉与表情名缺失问题
  - [x] 评估改进方案潜在副作用（防误伤真实拼图、防逆反心理、防人设 OOC、防斗图乱码泄漏）
  - [x] `detector.py` 动态提取 `raw.faceText` 覆盖 100% 官方小黄脸
  - [x] `detector.py` 增加 `has_animated_stickers` 精准区分动图与静态图
  - [x] `main.py` 注入动图连贯认知规范，消除“九宫格九次”出戏幻觉
  - [x] `main.py` 强化表情包网络意图感知与人设第一防 OOC 约束
  - [x] `main.py` 与 `_conf_schema.json` 扩充 `roast` 风格与 `enable_meme_reaction` 双向斗图开关
  - [x] 编写并扩充单元测试用例（13/13 全部通过）
  - [x] Ruff 检查与代码格式化通过
  - [x] 提交专属 Git 仓库并同步远程 GitHub
  - [x] 热同步至运行实例目录并更新 `DEVLOG.md`
- [x] **v1.1.1 平台支持范围修正与元数据收敛**：
  - [x] 确立 QQ 生态专属定位（纠正多填的 Telegram/Discord/WeCom 等非 QQ 平台）
  - [x] `metadata.yaml` 严格限定支持平台为 `aiocqhttp`、`qq_official`、`qq_official_webhook`
  - [x] 同步更新 `README.md`、`objective.md`、`test_plan.md`
  - [x] 新增平台声明单测用例并确保全量测试通过
  - [x] 提交并推送到 GitHub 远程仓库，热同步至本地运行实例并追加 `DEVLOG.md`

