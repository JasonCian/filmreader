"""
TTS 语音合成模块

负责将文本转换为语音并播放。采用策略模式设计，支持多种 TTS 引擎。

扩展点：
- 添加更多 TTS 引擎（Azure TTS, Google TTS, 本地 TTS 等）
- 支持语音情感、风格控制
- 支持 AI 语音克隆
- 支持语音后处理（降噪、音效等）
- 添加语音队列管理
"""

import asyncio
import logging
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
import threading
import queue

try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import pygame
    pygame.mixer.init()
except ImportError:
    pygame = None

try:
    from pydub import AudioSegment
    from pydub.playback import play
except ImportError:
    AudioSegment = None
    play = None

logger = logging.getLogger(__name__)


class AudioPlayer:
    """音频播放器
    
    负责播放音频文件。支持多种播放方式。
    
    扩展点：
    - 支持音频流播放
    - 添加播放队列管理
    - 支持音量控制、淡入淡出等效果
    """
    
    def __init__(self, method: str = "pygame"):
        """初始化音频播放器
        
        Args:
            method: 播放方法，支持 'pygame', 'pydub'
        """
        self.method = method
        self._validate_dependencies()
        self.is_playing = False
    
    def _validate_dependencies(self) -> None:
        """验证依赖库是否已安装"""
        if self.method == "pygame" and pygame is None:
            raise ImportError("请安装 pygame 库: pip install pygame")
        elif self.method == "pydub" and AudioSegment is None:
            raise ImportError("请安装 pydub 库: pip install pydub")
    
    def play(self, audio_path: Path) -> None:
        """播放音频文件
        
        Args:
            audio_path: 音频文件路径
        """
        try:
            if self.method == "pygame":
                self._play_pygame(audio_path)
            elif self.method == "pydub":
                self._play_pydub(audio_path)
            else:
                logger.error(f"不支持的播放方法: {self.method}")
        except Exception as e:
            logger.error(f"播放音频失败: {e}")
    
    def _play_pygame(self, audio_path: Path) -> None:
        """使用 pygame 播放音频（推荐）
        
        Args:
            audio_path: 音频文件路径
        """
        self.is_playing = True
        pygame.mixer.music.load(str(audio_path))
        pygame.mixer.music.play()
        
        # 等待播放完成
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        
        self.is_playing = False
    
    def _play_pydub(self, audio_path: Path) -> None:
        """使用 pydub 播放音频
        
        Args:
            audio_path: 音频文件路径
        """
        self.is_playing = True
        audio = AudioSegment.from_file(str(audio_path))
        play(audio)
        self.is_playing = False
    
    def stop(self) -> None:
        """停止播放"""
        if self.method == "pygame" and pygame:
            pygame.mixer.music.stop()
        self.is_playing = False


class TTSEngine(ABC):
    """TTS 引擎抽象基类
    
    定义 TTS 引擎的标准接口。所有 TTS 实现都应继承此类。
    
    扩展点：
    - 实现新的 TTS 引擎（继承此类并实现 synthesize 方法）
    - 添加批量合成接口
    - 添加异步合成支持
    """
    
    @abstractmethod
    def synthesize(self, text: str, output_path: Path) -> bool:
        """合成语音
        
        Args:
            text: 要合成的文本
            output_path: 输出音频文件路径
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查 TTS 引擎是否可用
        
        Returns:
            是否可用
        """
        pass


class EdgeTTS(TTSEngine):
    """Edge TTS 引擎
    
    使用 Microsoft Edge 的在线 TTS 服务。
    
    优点：
    - 免费
    - 语音质量高
    - 支持多种语言和语音
    
    缺点：
    - 需要网络连接
    - 可能有使用限制
    
    扩展点：
    - 支持更多语音参数（情感、风格等）
    - 添加请求重试机制
    - 支持语音缓存
    """
    
    def __init__(self, 
                 voice: str = "en-US-AriaNeural",
                 rate: str = "+0%",
                 volume: str = "+0%",
                 pitch: str = "+0Hz"):
        """初始化 Edge TTS
        
        Args:
            voice: 语音名称（如 'zh-CN-XiaoxiaoNeural', 'en-US-AriaNeural'）
            rate: 语速（-50% 到 +50%）
            volume: 音量（-50% 到 +50%）
            pitch: 音调（-50Hz 到 +50Hz）
        """
        if edge_tts is None:
            raise ImportError("请安装 edge-tts 库: pip install edge-tts")
        
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch
    
    def synthesize(self, text: str, output_path: Path) -> bool:
        """合成语音
        
        Args:
            text: 要合成的文本
            output_path: 输出音频文件路径
            
        Returns:
            是否成功
        """
        try:
            # Edge TTS 是异步的，需要在事件循环中运行
            asyncio.run(self._async_synthesize(text, output_path))
            return True
        except Exception as e:
            if "403" in str(e):
                logger.error("Edge TTS 返回 403，可能是网络被限制或服务端拒绝请求")
                logger.error("建议：更新 edge-tts 版本，或切换到离线 TTS 引擎")
            logger.error(f"Edge TTS 合成失败: {e}")
            return False
    
    async def _async_synthesize(self, text: str, output_path: Path) -> None:
        """异步合成语音
        
        Args:
            text: 要合成的文本
            output_path: 输出音频文件路径
        """
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
            pitch=self.pitch
        )
        await communicate.save(str(output_path))
    
    def is_available(self) -> bool:
        """检查 Edge TTS 是否可用
        
        Returns:
            是否可用
        """
        return edge_tts is not None
    
    @staticmethod
    async def list_voices() -> list:
        """列出所有可用的语音
        
        Returns:
            语音列表
        """
        voices = await edge_tts.list_voices()
        return voices


