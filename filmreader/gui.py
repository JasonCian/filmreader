"""
GUI 界面模块

提供图形用户界面，支持屏幕区域选择、参数配置、控制按钮等功能。
使用 tkinter 构建（Python 内置，无需额外安装）。

扩展点：
- 支持 PyQt5/PySide6（更现代化的界面）
- 添加主题切换
- 支持界面自定义布局
- 添加更多可视化功能（如识别结果历史、统计信息等）
- 支持多语言界面
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from typing import Optional, Callable, Dict, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# 设置 DPI 感知（Windows）
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except:
    pass


class RegionSelector:
    """屏幕区域选择器
    
    提供交互式的屏幕区域选择功能。
    
    扩展点：
    - 支持多种选择方式（框选、点选、预设区域等）
    - 添加区域预览功能
    - 支持区域保存和加载
    """
    
    def __init__(self, parent: tk.Tk):
        """初始化区域选择器
        
        Args:
            parent: 父窗口
        """
        self.parent = parent
        self.region: Optional[Dict[str, int]] = None
        self.selection_window: Optional[tk.Toplevel] = None
    
    def select_region(self) -> Optional[Dict[str, int]]:
        """打开区域选择窗口
        
        Returns:
            选中的区域 {"x": x, "y": y, "width": w, "height": h}
        """
        # 创建全屏半透明窗口
        self.selection_window = tk.Toplevel(self.parent)
        self.selection_window.attributes('-alpha', 0.3)
        self.selection_window.attributes('-fullscreen', True)
        self.selection_window.attributes('-topmost', True)
        self.selection_window.configure(bg='black')
        
        # 添加说明文字
        label = tk.Label(
            self.selection_window,
            text="拖动鼠标选择字幕区域，按 ESC 取消",
            font=('Arial', 16),
            fg='white',
            bg='black'
        )
        label.pack(pady=20)
        
        # 绑定鼠标事件
        self.start_x = self.start_y = 0
        self.rect_id = None
        self.canvas = tk.Canvas(
            self.selection_window,
            highlightthickness=0,
            bg='black'
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind('<Button-1>', self._on_mouse_down)
        self.canvas.bind('<B1-Motion>', self._on_mouse_move)
        self.canvas.bind('<ButtonRelease-1>', self._on_mouse_up)
        self.selection_window.bind('<Escape>', lambda e: self._cancel_selection())
        
        # 等待选择完成
        self.selection_window.wait_window()
        
        return self.region
    
    def _on_mouse_down(self, event):
        """鼠标按下事件"""
        self.start_x = event.x
        self.start_y = event.y
        
        # 创建矩形
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline='red', width=2
        )
    
    def _on_mouse_move(self, event):
        """鼠标移动事件"""
        if self.rect_id:
            self.canvas.coords(
                self.rect_id,
                self.start_x, self.start_y, event.x, event.y
            )
    
    def _on_mouse_up(self, event):
        """鼠标释放事件"""
        end_x, end_y = event.x, event.y
        
        # 计算相对于 Canvas 的区域
        canvas_x = min(self.start_x, end_x)
        canvas_y = min(self.start_y, end_y)
        width = abs(end_x - self.start_x)
        height = abs(end_y - self.start_y)
        
        if width > 10 and height > 10:  # 最小尺寸
            # 转换为屏幕绝对坐标
            # 获取 Canvas 在屏幕上的位置
            canvas_screen_x = self.canvas.winfo_rootx()
            canvas_screen_y = self.canvas.winfo_rooty()
            
            # 计算屏幕绝对坐标
            screen_x = canvas_screen_x + canvas_x
            screen_y = canvas_screen_y + canvas_y
            
            self.region = {
                "x": screen_x,
                "y": screen_y,
                "width": width,
                "height": height
            }
            logger.debug(f"选择区域 - Canvas: ({canvas_x}, {canvas_y}), Screen: ({screen_x}, {screen_y}), Size: {width}x{height}")
            self.selection_window.destroy()
        else:
            messagebox.showwarning("区域太小", "请选择更大的区域")
    
    def _cancel_selection(self):
        """取消选择"""
        self.region = None
        self.selection_window.destroy()


class FilmReaderGUI:
    """FilmReader 主界面
    
    提供完整的图形用户界面。
    
    扩展点：
    - 添加更多配置选项
    - 支持界面布局自定义
    - 添加可视化统计
    - 支持插件系统
    """
    
    def __init__(self, 
                 on_start: Optional[Callable] = None,
                 on_pause: Optional[Callable] = None,
                 on_stop: Optional[Callable] = None,
                 on_config_change: Optional[Callable[[str, Any], None]] = None):
        """初始化 GUI
        
        Args:
            on_start: 启动回调函数
            on_pause: 暂停回调函数
            on_stop: 停止回调函数
            on_config_change: 配置变更回调函数
        """
        self.on_start = on_start
        self.on_pause = on_pause
        self.on_stop = on_stop
        self.on_config_change = on_config_change
        
        self.root = tk.Tk()
        self.root.title("FilmReader - 字幕朗读助手")
        self.root.geometry("700x500")
        
        # 状态变量
        self.is_running = False
        self.is_paused = False
        self.region: Optional[Dict[str, int]] = None
        
        self._create_widgets()
        
    def _create_widgets(self):
        """创建界面组件"""
        # 主容器
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置根窗口的网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # 1. 区域选择区域
        region_frame = ttk.LabelFrame(main_frame, text="字幕区域", padding="10")
        region_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        region_frame.columnconfigure(1, weight=1)
        
        ttk.Button(region_frame, text="选择区域", command=self._select_region).grid(
            row=0, column=0, padx=5
        )
        
        self.region_label = ttk.Label(region_frame, text="未选择")
        self.region_label.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # 手动输入坐标
        ttk.Label(region_frame, text="或手动输入:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        
        coord_frame = ttk.Frame(region_frame)
        coord_frame.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(coord_frame, text="X:").pack(side=tk.LEFT)
        self.x_entry = ttk.Entry(coord_frame, width=8)
        self.x_entry.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(coord_frame, text="Y:").pack(side=tk.LEFT, padx=(10, 0))
        self.y_entry = ttk.Entry(coord_frame, width=8)
        self.y_entry.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(coord_frame, text="宽:").pack(side=tk.LEFT, padx=(10, 0))
        self.width_entry = ttk.Entry(coord_frame, width=8)
        self.width_entry.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(coord_frame, text="高:").pack(side=tk.LEFT, padx=(10, 0))
        self.height_entry = ttk.Entry(coord_frame, width=8)
        self.height_entry.pack(side=tk.LEFT, padx=2)
        
        # 2. OCR 配置
        ocr_frame = ttk.LabelFrame(main_frame, text="OCR 配置", padding="10")
        ocr_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        ocr_frame.columnconfigure(1, weight=1)
        
        ttk.Label(ocr_frame, text="引擎:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.ocr_engine_var = tk.StringVar(value="rapidocr")
        ocr_engine_combo = ttk.Combobox(
            ocr_frame,
            textvariable=self.ocr_engine_var,
            values=["rapidocr", "paddleocr", "tesseract", "windows_ocr", "ai_vision"],
            state="readonly"
        )
        ocr_engine_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        ttk.Label(ocr_frame, text="语言:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.ocr_language_var = tk.StringVar(value="chi_sim")
        ocr_language_combo = ttk.Combobox(
            ocr_frame,
            textvariable=self.ocr_language_var,
            values=["chi_sim", "chi_tra", "eng", "jpn", "kor", "fra", "deu", "spa", "rus"],
            state="normal"  # 可编辑
        )
        ocr_language_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # 预处理配置
        self.preprocess_enable_var = tk.BooleanVar(value=True)
        preprocess_check = ttk.Checkbutton(
            ocr_frame,
            text="启用预处理（提升识别效果）",
            variable=self.preprocess_enable_var
        )
        preprocess_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        preprocess_opts = ttk.Frame(ocr_frame)
        preprocess_opts.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        
        self.preprocess_grayscale_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            preprocess_opts,
            text="灰度化",
            variable=self.preprocess_grayscale_var
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        self.preprocess_invert_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            preprocess_opts,
            text="反色",
            variable=self.preprocess_invert_var
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.preprocess_auto_threshold_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            preprocess_opts,
            text="自适应阈值",
            variable=self.preprocess_auto_threshold_var
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(preprocess_opts, text="阈值:").pack(side=tk.LEFT)
        self.preprocess_threshold_var = tk.StringVar(value="160")
        ttk.Entry(preprocess_opts, textvariable=self.preprocess_threshold_var, width=6).pack(side=tk.LEFT, padx=5)

        ttk.Label(preprocess_opts, text="缩放:").pack(side=tk.LEFT, padx=(10, 0))
        self.preprocess_scale_var = tk.StringVar(value="2.0")
        ttk.Entry(preprocess_opts, textvariable=self.preprocess_scale_var, width=6).pack(side=tk.LEFT, padx=5)
        
        # 3. TTS 配置
        tts_frame = ttk.LabelFrame(main_frame, text="TTS 配置", padding="10")
        tts_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        tts_frame.columnconfigure(1, weight=1)
        
        ttk.Label(tts_frame, text="引擎:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.tts_engine_var = tk.StringVar(value="edge-tts")
        tts_engine_combo = ttk.Combobox(
            tts_frame,
            textvariable=self.tts_engine_var,
            values=["edge-tts", "pyttsx3", "azure-tts", "ai_voice"],
            state="readonly"
        )
        tts_engine_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        ttk.Label(tts_frame, text="语音:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.tts_voice_var = tk.StringVar(value="zh-CN-XiaoxiaoNeural")
        tts_voice_combo = ttk.Combobox(
            tts_frame,
            textvariable=self.tts_voice_var,
            values=[
                "zh-CN-XiaoxiaoNeural",
                "zh-CN-YunxiNeural",
                "zh-CN-YunyangNeural",
                "zh-CN-XiaoyiNeural",
                "zh-CN-YunjianNeural",
                "en-US-AriaNeural",
                "en-US-GuyNeural",
                "ja-JP-NanamiNeural",
                "ja-JP-KeitaNeural",
                "ko-KR-SunHiNeural"
            ],
            state="normal"  # 可编辑
        )
        tts_voice_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # 4. 运行参数
        params_frame = ttk.LabelFrame(main_frame, text="运行参数", padding="10")
        params_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        params_frame.columnconfigure(1, weight=1)
        
        ttk.Label(params_frame, text="识别间隔(秒):").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.interval_var = tk.StringVar(value="1.0")
        interval_entry = ttk.Entry(params_frame, textvariable=self.interval_var, width=10)
        interval_entry.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # 5. 控制按钮
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=4, column=0, pady=10)
        
        self.start_button = ttk.Button(
            control_frame,
            text="启动",
            command=self._on_start_clicked
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.pause_button = ttk.Button(
            control_frame,
            text="暂停",
            command=self._on_pause_clicked,
            state=tk.DISABLED
        )
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            control_frame,
            text="停止",
            command=self._on_stop_clicked,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # 6. 状态显示
        status_frame = ttk.LabelFrame(main_frame, text="状态", padding="10")
        status_frame.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(5, weight=1)
        
        self.status_text = tk.Text(status_frame, height=6, wrap=tk.WORD)
        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(status_frame, command=self.status_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.status_text['yscrollcommand'] = scrollbar.set
        
        self._log_status("就绪")
    
    def _select_region(self):
        """选择屏幕区域"""
        selector = RegionSelector(self.root)
        region = selector.select_region()
        
        if region:
            self.region = region
            self.region_label.config(
                text=f"X:{region['x']} Y:{region['y']} "
                     f"宽:{region['width']} 高:{region['height']}"
            )
            
            # 更新输入框
            self.x_entry.delete(0, tk.END)
            self.x_entry.insert(0, str(region['x']))
            self.y_entry.delete(0, tk.END)
            self.y_entry.insert(0, str(region['y']))
            self.width_entry.delete(0, tk.END)
            self.width_entry.insert(0, str(region['width']))
            self.height_entry.delete(0, tk.END)
            self.height_entry.insert(0, str(region['height']))
            
            self._log_status(f"已选择区域: {region}")
    
    def _get_region_from_entries(self) -> Optional[Dict[str, int]]:
        """从输入框获取区域"""
        try:
            region = {
                "x": int(self.x_entry.get()),
                "y": int(self.y_entry.get()),
                "width": int(self.width_entry.get()),
                "height": int(self.height_entry.get())
            }
            return region
        except (ValueError, tk.TclError):
            return None
    
    def _on_start_clicked(self):
        """启动按钮点击事件"""
        # 获取区域
        region = self.region or self._get_region_from_entries()
        
        if not region:
            messagebox.showwarning("警告", "请先选择字幕区域")
            return
        
        # 更新状态
        self.is_running = True
        self.is_paused = False
        self.start_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL)
        
        self._log_status("已启动")
        
        # 调用回调
        if self.on_start:
            config = self._get_config()
            self.on_start(config)
    
    def _on_pause_clicked(self):
        """暂停按钮点击事件"""
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            self.pause_button.config(text="继续")
            self._log_status("已暂停")
        else:
            self.pause_button.config(text="暂停")
            self._log_status("已继续")
        
        # 调用回调
        if self.on_pause:
            self.on_pause(self.is_paused)
    
    def _on_stop_clicked(self):
        """停止按钮点击事件"""
        self.is_running = False
        self.is_paused = False
        
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED, text="暂停")
        self.stop_button.config(state=tk.DISABLED)
        
        self._log_status("已停止")
        
        # 调用回调
        if self.on_stop:
            self.on_stop()
    
    def _get_config(self) -> Dict[str, Any]:
        """获取当前配置
        
        Returns:
            配置字典
        """
        return {
            "region": self.region or self._get_region_from_entries(),
            "ocr_engine": self.ocr_engine_var.get(),
            "ocr_language": self.ocr_language_var.get(),
            "preprocess_enable": self.preprocess_enable_var.get(),
            "preprocess_grayscale": self.preprocess_grayscale_var.get(),
            "preprocess_invert": self.preprocess_invert_var.get(),
            "preprocess_auto_threshold": self.preprocess_auto_threshold_var.get(),
            "preprocess_threshold": int(self.preprocess_threshold_var.get() or "160"),
            "preprocess_scale": float(self.preprocess_scale_var.get() or "2.0"),
            "tts_engine": self.tts_engine_var.get(),
            "tts_voice": self.tts_voice_var.get(),
            "interval": float(self.interval_var.get())
        }
    
    def _log_status(self, message: str):
        """记录状态信息
        
        Args:
            message: 状态消息
        """
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        logger.info(message)
    
    def update_status(self, message: str):
        """更新状态显示（线程安全）
        
        Args:
            message: 状态消息
        """
        self.root.after(0, self._log_status, message)
    
    def run(self):
        """运行 GUI 主循环"""
        self.root.mainloop()
    
    def destroy(self):
        """销毁窗口"""
        self.root.destroy()
