"""
配置管理模块

负责加载、保存和管理应用程序配置。支持从配置文件和命令行读取配置。
设计为易于扩展，可以轻松添加新的配置项。

扩展点：
- 支持多种配置源（JSON、YAML、环境变量等）
- 可添加配置验证逻辑
- 支持热重载配置
- 可集成远程配置服务
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class OCRConfig:
    """OCR 识别配置
    
    扩展点：
    - 可添加更多 OCR 引擎配置（如 EasyOCR, PaddleOCR）
    - 支持自定义 OCR 模型路径
    - 可添加预处理参数（二值化、去噪等）
    """
    engine: str = "tesseract"  # OCR 引擎：tesseract, windows_ocr, easyocr, ai_vision
    language: str = "chi_sim"  # 识别语言
    confidence_threshold: float = 0.6  # 置信度阈值
    tesseract_path: Optional[str] = None  # Tesseract 可执行文件路径
    tesseract_psm: int = 7  # PSM 模式（字幕通常为单行文本，推荐 7）
    
    # 图像预处理（提升字幕识别效果）
    preprocess_enable: bool = True  # 是否启用预处理
    preprocess_grayscale: bool = True  # 灰度化
    preprocess_threshold: int = 160  # 二值化阈值（0-255）
    preprocess_invert: bool = False  # 反色（白底黑字时可打开）
    preprocess_auto_threshold: bool = True  # 自适应阈值（优先于固定阈值）
    preprocess_scale: float = 2.0  # 放大倍率（提升小字体识别）
    
    # AI 扩展配置（预留）
    ai_model: Optional[str] = None  # AI 模型名称（如 GPT-4 Vision）
    ai_api_key: Optional[str] = None  # AI API 密钥
    ai_endpoint: Optional[str] = None  # AI 服务端点


@dataclass
class TTSConfig:
    """TTS 语音合成配置
    
    扩展点：
    - 支持多种 TTS 引擎（Azure TTS, Google TTS, 本地 TTS）
    - 可配置语音情感、语速、音调等
    - 支持 AI 语音克隆
    """
    engine: str = "edge-tts"  # TTS 引擎：edge-tts, azure-tts, google-tts, ai_voice
    voice: str = "zh-CN-XiaoxiaoNeural"  # 语音名称
    rate: str = "+0%"  # 语速（-50% 到 +50%）
    volume: str = "+0%"  # 音量（-50% 到 +50%）
    pitch: str = "+0Hz"  # 音调
    fallback_engine: Optional[str] = "pyttsx3"  # 失败时回退引擎
    fallback_voice: Optional[str] = None  # 回退引擎语音
    fallback_rate: Optional[int] = None  # 回退引擎语速
    
    # AI 扩展配置（预留）
    ai_voice_model: Optional[str] = None  # AI 语音模型
    ai_api_key: Optional[str] = None  # AI API 密钥
    voice_clone_sample: Optional[str] = None  # 语音克隆样本路径


@dataclass
class CaptureConfig:
    """屏幕捕获配置"""
    region: Optional[Dict[str, int]] = None  # 捕获区域 {"x": 0, "y": 0, "width": 800, "height": 100}
    interval: float = 1.0  # 捕获间隔（秒）
    method: str = "mss"  # 捕获方法：mss, pillow, pyautogui
    
    def __post_init__(self):
        if self.region is None:
            self.region = {"x": 0, "y": 0, "width": 800, "height": 100}


@dataclass
class GUIConfig:
    """GUI 界面配置"""
    framework: str = "tkinter"  # GUI 框架：tkinter, pyqt5
    theme: str = "default"  # 主题
    window_size: Dict[str, int] = field(default_factory=lambda: {"width": 600, "height": 400})
    always_on_top: bool = False  # 窗口置顶
    start_minimized: bool = False  # 启动时最小化


@dataclass
class HotkeyConfig:
    """热键配置
    
    扩展点：
    - 支持更多快捷键
    - 可配置全局热键
    """
    enable: bool = True
    start_stop: str = "F9"  # 启动/停止热键
    pause_resume: str = "F10"  # 暂停/继续热键


@dataclass
class AppConfig:
    """应用程序总配置
    
    统一管理所有子配置模块。
    """
    ocr: OCRConfig = field(default_factory=OCRConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    gui: GUIConfig = field(default_factory=GUIConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    
    # 全局配置
    log_level: str = "INFO"  # 日志级别
    log_file: Optional[str] = None  # 日志文件路径
    auto_start: bool = False  # 启动时自动开始识别


class ConfigManager:
    """配置管理器
    
    负责配置的加载、保存和访问。
    
    扩展点：
    - 支持配置加密
    - 支持配置迁移（版本升级）
    - 支持配置同步（多设备）
    - 可添加配置变更监听器
    """
    
    DEFAULT_CONFIG_PATH = Path("config/config.json")
    
    def __init__(self, config_path: Optional[Path] = None):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为 config/config.json
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config: AppConfig = AppConfig()
        self._load_config()
    
    def _load_config(self) -> None:
        """从文件加载配置
        
        如果配置文件不存在，使用默认配置并创建文件。
        """
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config = self._dict_to_config(data)
                logger.info(f"配置已从 {self.config_path} 加载")
            else:
                logger.info("配置文件不存在，使用默认配置")
                self.save_config()  # 创建默认配置文件
        except Exception as e:
            logger.error(f"加载配置失败: {e}，使用默认配置")
            self.config = AppConfig()
    
    def _dict_to_config(self, data: Dict[str, Any]) -> AppConfig:
        """将字典转换为配置对象
        
        Args:
            data: 配置字典
            
        Returns:
            配置对象
        """
        return AppConfig(
            ocr=OCRConfig(**data.get('ocr', {})),
            tts=TTSConfig(**data.get('tts', {})),
            capture=CaptureConfig(**data.get('capture', {})),
            gui=GUIConfig(**data.get('gui', {})),
            hotkey=HotkeyConfig(**data.get('hotkey', {})),
            log_level=data.get('log_level', 'INFO'),
            log_file=data.get('log_file'),
            auto_start=data.get('auto_start', False)
        )
    
    def save_config(self) -> None:
        """保存配置到文件"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config_to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"配置已保存到 {self.config_path}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
    
    def _config_to_dict(self) -> Dict[str, Any]:
        """将配置对象转换为字典
        
        Returns:
            配置字典
        """
        return {
            'ocr': asdict(self.config.ocr),
            'tts': asdict(self.config.tts),
            'capture': asdict(self.config.capture),
            'gui': asdict(self.config.gui),
            'hotkey': asdict(self.config.hotkey),
            'log_level': self.config.log_level,
            'log_file': self.config.log_file,
            'auto_start': self.config.auto_start
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项
        
        支持点号分隔的嵌套键，如 'ocr.language'
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config
        try:
            for k in keys:
                value = getattr(value, k)
            return value
        except AttributeError:
            return default
    
    def set(self, key: str, value: Any) -> None:
        """设置配置项
        
        支持点号分隔的嵌套键，如 'ocr.language'
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config_obj = self.config
        try:
            for k in keys[:-1]:
                config_obj = getattr(config_obj, k)
            setattr(config_obj, keys[-1], value)
        except AttributeError as e:
            logger.error(f"设置配置项失败: {e}")


# 全局配置实例
config_manager: Optional[ConfigManager] = None


def init_config(config_path: Optional[Path] = None) -> ConfigManager:
    """初始化全局配置
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置管理器实例
    """
    global config_manager
    config_manager = ConfigManager(config_path)
    return config_manager


def get_config() -> ConfigManager:
    """获取全局配置管理器
    
    Returns:
        配置管理器实例
    """
    global config_manager
    if config_manager is None:
        config_manager = init_config()
    return config_manager
