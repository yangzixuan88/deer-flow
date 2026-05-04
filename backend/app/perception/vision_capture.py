import io
import base64
import logging
try:
    import mss
    from PIL import Image
    HAS_VISION_DEPS = True
except ImportError:
    HAS_VISION_DEPS = False

logger = logging.getLogger(__name__)

class VisionCaptureEngine:
    """
    视觉感知捕捉模块 (Vision M06)
    捕获系统当前屏幕，提供大模型能够直接消费的 Base64 视觉片段。
    """
    @staticmethod
    def capture_screen_base64(quality: int = 70, max_width: int = 1920) -> str:
        """
        截取当前系统主屏幕，并压缩编码为 Base64 JPEG
        """
        if not HAS_VISION_DEPS:
            logger.error("Vision capture failed: mss and Pillow are required.")
            return ""

        try:
            with mss.mss() as sct:
                # 兼容多屏，优先抓取主屏幕 (monitor 1)
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                sct_img = sct.grab(monitor)
                
                # 转换至 PIL Image 格式方便切分与压缩
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                # 尺寸限缩，防止大模型 token 开销过高
                if img.width > max_width:
                    ratio = max_width / float(img.width)
                    new_height = int((float(img.height) * float(ratio)))
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                
                # 保存至内存流缓冲
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality)
                img_bytes = buffer.getvalue()
                
                # 转换为 Base64，满足大部分多模态 LLM 传入格式
                b64_str = base64.b64encode(img_bytes).decode("utf-8")
                return b64_str
        except Exception as e:
            logger.error(f"Vision capture execution error: {e}")
            return ""

# 提供全局单例引擎
vision_engine = VisionCaptureEngine()