class AzureTTS(TTSEngine):
    """Azure TTS 引擎（预留接口）
    
    使用 Microsoft Azure 的 TTS 服务。
    
    扩展点：
    - 实现 Azure TTS API 调用
    - 支持 SSML（语音合成标记语言）
    - 支持神经语音
    
    注意：需要 Azure 订阅和 API 密钥
    """
    
    def __init__(self, api_key: str, region: str = "eastus"):
        """初始化 Azure TTS
        
        Args:
            api_key: Azure API 密钥
            region: Azure 区域
        """
        self.api_key = api_key
        self.region = region
        logger.warning("Azure TTS 为预留接口，暂未实现")
    
    def synthesize(self, text: str, output_path: Path) -> bool:
        """合成语音
        
        Args:
            text: 要合成的文本
            output_path: 输出音频文件路径
            
        Returns:
            是否成功
        """
        # TODO: 实现 Azure TTS 合成
        logger.warning("Azure TTS 合成暂未实现")
        return False
    
    def is_available(self) -> bool:
        """检查 Azure TTS 是否可用
        
        Returns:
            是否可用
        """
        return False


class Pyttsx3TTS(TTSEngine):
    """pyttsx3 离线 TTS 引擎
    
    基于 Windows SAPI，无需联网。
    
    注意：需要安装 pyttsx3：pip install pyttsx3
    """
    
    def __init__(self, voice: Optional[str] = None, rate: Optional[int] = None):
        if pyttsx3 is None:
            raise ImportError("请安装 pyttsx3: pip install pyttsx3")
        self.voice = voice
        self.rate = rate
    
    def synthesize(self, text: str, output_path: Path) -> bool:
        try:
            engine = pyttsx3.init()
            if self.rate is not None:
                engine.setProperty('rate', self.rate)
            if self.voice:
                engine.setProperty('voice', self.voice)
            # 保存为 wav 文件
            if output_path.suffix.lower() != ".wav":
                output_path = output_path.with_suffix(".wav")
            engine.save_to_file(text, str(output_path))
            engine.runAndWait()
            return True
        except Exception as e:
            logger.error(f"pyttsx3 合成失败: {e}")
            return False
    
    def is_available(self) -> bool:
        return pyttsx3 is not None


class AIVoiceTTS(TTSEngine):
    """AI 语音合成引擎（预留接口）
    
    支持使用 AI 模型进行语音合成，包括语音克隆。
    
    扩展点：
    - 支持 OpenAI TTS
    - 支持 ElevenLabs
    - 支持本地部署的语音模型（如 Bark, VALL-E）
    - 支持语音克隆（从样本学习语音特征）
    """
    
    def __init__(self, 
                 model: str = "openai-tts",
                 api_key: Optional[str] = None,
                 voice_sample: Optional[Path] = None):
        """初始化 AI 语音 TTS
        
        Args:
            model: AI 模型名称
            api_key: API 密钥
            voice_sample: 语音克隆样本路径
        """
        self.model = model
        self.api_key = api_key
        self.voice_sample = voice_sample
        logger.warning("AI Voice TTS 为预留接口，暂未实现")
    
    def synthesize(self, text: str, output_path: Path) -> bool:
        """合成语音
        
        Args:
            text: 要合成的文本
            output_path: 输出音频文件路径
            
        Returns:
            是否成功
        """
        # TODO: 实现 AI 语音合成
        # 可以调用 OpenAI TTS API, ElevenLabs API 等
        logger.warning("AI Voice TTS 合成暂未实现")
        return False
    
    def is_available(self) -> bool:
        """检查 AI Voice TTS 是否可用
        
        Returns:
            是否可用
        """
        return False


