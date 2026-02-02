"""
主程序模块

整合所有组件，提供完整的应用程序流程控制。

扩展点：
- 添加更多工作模式（如录制模式、回放模式等）
- 支持插件系统
- 添加远程控制接口
- 支持多任务并行处理
"""

import logging
import time
import threading
from typing import Optional, Dict, Any
from pathlib import Path

from .config import get_config, init_config, ConfigManager
from .ocr import SubtitleRecognizer, create_ocr_engine
from .tts import SpeechSynthesizer, create_tts_engine
from .gui import FilmReaderGUI

logger = logging.getLogger(__name__)


class FilmReaderApp:
    """FilmReader 应用程序主类
    
    负责协调各个模块，实现完整的字幕识别和朗读功能。
    
    扩展点：
    - 添加事件系统（如识别事件、朗读事件等）
    - 支持多种运行模式（GUI 模式、命令行模式、服务模式）
    - 添加性能监控和统计
    - 支持远程控制和 API
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """初始化应用程序
        
        Args:
            config_path: 配置文件路径
        """
        # 初始化配置
        self.config_manager = init_config(config_path)
        
        # 初始化日志
        self._init_logging()
        
        # 初始化组件
        self.recognizer: Optional[SubtitleRecognizer] = None
        self.synthesizer: Optional[SpeechSynthesizer] = None
        self.gui: Optional[FilmReaderGUI] = None
        
        # 运行状态
        self.is_running = False
        self.is_paused = False
        self.worker_thread: Optional[threading.Thread] = None
        
        logger.info("FilmReader 应用程序已初始化")
    
    def _init_logging(self):
        """初始化日志系统"""
        log_level = getattr(logging, self.config_manager.config.log_level.upper())
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # 配置根日志记录器
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[
                logging.StreamHandler()
            ]
        )
        
        # 如果配置了日志文件，添加文件处理器
        if self.config_manager.config.log_file:
            log_file = Path(self.config_manager.config.log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(log_format))
            logging.getLogger().addHandler(file_handler)
            
            logger.info(f"日志将保存到: {log_file}")
    
    def _init_components(self, config: Dict[str, Any]):
        """初始化各个组件
        
        Args:
            config: 运行配置
        """
        try:
            # 创建 OCR 引擎
            ocr_config = self.config_manager.config.ocr
            ocr_engine = create_ocr_engine(
                config.get("ocr_engine", ocr_config.engine),
                language=config.get("ocr_language", ocr_config.language),
                tesseract_path=ocr_config.tesseract_path,
                psm=ocr_config.tesseract_psm,
                ai_model=ocr_config.ai_model,
                ai_api_key=ocr_config.ai_api_key
            )
            
            # 创建字幕识别器
            self.recognizer = SubtitleRecognizer(
                ocr_engine=ocr_engine,
                capture_method=self.config_manager.config.capture.method,
                confidence_threshold=ocr_config.confidence_threshold,
                preprocess_enable=config.get("preprocess_enable", ocr_config.preprocess_enable),
                preprocess_grayscale=config.get("preprocess_grayscale", ocr_config.preprocess_grayscale),
                preprocess_threshold=config.get("preprocess_threshold", ocr_config.preprocess_threshold),
                preprocess_invert=config.get("preprocess_invert", ocr_config.preprocess_invert),
                preprocess_auto_threshold=config.get("preprocess_auto_threshold", ocr_config.preprocess_auto_threshold),
                preprocess_scale=config.get("preprocess_scale", ocr_config.preprocess_scale)
            )
            logger.info(f"OCR 引擎已初始化: {config.get('ocr_engine', ocr_config.engine)}")
            
            # 创建 TTS 引擎
            tts_config = self.config_manager.config.tts
            tts_engine = create_tts_engine(
                config.get("tts_engine", tts_config.engine),
                voice=config.get("tts_voice", tts_config.voice),
                rate=tts_config.rate,
                volume=tts_config.volume,
                pitch=tts_config.pitch,
                ai_voice_model=tts_config.ai_voice_model,
                ai_api_key=tts_config.ai_api_key,
                voice_clone_sample=tts_config.voice_clone_sample
            )
            
            # 创建回退 TTS 引擎（可选）
            fallback_engine = None
            if tts_config.fallback_engine:
                try:
                    fallback_engine = create_tts_engine(
                        tts_config.fallback_engine,
                        voice=tts_config.fallback_voice,
                        rate=tts_config.fallback_rate
                    )
                except Exception as e:
                    logger.warning(f"回退 TTS 引擎不可用: {e}")
            
            # 创建语音合成器
            self.synthesizer = SpeechSynthesizer(
                tts_engine=tts_engine,
                fallback_engine=fallback_engine
            )
            self.synthesizer.start_queue_worker()
            logger.info(f"TTS 引擎已初始化: {config.get('tts_engine', tts_config.engine)}")
            
        except Exception as e:
            logger.error(f"初始化组件失败: {e}")
            
            # 如果是 Tesseract 问题，提供友好提示
            if "tesseract" in str(e).lower() or "Tesseract" in str(type(e).__name__):
                if self.gui:
                    self.gui.update_status("错误: Tesseract OCR 未安装")
                    self.gui.update_status("请查看 INSTALL_TESSERACT.md 获取安装指南")
                    self.gui.update_status("或在 GUI 中切换到其他 OCR 引擎")
            
            raise
    
    def start(self, config: Dict[str, Any]):
        """启动字幕识别和朗读
        
        Args:
            config: 运行配置，包含 region, ocr_engine, tts_engine, interval 等
        """
        if self.is_running:
            logger.warning("应用程序已在运行中")
            return
        
        try:
            # 初始化组件
            self._init_components(config)
            
            # 启动工作线程
            self.is_running = True
            self.is_paused = False
            self.worker_thread = threading.Thread(
                target=self._worker_loop,
                args=(config,)
            )
            self.worker_thread.daemon = True
            self.worker_thread.start()
            
            logger.info("字幕识别和朗读已启动")
            
        except Exception as e:
            logger.error(f"启动失败: {e}")
            self.is_running = False
            raise
    
    def pause(self, paused: bool):
        """暂停/继续
        
        Args:
            paused: True 为暂停，False 为继续
        """
        self.is_paused = paused
        if paused:
            logger.info("已暂停")
        else:
            logger.info("已继续")
    
    def stop(self):
        """停止字幕识别和朗读"""
        if not self.is_running:
            return
        
        logger.info("正在停止...")
        
        # 停止工作线程
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        
        # 停止语音合成
        if self.synthesizer:
            self.synthesizer.stop_speaking()
            self.synthesizer.stop_queue_worker()
        
        # 重置识别器
        if self.recognizer:
            self.recognizer.reset()
        
        logger.info("已停止")
    
    def _worker_loop(self, config: Dict[str, Any]):
        """工作线程主循环
        
        Args:
            config: 运行配置
        """
        region = config.get("region")
        interval = config.get("interval", self.config_manager.config.capture.interval)
        
        logger.info(f"开始识别循环，区域: {region}，间隔: {interval}秒")
        last_status_time = 0.0
        
        while self.is_running:
            try:
                # 检查暂停状态
                if self.is_paused:
                    time.sleep(0.5)
                    continue
                
                # 识别字幕
                result = self.recognizer.recognize_subtitle(region)
                
                if result.text:
                    logger.info(f"识别到字幕 (置信度: {result.confidence:.2f}): {result.text}")
                    
                    # 更新 GUI 状态
                    if self.gui:
                        self.gui.update_status(f"[{result.confidence:.2f}] {result.text}")
                    
                    # 朗读文本
                    self.synthesizer.enqueue_speech(result.text)
                    last_status_time = time.time()
                else:
                    # 每 5 秒提示一次未识别原因，避免刷屏
                    now = time.time()
                    if self.gui and (now - last_status_time) > 5:
                        reason_map = {
                            "capture_failed": "截图失败（检查区域或权限）",
                            "no_text": "未检测到文本",
                            "low_confidence": "置信度过低（可适当降低阈值）",
                            "duplicate": "重复字幕已跳过",
                            "error": "识别异常（查看日志）",
                            "ok": "已识别"
                        }
                        reason_text = reason_map.get(result.reason, result.reason)
                        self.gui.update_status(
                            f"未识别到字幕: {reason_text}，置信度: {result.confidence:.2f}"
                        )
                        last_status_time = now
                
                # 等待下次识别
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"工作循环错误: {e}")
                time.sleep(interval)
        
        logger.info("工作循环已退出")
    
    def run_gui(self):
        """运行 GUI 模式"""
        try:
            # 创建 GUI
            self.gui = FilmReaderGUI(
                on_start=self.start,
                on_pause=self.pause,
                on_stop=self.stop
            )
            
            logger.info("GUI 模式启动")
            
            # 运行 GUI 主循环
            self.gui.run()
            
        except KeyboardInterrupt:
            logger.info("收到中断信号")
        finally:
            self.cleanup()
    
    def run_cli(self, 
                region: Dict[str, int],
                ocr_engine: Optional[str] = None,
                ocr_language: Optional[str] = None,
                tts_engine: Optional[str] = None,
                tts_voice: Optional[str] = None,
                interval: Optional[float] = None):
        """运行命令行模式
        
        Args:
            region: 捕获区域
            ocr_engine: OCR 引擎
            ocr_language: OCR 语言
            tts_engine: TTS 引擎
            tts_voice: TTS 语音
            interval: 识别间隔
        """
        try:
            config = {
                "region": region,
                "ocr_engine": ocr_engine,
                "ocr_language": ocr_language,
                "tts_engine": tts_engine,
                "tts_voice": tts_voice,
                "interval": interval
            }
            
            logger.info("命令行模式启动")
            logger.info("按 Ctrl+C 停止")
            
            # 启动
            self.start(config)
            
            # 等待中断
            try:
                while self.is_running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("收到中断信号")
            
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理资源"""
        logger.info("正在清理资源...")
        
        # 停止运行
        self.stop()
        
        # 销毁 GUI
        if self.gui:
            try:
                self.gui.destroy()
            except:
                pass
        
        logger.info("清理完成")


def main():
    """主函数
    
    扩展点：
    - 添加命令行参数解析
    - 支持配置文件指定
    - 添加更多启动选项
    """
    try:
        # 创建应用程序实例
        app = FilmReaderApp()
        
        # 运行 GUI 模式
        app.run_gui()
        
    except Exception as e:
        logger.error(f"应用程序错误: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
