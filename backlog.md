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
- [ ] 创建 GitHub 远程仓库并完成首次推送
- [ ] 更新根目录 `DEVLOG.md`