class SpeechSynthesizer:
    """语音合成器
    
    整合 TTS 引擎和音频播放器，提供完整的语音合成和播放功能。
    
    扩展点：
    - 添加语音队列（异步合成和播放）
    - 支持语音缓存（避免重复合成）
    - 添加播放控制（暂停、继续、停止）
    - 支持语音后处理
    """
    
    def __init__(self, 
                 tts_engine: TTSEngine,
                 player_method: str = "pygame",
                 cache_dir: Optional[Path] = None,
                 fallback_engine: Optional[TTSEngine] = None):
        """初始化语音合成器
        
        Args:
            tts_engine: TTS 引擎实例
            player_method: 音频播放方法
            cache_dir: 音频缓存目录
        """
        self.tts_engine = tts_engine
        self.fallback_engine = fallback_engine
        self.audio_player = AudioPlayer(method=player_method)
        self.cache_dir = cache_dir or Path(tempfile.gettempdir()) / "filmreader_audio"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 语音队列
        self.speech_queue = queue.Queue()
        self.is_running = False
        self.worker_thread: Optional[threading.Thread] = None
    
    def _get_audio_path(self, text: str, extension: str) -> Path:
        """根据文本和扩展名生成缓存路径"""
        ext = extension.lstrip(".")
        return self.cache_dir / f"speech_{hash(text)}.{ext}"

    def speak(self, text: str, blocking: bool = True) -> bool:
        """朗读文本
        
        Args:
            text: 要朗读的文本
            blocking: 是否阻塞等待播放完成
            
        Returns:
            是否成功
        """
        if not text.strip():
            return False
        
        try:
            # 选择主引擎扩展名
            main_ext = "wav" if isinstance(self.tts_engine, Pyttsx3TTS) else "mp3"
            audio_path = self._get_audio_path(text, main_ext)
            
            # 检查缓存并合成
            if not audio_path.exists():
                logger.info(f"合成语音: {text}")
                if not self.tts_engine.synthesize(text, audio_path):
                    # 主引擎失败，尝试回退
                    if self.fallback_engine:
                        logger.warning("主 TTS 引擎失败，尝试回退引擎")
                        fallback_ext = "wav" if isinstance(self.fallback_engine, Pyttsx3TTS) else "mp3"
                        fallback_path = self._get_audio_path(text, fallback_ext)
                        if not fallback_path.exists():
                            if not self.fallback_engine.synthesize(text, fallback_path):
                                return False
                        audio_path = fallback_path
                    else:
                        return False
            else:
                logger.debug(f"使用缓存的语音: {text}")
            
            # 播放音频
            if blocking:
                self.audio_player.play(audio_path)
            else:
                # 异步播放
                thread = threading.Thread(target=self.audio_player.play, args=(audio_path,))
                thread.daemon = True
                thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"朗读失败: {e}")
            return False
    
    def start_queue_worker(self) -> None:
        """启动语音队列工作线程
        
        用于异步处理语音队列。
        """
        if self.is_running:
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._queue_worker)
        self.worker_thread.daemon = True
        self.worker_thread.start()
    
    def stop_queue_worker(self) -> None:
        """停止语音队列工作线程"""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2)
    
    def _queue_worker(self) -> None:
        """语音队列工作函数"""
        while self.is_running:
            try:
                text = self.speech_queue.get(timeout=0.5)
                self.speak(text, blocking=True)
                self.speech_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"队列工作线程错误: {e}")
    
    def enqueue_speech(self, text: str) -> None:
        """将文本加入语音队列
        
        Args:
            text: 要朗读的文本
        """
        if text.strip():
            self.speech_queue.put(text)
    
    def clear_queue(self) -> None:
        """清空语音队列"""
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
            except queue.Empty:
                break
    
    def stop_speaking(self) -> None:
        """停止当前朗读"""
        self.audio_player.stop()
        self.clear_queue()
    
    def clear_cache(self) -> None:
        """清空音频缓存"""
        try:
            for file in self.cache_dir.glob("*.mp3"):
                file.unlink()
            logger.info("音频缓存已清空")
        except Exception as e:
            logger.error(f"清空缓存失败: {e}")


def create_tts_engine(engine_type: str, **kwargs) -> TTSEngine:
    """TTS 引擎工厂函数
    
    根据配置创建相应的 TTS 引擎。
    
    Args:
        engine_type: 引擎类型（'edge-tts', 'azure-tts', 'ai_voice'）
        **kwargs: 引擎特定参数
        
    Returns:
        TTS 引擎实例
        
    扩展点：
    - 添加新的引擎类型
    - 支持引擎自动选择（根据网络状况、系统环境等）
    """
    if engine_type == "edge-tts":
        return EdgeTTS(
            voice=kwargs.get("voice", "en-US-AriaNeural"),
            rate=kwargs.get("rate", "+0%"),
            volume=kwargs.get("volume", "+0%"),
            pitch=kwargs.get("pitch", "+0Hz")
        )
    elif engine_type == "azure-tts":
        return AzureTTS(
            api_key=kwargs.get("api_key"),
            region=kwargs.get("region", "eastus")
        )
    elif engine_type == "ai_voice":
        return AIVoiceTTS(
            model=kwargs.get("ai_voice_model", "openai-tts"),
            api_key=kwargs.get("ai_api_key"),
            voice_sample=kwargs.get("voice_clone_sample")
        )
    elif engine_type == "pyttsx3":
        return Pyttsx3TTS(
            voice=kwargs.get("voice"),
            rate=kwargs.get("rate")
        )
    else:
        logger.warning(f"未知的 TTS 引擎类型: {engine_type}，使用 Edge TTS")
        return EdgeTTS(voice=kwargs.get("voice", "en-US-AriaNeural"))


async def list_available_voices() -> list:
    """列出所有可用的语音（Edge TTS）
    
    Returns:
        语音列表
    """
    try:
        return await EdgeTTS.list_voices()
    except Exception as e:
        logger.error(f"获取语音列表失败: {e}")
        return []
