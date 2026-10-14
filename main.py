"""表情感知增强插件主入口。

提供多模态表情包与普通图片的智能识别判定，并动态注入社交交互指引，
帮助大模型理解表情包情绪、态度与梗文化，告别呆板的看图说话。
"""

from __future__ import annotations

from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star
from astrbot.core.agent.message import TextPart

from .detector import MessageSenseResult, StickerDetector


class StickerSensePlugin(Star):
    """表情与表情包感知增强插件。"""

    def __init__(self, context: Context, config: dict | None = None) -> None:
        """初始化插件。

        Args:
            context: AstrBot 插件运行上下文。
            config: 插件配置字典（由 AstrBot 自动传入）。
        """
        super().__init__(context)
        self.config: dict[str, Any] = config or {}
        max_dim = self.config.get("max_sticker_dimension", 640)
        self.detector = StickerDetector(max_sticker_dimension=int(max_dim))

    async def initialize(self) -> None:
        """异步生命周期初始化。"""
        # 读取持久化的开关覆盖（若用户通过指令修改过）
        try:
            persisted_enabled = await self.get_kv_data("enable_sticker_sense", None)
            if persisted_enabled is not None:
                self.config["enable_sticker_sense"] = bool(persisted_enabled)
        except Exception as exc:
            logger.debug(f"[StickerSense] 读取持久化配置异常，回退默认配置: {exc}")

        enabled = self.config.get("enable_sticker_sense", True)
        style = self.config.get("prompt_style", "natural")
        logger.info(
            f"[StickerSense] 表情感知插件已加载，状态: {'启用' if enabled else '停用'}，交互风格: {style}。"
        )

    async def terminate(self) -> None:
        """异步生命周期终止清理。"""
        logger.info("[StickerSense] 表情感知插件已卸载。")

    def _build_style_guide(self, style: str) -> str:
        """根据配置风格生成对应的交互要求。

        Args:
            style: 风格名称 ('natural' | 'humorous' | 'gentle' | 'roast')。

        Returns:
            针对该风格的提示文本。
        """
        if style == "roast":
            return (
                "用户正在使用表情包与你幽默互怼或戏谑调侃！"
                "请以机智幽默、轻度吐槽或动漫式傲娇的方式接招，"
                "切勿死板看图说话。但注意必须在严格维持你既有性格人设的前提下进行，不可脱离人设！"
            )
        if style == "humorous":
            return (
                "用户正在使用表情包与你斗图或幽默互动！"
                "请积极接梗，以机智风趣、生动活泼且贴合人设的口吻进行互动吐槽，"
                "切勿死板、机械地描述画面细节。"
            )
        if style == "gentle":
            return (
                "用户正在借由表情包委婉传达自身心情或社交情感。"
                "请细心体察对方表达的微妙情绪，给予温柔贴切、有共鸣的回应，"
                "避免生硬的看图说话。"
            )
        # 默认 natural
        return (
            "请结合当前对话语境，将其理解为用户的情绪反应、打趣或表情互动。"
            "请像现实生活中真人聊天那样自然、有温度地回应，"
            "切勿生硬地逐一描述画面的构图或文字细节，除非用户明确要求解释图意。"
        )

    def _generate_llm_guidance(self, sense: MessageSenseResult) -> str:
        """生成注入给 LLM 的动态指引块。

        Args:
            sense: 消息视觉与表情检测结果。

        Returns:
            生成的 XML 格式指引文本。
        """
        style = self.config.get("prompt_style", "natural")
        style_rule = self._build_style_guide(style)
        face_translation_enabled = self.config.get("enable_face_translation", True)
        display_faces = sense.faces if face_translation_enabled else []

        lines: list[str] = [
            "<image_interaction_guide>",
            "【视觉与社交交互指引】",
        ]

        if sense.has_stickers and not sense.has_normal_photos:
            lines.append(
                "检测到用户发送的内容为【表情包 / 梗图 / 趣味动图】（非日常摄影或截图）："
            )
            for item in sense.images:
                lines.append(f"- {item.describe()}")
            if display_faces:
                lines.append(f"- 伴随表情符号: {', '.join(display_faces)}")
            lines.append(f"【互动原则】：{style_rule}")

        elif sense.has_stickers and sense.has_normal_photos:
            lines.append("检测到用户同时发送了【表情包】与【普通图片/截图】：")
            for item in sense.images:
                lines.append(f"- {item.describe()}")
            if display_faces:
                lines.append(f"- 伴随表情符号: {', '.join(display_faces)}")
            lines.append(
                f"【互动原则】：请区分对待——对表情包请按社交梗与情绪自然反应（{style_rule}）；"
                "对普通照片或截图则正常关注内容并提供协助或评论。"
            )

        elif sense.has_normal_photos:
            lines.append("检测到用户发送的内容为【普通图片 / 拍摄照片 / 屏幕截图】：")
            for item in sense.images:
                lines.append(f"- {item.describe()}")
            if display_faces:
                lines.append(f"- 伴随表情符号: {', '.join(display_faces)}")
            lines.append(
                "【互动原则】：用户正在分享现实生活细节、寻求帮助或展示内容，"
                "请结合对话上下文正常理解与分析图片内容。"
            )

        elif display_faces:
            lines.append(f"检测到用户发送了表情符号: {', '.join(display_faces)}。")
            lines.append(
                "【互动原则】：请结合该表情符号所体现的语气与情绪倾向，自然贴合地回应用户。"
            )

        if sense.has_stickers:
            if sense.has_animated_stickers:
                lines.append(
                    "【动图认知规范】：检测到动态表情包。若底层视觉服务将其分解为多帧排列，此排版仅为展示连贯动作，切勿将其误认为九宫格、拼图或数其帧数，请直接理解其连贯动作与情绪含义。"
                )
            lines.append(
                "【意图与人设原则】：若表情包带有调侃、赞同、认怂或撒娇等潜台词，请自然接梗反应；无论何种互动，必须严格保持你既有的角色人设底线，不可脱离人设。"
            )
            enable_meme_reaction = self.config.get("enable_meme_reaction", False)
            if enable_meme_reaction:
                lines.append(
                    "【双向斗图提示】：用户开启了斗图互动倾向。如果你觉得当前语境非常适合以表情包回敬（如极度无语、开怀大笑、傲娇吐槽时），可根据平台支持的表情或在适当情境下配合斗图，但请以文字对话为主，严禁每句都机械性回复表情。"
                )

        custom_guide = (self.config.get("custom_prompt_guide") or "").strip()
        if custom_guide:
            lines.append(f"【个性化补充指引】：{custom_guide}")

        lines.append("</image_interaction_guide>")
        return "\n".join(lines)

    @filter.on_llm_request()
    async def on_llm_request(
        self,
        event: AstrMessageEvent,
        req: ProviderRequest,
    ) -> None:
        """在 LLM 组装请求前拦截并注入表情包感知指引。

        Args:
            event: 当前平台消息事件对象。
            req: 即将提交给大模型的请求载荷对象。
        """
        # 1. 开关校验
        if not self.config.get("enable_sticker_sense", True):
            return

        raw_message = getattr(event.message_obj, "raw_message", None)
        components = getattr(event.message_obj, "message", [])

        # 2. 图像与表情综合感知分析
        # req.image_urls 包含了 AstrMainAgent 已经下载/准备好的本地图像路径
        image_paths = req.image_urls or []

        sense = self.detector.analyze_event(
            image_paths=image_paths,
            raw_message=raw_message,
            components=components,
        )

        if not sense.has_any_visual_or_emoji:
            # 没有图片也没有表情符号，静默放行
            return

        # 3. 针对纯表情或纯表情包空 Prompt 进行兜底保护
        auto_fill = self.config.get("auto_fill_empty_prompt", True)
        face_translation_enabled = self.config.get("enable_face_translation", True)
        if auto_fill and not (req.prompt or "").strip():
            if sense.has_stickers:
                req.prompt = "（用户向你发送了一张表情包）"
            elif sense.has_normal_photos:
                req.prompt = "（用户向你分享了一张图片）"
            elif sense.faces and face_translation_enabled:
                req.prompt = f"（用户向你发送了表情：{', '.join(sense.faces)}）"
            elif sense.faces:
                req.prompt = "（用户向你发送了表情符号）"

        # 4. 构建动态指引并通过 extra_user_content_parts 临时注入
        guidance = self._generate_llm_guidance(sense)

        # 必须调用 .mark_as_temp()：确保仅单轮生效，不修改 system_prompt，不破坏缓存
        req.extra_user_content_parts.append(TextPart(text=guidance).mark_as_temp())

        logger.debug(
            f"[StickerSense] 已为会话 {event.unified_msg_origin} 注入表情感知提示 (包含 "
            f"{len(sense.images)} 张图片, {len(sense.faces)} 个表情)。"
        )

    # ------------------ 管理指令组 ------------------
    @filter.command_group("sticker")
    def sticker(self) -> None:
        """表情包感知插件管理指令。"""
        pass

    @sticker.command("status")
    async def sticker_status(self, event: AstrMessageEvent):
        """查看表情感知插件运行状态与当前配置。"""
        enabled = self.config.get("enable_sticker_sense", True)
        face_trans = self.config.get("enable_face_translation", True)
        style = self.config.get("prompt_style", "natural")
        max_dim = self.config.get("max_sticker_dimension", 640)
        auto_fill = self.config.get("auto_fill_empty_prompt", True)
        meme_reaction = self.config.get("enable_meme_reaction", False)
        custom_guide = self.config.get("custom_prompt_guide", "")

        msg = (
            "✨ 【表情感知 (Sticker Sense) 运行状态】\n"
            f"• 核心感知开关: {'🟢 启用' if enabled else '🔴 停用'}\n"
            f"• 表情符号转义: {'🟢 开启' if face_trans else '🔴 关闭'}\n"
            f"• 交互引导风格: {style}\n"
            f"• 双向斗图倾向: {'🟢 开启' if meme_reaction else '🔴 关闭'}\n"
            f"• 启发式尺寸上限: {max_dim} px\n"
            f"• 空文本自动兜底: {'🟢 开启' if auto_fill else '🔴 关闭'}\n"
            f"• 自定义补充指引: {custom_guide if custom_guide else '(未设定)'}\n\n"
            "💡 提示: 可通过 WebUI 面板直接修改配置，或使用 /sticker toggle 快速切换开关。"
        )
        yield event.plain_result(msg)

    @sticker.command("toggle")
    async def sticker_toggle(self, event: AstrMessageEvent):
        """快速切换表情感知插件的启用状态并持久化。"""
        current = self.config.get("enable_sticker_sense", True)
        new_state = not current
        self.config["enable_sticker_sense"] = new_state

        try:
            await self.put_kv_data("enable_sticker_sense", new_state)
        except Exception as exc:
            logger.warning(f"[StickerSense] 保存状态失败: {exc}")

        state_text = "🟢 已启用" if new_state else "🔴 已停用"
        yield event.plain_result(f"表情感知功能已切换为: {state_text}")
