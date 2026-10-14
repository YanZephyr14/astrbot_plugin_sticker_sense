"""Unit and integration tests for astrbot_plugin_sticker_sense."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image as PILImage

from astrbot.core.agent.message import TextPart
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.provider.entities import ProviderRequest

# 导入插件模块
from data.plugins.astrbot_plugin_sticker_sense.detector import (
    ImageDetectionResult,
    MessageSenseResult,
    StickerDetector,
)
from data.plugins.astrbot_plugin_sticker_sense.face_map import get_face_name
from data.plugins.astrbot_plugin_sticker_sense.main import StickerSensePlugin


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test images."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


def create_test_image(
    path: Path,
    size: tuple[int, int] = (200, 200),
    is_animated: bool = False,
    fmt: str = "PNG",
) -> str:
    """Helper to create test images."""
    file_path = str(path)
    if is_animated:
        images = [
            PILImage.new("RGB", size, color="red"),
            PILImage.new("RGB", size, color="blue"),
        ]
        images[0].save(
            file_path,
            save_all=True,
            append_images=images[1:],
            format="GIF",
            duration=100,
            loop=0,
        )
    else:
        img = PILImage.new("RGB", size, color="white")
        img.save(file_path, format=fmt)
    return file_path


class TestFaceMap:
    """Test QQ face ID mappings."""

    def test_known_face_ids(self):
        assert get_face_name(14) == "微笑"
        assert get_face_name(178) == "狗头"
        assert get_face_name("13") == "呲牙"

    def test_unknown_face_ids(self):
        assert get_face_name(99999) == "表情_99999"
        assert get_face_name("abc") == "表情_abc"


class TestStickerDetector:
    """Test image detection logic."""

    def test_protocol_subtype_detection(self):
        detector = StickerDetector(max_sticker_dimension=640)
        res = detector.inspect_image_file(
            file_path="dummy.jpg",
            index=1,
            protocol_data={"subType": 1, "summary": "[动画表情]"},
        )
        assert res.is_sticker is True
        assert "协议层标记为表情包" in res.reason

    def test_animated_gif_detection(self, temp_dir):
        gif_path = create_test_image(
            temp_dir / "anim.gif", size=(300, 300), is_animated=True
        )
        detector = StickerDetector()
        res = detector.inspect_image_file(gif_path, index=1)
        assert res.is_sticker is True
        assert res.is_animated is True
        assert "多帧动态图像" in res.reason

    def test_small_heuristic_sticker(self, temp_dir):
        small_path = create_test_image(
            temp_dir / "small.png", size=(240, 240), is_animated=False
        )
        detector = StickerDetector(max_sticker_dimension=640)
        res = detector.inspect_image_file(small_path, index=1)
        assert res.is_sticker is True
        assert "启发式小尺寸图像" in res.reason

    def test_large_photo_detection(self, temp_dir):
        large_path = create_test_image(
            temp_dir / "photo.jpg", size=(1920, 1080), is_animated=False, fmt="JPEG"
        )
        detector = StickerDetector(max_sticker_dimension=640)
        res = detector.inspect_image_file(large_path, index=1)
        assert res.is_sticker is False
        assert "高分辨率或摄影图规格" in res.reason

    def test_analyze_event_mixed(self, temp_dir):
        gif_path = create_test_image(
            temp_dir / "sticker.gif", size=(200, 200), is_animated=True
        )
        photo_path = create_test_image(
            temp_dir / "photo.png", size=(1600, 1200), is_animated=False
        )
        detector = StickerDetector(max_sticker_dimension=640)

        raw_msg = {
            "message": [
                {"type": "image", "data": {"file": "sticker.gif"}},
                {"type": "image", "data": {"file": "photo.png"}},
                {"type": "face", "data": {"id": 178}},
            ]
        }

        sense = detector.analyze_event(
            image_paths=[gif_path, photo_path], raw_message=raw_msg
        )
        assert sense.has_stickers is True
        assert sense.has_normal_photos is True
        assert len(sense.faces) == 1
        assert sense.faces[0] == "[表情: 狗头]"


class TestStickerSensePlugin:
    """Test main plugin hooks and commands."""

    @pytest.mark.asyncio
    async def test_llm_request_hook_sticker_injection(self, temp_dir):
        gif_path = create_test_image(
            temp_dir / "meme.gif", size=(200, 200), is_animated=True
        )

        context = MagicMock()
        plugin = StickerSensePlugin(
            context,
            config={
                "enable_sticker_sense": True,
                "prompt_style": "humorous",
                "auto_fill_empty_prompt": True,
            },
        )
        await plugin.initialize()

        event = MagicMock(spec=AstrMessageEvent)
        event.unified_msg_origin = "qq:group:123456"
        event.message_obj = MagicMock()
        event.message_obj.raw_message = {
            "message": [
                {"type": "image", "data": {"subType": 1}},
                {"type": "face", "data": {"id": 14}},
            ]
        }
        event.message_obj.message = []

        req = ProviderRequest(prompt="")
        req.image_urls = [gif_path]
        req.system_prompt = "你是AI助手。"

        # 执行 hook
        await plugin.on_llm_request(event, req)

        # 验证 system_prompt 未被篡改 (四大铁律/缓存友好)
        assert req.system_prompt == "你是AI助手。"

        # 验证空 prompt 被自动兜底
        assert req.prompt == "（用户向你发送了一张表情包）"

        # 验证 extra_user_content_parts 注入了动态指引
        assert len(req.extra_user_content_parts) == 1
        part = req.extra_user_content_parts[0]
        assert isinstance(part, TextPart)
        assert part._no_save is True  # mark_as_temp生效
        assert "<image_interaction_guide>" in part.text
        assert "斗图或幽默互动" in part.text  # humorous风格
        assert "[表情: 微笑]" in part.text

    @pytest.mark.asyncio
    async def test_llm_request_disabled(self):
        context = MagicMock()
        plugin = StickerSensePlugin(
            context,
            config={"enable_sticker_sense": False},
        )
        event = MagicMock()
        req = ProviderRequest(prompt="test")
        req.image_urls = ["dummy.jpg"]

        await plugin.on_llm_request(event, req)
        assert len(req.extra_user_content_parts) == 0

    @pytest.mark.asyncio
    async def test_sticker_commands(self):
        context = MagicMock()
        plugin = StickerSensePlugin(context, config={"enable_sticker_sense": True})

        event = MagicMock(spec=AstrMessageEvent)
        event.plain_result = MagicMock(side_effect=lambda x: x)

        # Test status command
        status_gen = plugin.sticker_status(event)
        res = [item async for item in status_gen]
        assert len(res) == 1
        assert "表情感知 (Sticker Sense) 运行状态" in res[0]
        assert "🟢 启用" in res[0]

        # Test toggle command
        toggle_gen = plugin.sticker_toggle(event)
        toggle_res = [item async for item in toggle_gen]
        assert len(toggle_res) == 1
        assert "🔴 已停用" in toggle_res[0]
        assert plugin.config["enable_sticker_sense"] is False
