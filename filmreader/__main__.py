"""
FilmReader 启动入口

支持通过 `python -m filmreader` 启动应用程序。

扩展点：
- 添加命令行参数解析（argparse）
- 支持不同的运行模式（GUI、CLI、服务）
- 添加版本信息、帮助信息等
"""

import sys
import argparse
from pathlib import Path

from . import main, __version__


def parse_args():
    """解析命令行参数
    
    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        prog="filmreader",
        description="FilmReader - 字幕朗读助手",
        epilog="更多信息请访问: https://github.com/your-repo/filmreader"
    )
    
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"FilmReader {__version__}"
    )
    
    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="配置文件路径（默认: config/config.json）"
    )
    
    parser.add_argument(
        "--cli",
        action="store_true",
        help="以命令行模式运行（需要指定区域参数）"
    )
    
    # CLI 模式参数
    cli_group = parser.add_argument_group("CLI 模式参数")
    
    cli_group.add_argument(
        "--region",
        type=str,
        help="捕获区域，格式: x,y,width,height （如: 0,0,800,100）"
    )
    
    cli_group.add_argument(
        "--ocr-engine",
        type=str,
        choices=["tesseract", "windows_ocr", "ai_vision"],
        help="OCR 引擎"
    )
    
    cli_group.add_argument(
        "--ocr-language",
        type=str,
        help="OCR 识别语言（如: eng, chi_sim, jpn）"
    )
    
    cli_group.add_argument(
        "--tts-engine",
        type=str,
        choices=["edge-tts", "azure-tts", "ai_voice"],
        help="TTS 引擎"
    )
    
    cli_group.add_argument(
        "--tts-voice",
        type=str,
        help="TTS 语音（如: en-US-AriaNeural, zh-CN-XiaoxiaoNeural）"
    )
    
    cli_group.add_argument(
        "--interval",
        type=float,
        help="识别间隔（秒）"
    )
    
    return parser.parse_args()


def main_entry():
    """主入口函数"""
    args = parse_args()
    
    try:
        # 创建应用程序实例
        from .main import FilmReaderApp
        app = FilmReaderApp(config_path=args.config)
        
        if args.cli:
            # CLI 模式
            if not args.region:
                print("错误: CLI 模式需要指定 --region 参数", file=sys.stderr)
                print("格式: --region x,y,width,height", file=sys.stderr)
                print("示例: --region 0,900,1920,100", file=sys.stderr)
                return 1
            
            # 解析区域参数
            try:
                x, y, width, height = map(int, args.region.split(','))
                region = {"x": x, "y": y, "width": width, "height": height}
            except ValueError:
                print("错误: 区域格式不正确", file=sys.stderr)
                print("格式: x,y,width,height", file=sys.stderr)
                return 1
            
            # 运行 CLI 模式
            app.run_cli(
                region=region,
                ocr_engine=args.ocr_engine,
                ocr_language=args.ocr_language,
                tts_engine=args.tts_engine,
                tts_voice=args.tts_voice,
                interval=args.interval
            )
        else:
            # GUI 模式（默认）
            app.run_gui()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n程序已中断")
        return 0
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main_entry())
