"""
OCR 识别模块

负责屏幕捕获和字幕文本识别。采用策略模式设计，支持多种 OCR 引擎。

扩展点：
- 添加更多 OCR 引擎（EasyOCR, PaddleOCR, Windows OCR, AI Vision 等）
- 支持图像预处理（去噪、二值化、倾斜校正等）
- 支持字幕区域自动检测
- 支持多语言混合识别
- 集成 AI 视觉模型进行更智能的识别
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from dataclasses import dataclass
import time

try:
    from PIL import Image, ImageGrab, ImageOps
    import numpy as np
except ImportError:
    Image = None
    ImageGrab = None
    ImageOps = None
    np = None

try:
    import mss
except ImportError:
    mss = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

logger = logging.getLogger(__name__)


class ScreenCapture:
    """屏幕捕获类
    
    负责捕获指定区域的屏幕内容。支持多种捕获方式。
    
    扩展点：
    - 支持视频流捕获（从摄像头或视频文件）
    - 支持多显示器
    - 添加捕获性能监控
    """
    
    def __init__(self, method: str = "mss"):
        """初始化屏幕捕获器
        
        Args:
            method: 捕获方法，支持 'mss', 'pillow', 'pyautogui'
        """
        self.method = method
        self._validate_dependencies()
    
    def _validate_dependencies(self) -> None:
        """验证依赖库是否已安装"""
        if self.method == "mss" and mss is None:
            raise ImportError("请安装 mss 库: pip install mss")
        elif self.method in ["pillow", "pyautogui"] and Image is None:
            raise ImportError("请安装 Pillow 库: pip install Pillow")
    
    def capture(self, region: Optional[Dict[str, int]] = None) -> Optional[Image.Image]:
        """捕获屏幕区域
        
        Args:
            region: 捕获区域 {"x": x, "y": y, "width": w, "height": h}
                   如果为 None，捕获全屏
        
        Returns:
            PIL Image 对象，失败返回 None
        """
        try:
            if self.method == "mss":
                return self._capture_mss(region)
            elif self.method == "pillow":
                return self._capture_pillow(region)
            else:
                logger.error(f"不支持的捕获方法: {self.method}")
                return None
        except Exception as e:
            logger.error(f"屏幕捕获失败: {e}")
            return None
    
    def _capture_mss(self, region: Optional[Dict[str, int]]) -> Optional[Image.Image]:
        """使用 mss 库捕获屏幕（推荐，性能最好）
        
        Args:
            region: 捕获区域
            
        Returns:
            PIL Image 对象
        """
        with mss.mss() as sct:
            if region:
                monitor = {
                    "top": region["y"],
                    "left": region["x"],
                    "width": region["width"],
                    "height": region["height"]
                }
            else:
                monitor = sct.monitors[1]  # 主显示器
            
            screenshot = sct.grab(monitor)
            return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
    
    def _capture_pillow(self, region: Optional[Dict[str, int]]) -> Optional[Image.Image]:
        """使用 Pillow 库捕获屏幕
        
        Args:
            region: 捕获区域
            
        Returns:
            PIL Image 对象
        """
        if region:
            bbox = (
                region["x"],
                region["y"],
                region["x"] + region["width"],
                region["y"] + region["height"]
            )
            return ImageGrab.grab(bbox=bbox)
        else:
            return ImageGrab.grab()


class OCREngine(ABC):
    """OCR 引擎抽象基类
    
    定义 OCR 引擎的标准接口。所有 OCR 实现都应继承此类。
    
    扩展点：
    - 实现新的 OCR 引擎（继承此类并实现 recognize 方法）
    - 添加批量识别接口
    - 添加异步识别支持
    """
    
    @abstractmethod
    def recognize(self, image: Image.Image) -> str:
        """识别图像中的文本
        
        Args:
            image: PIL Image 对象
            
        Returns:
            识别出的文本字符串
        """
        pass
    
    @abstractmethod
    def get_confidence(self, image: Image.Image) -> float:
        """获取识别置信度
        
        Args:
            image: PIL Image 对象
            
        Returns:
            置信度 (0-1)
        """
        pass


class TesseractOCR(OCREngine):
    """Tesseract OCR 引擎
    
    使用 Tesseract 进行文本识别。
    
    扩展点：
    - 支持自定义训练模型
    - 添加图像预处理流程
    - 支持 PSM (Page Segmentation Mode) 配置
    """
    
    def __init__(self, language: str = "eng", tesseract_path: Optional[str] = None, psm: int = 7):
        """初始化 Tesseract OCR
        
        Args:
            language: 识别语言代码（如 'eng', 'chi_sim', 'jpn'）
            tesseract_path: Tesseract 可执行文件路径
        """
        if pytesseract is None:
            raise ImportError("请安装 pytesseract: pip install pytesseract")
        
        self.language = language
        self.psm = psm
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        # 测试 Tesseract 是否可用
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            logger.error(f"Tesseract 不可用: {e}")
            logger.error("=" * 60)
            logger.error("请安装 Tesseract OCR 或配置 tesseract_path")
            logger.error("详细安装指南请查看: INSTALL_TESSERACT.md")
            logger.error("快速安装：")
            logger.error("1. 下载: https://github.com/UB-Mannheim/tesseract/wiki")
            logger.error("2. 安装时选择中文语言包")
            logger.error("3. 添加到系统 PATH 或在配置文件中指定路径")
            logger.error("=" * 60)
            raise RuntimeError("Tesseract OCR 未正确安装或配置")
    
    def recognize(self, image: Image.Image) -> str:
        """识别图像中的文本
        
        Args:
            image: PIL Image 对象
            
        Returns:
            识别出的文本字符串
        """
        try:
            # 配置 Tesseract
            config = f'--psm {self.psm} --oem 3'  # PSM 7: 单行文本更适合字幕
            text = pytesseract.image_to_string(image, lang=self.language, config=config)
            return text.strip()
        except Exception as e:
            logger.error(f"Tesseract 识别失败: {e}")
            return ""
    
    def get_confidence(self, image: Image.Image) -> float:
        """获取识别置信度
        
        Args:
            image: PIL Image 对象
            
        Returns:
            平均置信度 (0-1)
        """
        try:
            data = pytesseract.image_to_data(image, lang=self.language, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if conf != '-1']
            if confidences:
                return sum(confidences) / len(confidences) / 100.0
            return 0.0
        except Exception as e:
            logger.error(f"获取置信度失败: {e}")
            return 0.0


class WindowsOCR(OCREngine):
    """Windows 内置 OCR 引擎
    
    使用 Windows 10/11 内置的 OCR API（需要 Windows.Media.Ocr）
    
    扩展点：
    - 支持更多 Windows OCR 配置
    - 添加离线模型支持
    
    注意：需要安装 winrt 库: pip install winrt
    """
    
    def __init__(self, language: str = "en-US"):
        """初始化 Windows OCR
        
        Args:
            language: 识别语言（如 'en-US', 'zh-CN', 'ja-JP'）
        """
        self.language = language
        # TODO: 实现 Windows OCR 初始化
        logger.warning("Windows OCR 暂未实现")
    
    def recognize(self, image: Image.Image) -> str:
        """识别图像中的文本
        
        Args:
            image: PIL Image 对象
            
        Returns:
            识别出的文本字符串
        """
        # TODO: 实现 Windows OCR 识别
        logger.warning("Windows OCR 识别暂未实现")
        return ""
    
    def get_confidence(self, image: Image.Image) -> float:
        """获取识别置信度
        
        Args:
            image: PIL Image 对象
            
        Returns:
            置信度 (0-1)
        """
        return 0.0


class AIVisionOCR(OCREngine):
    """AI 视觉识别引擎（预留接口）
    
    支持调用 AI 视觉模型进行更智能的字幕识别。
    
    扩展点：
    - 支持 GPT-4 Vision
    - 支持 Claude Vision
    - 支持本地部署的视觉模型
    - 可添加上下文理解、翻译等功能
    """
    
    def __init__(self, model: str = "gpt-4-vision", api_key: Optional[str] = None):
        """初始化 AI 视觉 OCR
        
        Args:
            model: AI 模型名称
            api_key: API 密钥
        """
        self.model = model
        self.api_key = api_key
        logger.warning("AI Vision OCR 为预留接口，暂未实现")
    
    def recognize(self, image: Image.Image) -> str:
        """识别图像中的文本
        
        Args:
            image: PIL Image 对象
            
        Returns:
            识别出的文本字符串
        """
        # TODO: 实现 AI 视觉识别
        # 可以调用 OpenAI GPT-4 Vision API, Claude Vision API 等
        logger.warning("AI Vision OCR 识别暂未实现")
        return ""
    
    def get_confidence(self, image: Image.Image) -> float:
        """获取识别置信度
        
        Args:
            image: PIL Image 对象
            
        Returns:
            置信度 (0-1)
        """
        return 0.0


class SubtitleRecognizer:
    """字幕识别器
    
    整合屏幕捕获和 OCR 识别，提供完整的字幕识别功能。
    
    扩展点：
    - 添加字幕去重逻辑（避免重复朗读）
    - 支持字幕位置跟踪（自动调整识别区域）
    - 添加识别结果缓存
    - 支持多区域并行识别
    """
    
    def __init__(self, 
                 ocr_engine: OCREngine,
                 capture_method: str = "mss",
                 confidence_threshold: float = 0.6,
                 preprocess_enable: bool = True,
                 preprocess_grayscale: bool = True,
                 preprocess_threshold: int = 160,
                 preprocess_invert: bool = False,
                 preprocess_auto_threshold: bool = True,
                 preprocess_scale: float = 2.0):
        """初始化字幕识别器
        
        Args:
            ocr_engine: OCR 引擎实例
            capture_method: 屏幕捕获方法
            confidence_threshold: 置信度阈值，低于此值的识别结果将被忽略
        """
        self.ocr_engine = ocr_engine
        self.screen_capture = ScreenCapture(method=capture_method)
        self.confidence_threshold = confidence_threshold
        self.last_text = ""  # 上次识别的文本（用于去重）
        self.last_capture_time = 0.0
        
        # 预处理配置
        self.preprocess_enable = preprocess_enable
        self.preprocess_grayscale = preprocess_grayscale
        self.preprocess_threshold = preprocess_threshold
        self.preprocess_invert = preprocess_invert
        self.preprocess_auto_threshold = preprocess_auto_threshold
        self.preprocess_scale = preprocess_scale

    def _otsu_threshold(self, image: Image.Image) -> Optional[int]:
        """使用 Otsu 方法估计阈值（需要 numpy）"""
        if np is None:
            return None
        try:
            data = np.array(image).flatten()
            # 直方图
            hist, _ = np.histogram(data, bins=256, range=(0, 256))
            total = data.size
            sum_total = np.dot(np.arange(256), hist)

            sum_b = 0.0
            w_b = 0.0
            var_max = 0.0
            threshold = 0
            for t in range(256):
                w_b += hist[t]
                if w_b == 0:
                    continue
                w_f = total - w_b
                if w_f == 0:
                    break
                sum_b += t * hist[t]
                m_b = sum_b / w_b
                m_f = (sum_total - sum_b) / w_f
                var_between = w_b * w_f * (m_b - m_f) ** 2
                if var_between > var_max:
                    var_max = var_between
                    threshold = t
            return int(threshold)
        except Exception as e:
            logger.error(f"Otsu 阈值计算失败: {e}")
            return None

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """对图像进行预处理以提升 OCR 效果"""
        if not self.preprocess_enable:
            return image
        
        try:
            processed = image

            # 放大（提升小字体识别）
            if self.preprocess_scale and self.preprocess_scale > 1.0:
                new_w = int(processed.width * self.preprocess_scale)
                new_h = int(processed.height * self.preprocess_scale)
                processed = processed.resize((new_w, new_h), Image.LANCZOS)
            
            # 灰度化
            if self.preprocess_grayscale:
                processed = ImageOps.grayscale(processed)
            
            # 二值化
            threshold = None
            if self.preprocess_auto_threshold:
                threshold = self._otsu_threshold(processed)
            if threshold is None:
                threshold = max(0, min(255, int(self.preprocess_threshold)))
            processed = processed.point(lambda p: 255 if p > threshold else 0)
            
            # 反色
            if self.preprocess_invert:
                processed = ImageOps.invert(processed)
            
            return processed
        except Exception as e:
            logger.error(f"图像预处理失败: {e}")
            return image
    
    def recognize_subtitle(self, region: Optional[Dict[str, int]] = None) -> "RecognitionResult":
        """识别字幕
        
        Args:
            region: 捕获区域
            
        Returns:
            识别结果对象
        """
        try:
            # 捕获屏幕
            image = self.screen_capture.capture(region)
            if image is None:
                return RecognitionResult(text="", confidence=0.0, skipped=True, reason="capture_failed")
            
            # 预处理（可选）
            processed_image = self._preprocess_image(image)
            
            # OCR 识别
            text = self.ocr_engine.recognize(processed_image)
            confidence = self.ocr_engine.get_confidence(processed_image)
            
            # 记录捕获时间
            self.last_capture_time = time.time()
            
            # 无文本
            if not text:
                return RecognitionResult(text="", confidence=confidence, skipped=True, reason="no_text")
            
            # 过滤低置信度结果
            if confidence < self.confidence_threshold:
                logger.debug(f"置信度过低 ({confidence:.2f}): {text}")
                return RecognitionResult(text="", confidence=confidence, skipped=True, reason="low_confidence")
            
            # 去除重复文本
            if text == self.last_text:
                logger.debug(f"重复文本，跳过: {text}")
                return RecognitionResult(text="", confidence=confidence, skipped=True, reason="duplicate")
            
            self.last_text = text
            return RecognitionResult(text=text, confidence=confidence, skipped=False, reason="ok")
            
        except Exception as e:
            logger.error(f"识别字幕失败: {e}")
            return RecognitionResult(text="", confidence=0.0, skipped=True, reason="error")
    
    def reset(self) -> None:
        """重置识别状态"""
        self.last_text = ""
        self.last_capture_time = 0.0


@dataclass
class RecognitionResult:
    """字幕识别结果
    
    Attributes:
        text: 识别文本
        confidence: 置信度 (0-1)
        skipped: 是否被跳过
        reason: 跳过原因（ok, capture_failed, no_text, low_confidence, duplicate, error）
    """
    text: str
    confidence: float
    skipped: bool
    reason: str


def create_ocr_engine(engine_type: str, **kwargs) -> OCREngine:
    """OCR 引擎工厂函数
    
    根据配置创建相应的 OCR 引擎。
    
    Args:
        engine_type: 引擎类型（'tesseract', 'windows_ocr', 'ai_vision'）
        **kwargs: 引擎特定参数
        
    Returns:
        OCR 引擎实例
        
    扩展点：
    - 添加新的引擎类型
    - 支持引擎自动选择（根据系统环境）
    """
    if engine_type == "tesseract":
        return TesseractOCR(
            language=kwargs.get("language", "eng"),
            tesseract_path=kwargs.get("tesseract_path"),
            psm=kwargs.get("psm", 7)
        )
    elif engine_type == "windows_ocr":
        return WindowsOCR(language=kwargs.get("language", "en-US"))
    elif engine_type == "ai_vision":
        return AIVisionOCR(
            model=kwargs.get("ai_model", "gpt-4-vision"),
            api_key=kwargs.get("ai_api_key")
        )
    else:
        logger.warning(f"未知的 OCR 引擎类型: {engine_type}，使用 Tesseract")
        return TesseractOCR(language=kwargs.get("language", "eng"))
