"""图像与表情感知探测引擎。

支持结合 QQ/OneBot 协议段元数据与 PIL 本地图像属性进行综合启发式判定。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from PIL import Image as PILImage

from .face_map import get_face_name


@dataclass
class ImageDetectionResult:
    """单个图像检测结果。"""

    index: int
    path: str
    is_sticker: bool
    reason: str
    format: str = "UNKNOWN"
    width: int = 0
    height: int = 0
    is_animated: bool = False
    summary: str | None = None

    def describe(self) -> str:
        """生成面向 LLM 或日志的单行描述。"""
        kind = "表情包/梗图/趣味动图" if self.is_sticker else "普通照片/日常分享/截图"
        details = []
        if self.format != "UNKNOWN":
            details.append(self.format)
        if self.width > 0 and self.height > 0:
            details.append(f"{self.width}x{self.height}")
        if self.is_animated:
            details.append("动画")
        if self.summary:
            details.append(f"标记: {self.summary}")
        detail_str = f" ({', '.join(details)})" if details else ""
        return f"[图片 {self.index}] {kind}{detail_str}，判定依据: {self.reason}"


@dataclass
class MessageSenseResult:
    """整条消息的表情与视觉检测汇总结果。"""

    images: list[ImageDetectionResult]
    faces: list[str]
    has_stickers: bool = False
    has_normal_photos: bool = False
    has_animated_stickers: bool = False

    @property
    def has_any_visual_or_emoji(self) -> bool:
        """是否存在任何视觉或表情符号。"""
        return bool(self.images or self.faces)


class StickerDetector:
    """表情包感知探测器。"""

    # 常见 QQ 协议中表示表情包的 subType 值
    # 1: 表情包/自定义表情; 2: 热图; 3: 斗图; 4: 智图; 7: 贴纸; 8: 贴图; 9: 动画表情
    STICKER_SUBTYPES: set[str | int] = {
        1,
        "1",
        2,
        "2",
        3,
        "3",
        4,
        "4",
        7,
        "7",
        8,
        "8",
        9,
        "9",
    }

    def __init__(self, max_sticker_dimension: int = 640) -> None:
        """初始化探测器。

        Args:
            max_sticker_dimension: 判定为表情包的单边最大像素尺寸（默认 640）。
        """
        self.max_sticker_dimension = max_sticker_dimension

    def inspect_protocol_segments(
        self, raw_message: Any
    ) -> tuple[list[dict], list[str]]:
        """从底层平台原始报文中提取图像段和表情段。

        Args:
            raw_message: 原始事件或消息对象。

        Returns:
            image_segments: 提取出的图片数据字典列表。
            faces: 提取出的人类可读表情标签列表。
        """
        image_segments: list[dict] = []
        faces: list[str] = []

        if not raw_message:
            return image_segments, faces

        # 兼容 dict 或对象类型
        raw_dict: dict | None = None
        if isinstance(raw_message, dict):
            raw_dict = raw_message
        elif hasattr(raw_message, "__dict__"):
            raw_dict = raw_message.__dict__

        if not raw_dict:
            return image_segments, faces

        message_list = raw_dict.get("message")
        if not isinstance(message_list, list):
            return image_segments, faces

        for seg in message_list:
            if not isinstance(seg, dict):
                continue
            seg_type = seg.get("type")
            data = seg.get("data", {})
            if not isinstance(data, dict):
                continue

            if seg_type == "image":
                image_segments.append(data)
            elif seg_type == "face":
                # 优先从协议原始 raw 数据中提取动态 faceText（如 NapCat / OneBot 的 {"faceText": "/菜汪"}）
                face_name: str | None = None
                raw_info = data.get("raw")
                if isinstance(raw_info, dict):
                    raw_text = raw_info.get("faceText") or raw_info.get("text")
                    if isinstance(raw_text, str) and raw_text.strip():
                        face_name = raw_text.strip().lstrip("/").strip()

                if not face_name:
                    fid = data.get("id")
                    if fid is not None:
                        face_name = get_face_name(fid)

                if face_name:
                    faces.append(f"[表情: {face_name}]")
            elif seg_type == "mface":
                # 商城大表情
                summary = data.get("summary") or data.get("text") or "商城大表情"
                faces.append(f"[{summary}]")

        return image_segments, faces

    def inspect_image_file(
        self,
        file_path: str,
        index: int,
        protocol_data: dict | None = None,
    ) -> ImageDetectionResult:
        """根据协议元数据与本地图像属性判定是否为表情包。

        Args:
            file_path: 本地图像路径。
            index: 当前图片在本次请求中的序号（1-indexed）。
            protocol_data: 对应的协议端数据段。

        Returns:
            ImageDetectionResult 检测结果对象。
        """
        summary = None
        sub_type = None
        if protocol_data:
            summary = protocol_data.get("summary")
            sub_type = protocol_data.get("subType") or protocol_data.get("sub_type")

        # 1. 协议段显式标记判断（最高置信度）
        if sub_type is not None and sub_type in self.STICKER_SUBTYPES:
            return ImageDetectionResult(
                index=index,
                path=file_path,
                is_sticker=True,
                reason="协议层标记为表情包 (subType/贴纸/斗图)",
                summary=summary,
            )

        if summary and any(k in summary for k in ("动画表情", "表情", "贴纸")):
            return ImageDetectionResult(
                index=index,
                path=file_path,
                is_sticker=True,
                reason=f"协议层标记摘要: {summary}",
                summary=summary,
            )

        # 2. 本地文件物理检查
        if not file_path or not os.path.exists(file_path):
            return ImageDetectionResult(
                index=index,
                path=file_path,
                is_sticker=False,
                reason="文件不存在或无法访问，默认按普通图片处理",
            )

        try:
            with PILImage.open(file_path) as img:
                fmt = (img.format or "UNKNOWN").upper()
                width, height = img.size
                is_animated = bool(
                    getattr(img, "is_animated", False)
                    or getattr(img, "n_frames", 1) > 1
                )

                # 动图判定：聊天中的绝大多数 GIF/动态 WebP 都是动画表情包
                if is_animated:
                    return ImageDetectionResult(
                        index=index,
                        path=file_path,
                        is_sticker=True,
                        reason="多帧动态图像 (GIF/动图表情)",
                        format=fmt,
                        width=width,
                        height=height,
                        is_animated=True,
                        summary=summary,
                    )

                # 启发式尺寸判定：
                # 表情包通常尺寸较小（如 100~500px），宽高比相对适中（非超长全景图）
                max_edge = max(width, height)
                min_edge = min(width, height)
                aspect_ratio = min_edge / max_edge if max_edge > 0 else 1.0

                file_size_kb = os.path.getsize(file_path) / 1024

                # 表情包特征：长宽在阈值内，文件体积适中 (< 2.5MB)，宽高比在 0.4 以上
                if (
                    max_edge <= self.max_sticker_dimension
                    and aspect_ratio >= 0.4
                    and file_size_kb <= 2500
                ):
                    return ImageDetectionResult(
                        index=index,
                        path=file_path,
                        is_sticker=True,
                        reason=f"启发式小尺寸图像 ({width}x{height}, {file_size_kb:.0f}KB)",
                        format=fmt,
                        width=width,
                        height=height,
                        is_animated=False,
                        summary=summary,
                    )

                # 否则判定为普通图片（如生活摄影照片、高分辨率壁纸、全屏截图）
                return ImageDetectionResult(
                    index=index,
                    path=file_path,
                    is_sticker=False,
                    reason=f"高分辨率或摄影图规格 ({width}x{height}, {file_size_kb:.0f}KB)",
                    format=fmt,
                    width=width,
                    height=height,
                    is_animated=False,
                    summary=summary,
                )
        except Exception as exc:
            return ImageDetectionResult(
                index=index,
                path=file_path,
                is_sticker=False,
                reason=f"图像探测解析异常: {exc}",
            )

    def analyze_event(
        self,
        image_paths: list[str],
        raw_message: Any,
        components: list[Any] | None = None,
    ) -> MessageSenseResult:
        """综合分析事件中的所有图像与表情。

        Args:
            image_paths: 已经下载好的图像本地路径列表。
            raw_message: 协议端原始报文。
            components: AstrBot 解析的消息组件列表（可选）。

        Returns:
            MessageSenseResult 汇总检测结果。
        """
        protocol_images, protocol_faces = self.inspect_protocol_segments(raw_message)

        # 同时也从 components 中补充 Face（以防 raw_message 未覆盖）
        if components:
            for comp in components:
                # 兼容 Comp.Face
                comp_type = getattr(comp, "type", None)
                if comp_type == "Face" or comp.__class__.__name__ == "Face":
                    fid = getattr(comp, "id", None)
                    if fid is not None:
                        face_str = f"[表情: {get_face_name(fid)}]"
                        if face_str not in protocol_faces:
                            protocol_faces.append(face_str)

        detected_images: list[ImageDetectionResult] = []
        has_stickers = False
        has_normal = False
        has_animated_stickers = False

        for i, path in enumerate(image_paths, 1):
            protocol_data = (
                protocol_images[i - 1] if i - 1 < len(protocol_images) else None
            )
            res = self.inspect_image_file(path, index=i, protocol_data=protocol_data)
            detected_images.append(res)
            if res.is_sticker:
                has_stickers = True
                if res.is_animated:
                    has_animated_stickers = True
            else:
                has_normal = True

        return MessageSenseResult(
            images=detected_images,
            faces=protocol_faces,
            has_stickers=has_stickers,
            has_normal_photos=has_normal,
            has_animated_stickers=has_animated_stickers,
        )
