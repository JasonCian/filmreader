"""
FilmReader - 字幕朗读助手

一个用于观看非本地化视频时自动识别屏幕字幕并语音朗读的应用程序。

主要功能：
- 屏幕区域捕获
- OCR 字幕识别（支持多种引擎：Tesseract、Windows OCR、AI Vision 等）
- TTS 语音合成（支持 Edge TTS、Azure TTS、AI Voice 等）
- 图形用户界面（tkinter）

扩展点：
- 支持更多 OCR 和 TTS 引擎
- 支持插件系统
- 支持远程控制
- 支持多语言界面

作者: FilmReader Team
版本: 0.1.0
许可: MIT
"""

__version__ = "0.1.0"
__author__ = "FilmReader Team"
__license__ = "MIT"

# 导出主要类和函数
from .main import FilmReaderApp, main
from .config import ConfigManager, get_config, init_config
from .ocr import SubtitleRecognizer, create_ocr_engine
from .tts import SpeechSynthesizer, create_tts_engine
from .gui import FilmReaderGUI

__all__ = [
    "FilmReaderApp",
    "main",
    "ConfigManager",
    "get_config",
    "init_config",
    "SubtitleRecognizer",
    "create_ocr_engine",
    "SpeechSynthesizer",
    "create_tts_engine",
    "FilmReaderGUI",
]
