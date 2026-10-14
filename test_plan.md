# 表情感知 (Sticker Sense) - 测试方案与验收用例 (test_plan.md)

## 1. 测试范围

1. **表情包识别逻辑**：
   - 协议字段判定测试（`subType: 1`, `sub_type: "1"`, `summary: "[动画表情]"` 等）。
   - 动画格式判定测试（GIF 动图检测）。
   - 启发式尺寸判定测试（小图表情包 vs 高清照片/截图）。
2. **QQ 表情映射测试**：
   - 常用小黄脸表情 ID 转换为中文标签（微笑、狗头、滑稽等）。
   - 未知表情 ID 优雅降级（`[表情: ID 9999]`）。
3. **LLM 请求钩子注入测试**：
   - 表情包场景：检查注入的 `<image_interaction_guide>` 包含社交与情绪互动引导。
   - 普通图片场景：检查注入的提示指导大模型正常协助或评论。
   - 验证注入内容调用了 `.mark_as_temp()`，且未篡改 `req.system_prompt`。
   - 验证纯表情或纯表情包导致 `req.prompt` 为空时，兜底填充生效。
4. **管理指令与配置测试**：
   - `/sticker` 状态查询。
   - `/sticker toggle` 状态切换并验证 KV 存储持久化调用。
   - 自定义提示词追加（`custom_prompt_guide`）正确拼接测试。
   - 表情翻译开关（`enable_face_translation=False`）阻断测试。

---

## 2. 自动化测试计划

- 测试工具：`pytest`
- 测试文件：`data/plugins/astrbot_plugin_sticker_sense/tests/test_sticker_sense.py`
- Mock 机制：Mock `AstrMessageEvent`, `ProviderRequest`, PIL 图像对象。
- 验收标准：所有测试用例 100% 通过，无 Warning 与异常。
