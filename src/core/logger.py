import os
import time
import atexit
import functools
import inspect
import threading
import colorlog
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from src.config import settings

class HandleLog:
    """
    增强的日志处理类，支持彩色输出、文件轮转、自动清理等功能
    自动将title默认设置为调用函数名
    """
    
    # 日志级别映射
    LEVEL_MAP = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'WARN': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
        'CRI': logging.CRITICAL
    }
    
    def __init__(self, s_name, console_level='INFO', file_level=settings.LOG_LEVEL, log_dir='logs', max_bytes=5*1024*1024, backup_count=5,use_async=False, auto_clean_days=30):
        """
        初始化日志处理器
        
        Args:
            s_name: 日志名称
            console_level: 控制台日志级别
            file_level: 文件日志级别
            log_dir: 日志目录
            max_bytes: 单个日志文件最大字节数
            backup_count: 保留的备份文件数量
            use_async: 是否使用异步日志
            auto_clean_days: 自动清理多少天前的日志文件
        """
        self.logger = logging.getLogger(s_name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        
        # 创建日志目录
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        self.auto_clean_days = auto_clean_days
        self._setup_handlers(console_level, file_level, max_bytes, backup_count, use_async)
        
        # 注册程序退出时的清理函数
        atexit.register(self._cleanup)
        
        # 启动自动清理线程
        if auto_clean_days > 0:
            self._start_cleanup_thread()
    
    def _setup_handlers(self, console_level, file_level, max_bytes, backup_count, use_async):
        """设置日志处理器"""
        
        # 清理已有的处理器
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # 转换日志级别
        console_level = self._get_level(console_level)
        file_level = self._get_level(file_level)
        
        # 设置控制台日志处理器
        sh = self._create_console_handler(console_level)
        
        # 设置文件日志处理器
        fh = self._create_file_handler(file_level, max_bytes, backup_count)
        
        # 如果启用异步日志，包装处理器
        if use_async:
            sh = self._wrap_async_handler(sh)
            fh = self._wrap_async_handler(fh)
        
        self.logger.addHandler(sh)
        self.logger.addHandler(fh)
    
    def _get_level(self, level):
        """获取日志级别"""
        if isinstance(level, str):
            return self.LEVEL_MAP.get(level.upper(), logging.INFO)
        return level
    
    def _create_console_handler(self, level):
        """创建控制台日志处理器"""
        sh = logging.StreamHandler()
        sh.setLevel(level)
        
        formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s %(name)6s: %(message_log_color)s%(message)s',
            datefmt='%y%m%d %H:%M:%S',
            reset=True,
            log_colors={
                'DEBUG': 'black',
                'INFO': 'cyan',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            },
            secondary_log_colors={'message': {
                'DEBUG': 'light_black',
                'INFO': 'light_cyan',
                'WARNING': 'light_yellow',
                'ERROR': 'light_red',
                'CRITICAL': 'light_purple'
            }},
            style='%'
        )
        sh.setFormatter(formatter)
        return sh
    
    def _create_file_handler(self, level, max_bytes, backup_count):
        """创建文件日志处理器"""
        # 使用日期作为文件名，避免中文编码问题
        today = datetime.now().strftime('%Y%m%d')
        file_path = os.path.join(self.log_dir, f"{today}.log")
        
        # 使用追加模式，避免覆盖文件
        fh = RotatingFileHandler(
            filename=file_path, 
            mode="a", 
            maxBytes=max_bytes, 
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        formatter_file = logging.Formatter(
            '%(asctime)s %(name)s %(levelname)9s: %(message)s', 
            datefmt='%a %Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter_file)
        fh.setLevel(level)
        return fh
    
    def _wrap_async_handler(self, handler):
        """包装处理器为异步模式"""
        # 这里可以实现异步日志处理逻辑
        # 简化版本，实际应用中可以使用队列等机制
        return handler
    
    def _start_cleanup_thread(self):
        """启动日志清理线程"""
        def cleanup_task():
            while True:
                self._clean_old_logs()
                # 每24小时清理一次
                time.sleep(24 * 3600)
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
    
    def _clean_old_logs(self):
        """清理旧的日志文件"""
        if self.auto_clean_days <= 0:
            return
        
        try:
            current_time = time.time()
            cutoff_time = current_time - (self.auto_clean_days * 24 * 3600)
            
            for filename in os.listdir(self.log_dir):
                file_path = os.path.join(self.log_dir, filename)
                if os.path.isfile(file_path) and filename.endswith('.log'):
                    file_mod_time = os.path.getmtime(file_path)
                    if file_mod_time < cutoff_time:
                        os.remove(file_path)
        except Exception as e:
            self.error(f"清理旧日志文件时发生错误: {e}")
    
    def _cleanup(self):
        """程序退出时的清理工作"""
        try:
            # 关闭所有处理器
            for handler in self.logger.handlers[:]:
                handler.close()
                self.logger.removeHandler(handler)
        except Exception:
            pass
    
    def _get_caller_function_name(self, skip_frames=2):
        """
        获取调用者的函数名称
        
        Args:
            skip_frames: 跳过的栈帧数，默认跳过当前方法和调用它的日志方法
        
        Returns:
            str: 调用者的函数名称，如果无法获取则返回'unknown'
        """
        try:
            # 获取调用栈
            frame = inspect.currentframe()
            
            # 跳过指定数量的栈帧
            for _ in range(skip_frames):
                if frame and frame.f_back:
                    frame = frame.f_back
                else:
                    return 'unknown'
            
            # 获取函数名称
            if frame:
                return frame.f_code.co_name
            return 'unknown'
        except Exception:
            return 'unknown'
        finally:
            # 避免循环引用
            del frame
    
    def debug(self, message, title=None, **kwargs):
        """
        记录调试级别日志
        
        Args:
            message: 日志消息
            title: 日志标题，默认为调用函数名
            **kwargs: 其他日志参数
        """
        if title is None:
            title = self._get_caller_function_name()
        self._log(logging.DEBUG, message, title, **kwargs)
    
    def info(self, message, title=None, **kwargs):
        """
        记录信息级别日志
        
        Args:
            message: 日志消息
            title: 日志标题，默认为调用函数名
            **kwargs: 其他日志参数
        """
        if title is None:
            title = self._get_caller_function_name()
        self._log(logging.INFO, message, title, **kwargs)
    
    def warning(self, message, title=None, **kwargs):
        """
        记录警告级别日志
        
        Args:
            message: 日志消息
            title: 日志标题，默认为调用函数名
            **kwargs: 其他日志参数
        """
        if title is None:
            title = self._get_caller_function_name()
        self._log(logging.WARNING, message, title, **kwargs)
    
    def error(self, message, title=None, exc_info=False, **kwargs):
        """
        记录错误级别日志
        
        Args:
            message: 日志消息
            title: 日志标题，默认为调用函数名
            exc_info: 是否包含异常信息
            **kwargs: 其他日志参数
        """
        if title is None:
            title = self._get_caller_function_name()
        self._log(logging.ERROR, message, title, exc_info=exc_info, **kwargs)
    
    def critical(self, message, title=None, exc_info=False, **kwargs):
        """
        记录严重错误级别日志
        
        Args:
            message: 日志消息
            title: 日志标题，默认为调用函数名
            exc_info: 是否包含异常信息
            **kwargs: 其他日志参数
        """
        if title is None:
            title = self._get_caller_function_name()
        self._log(logging.CRITICAL, message, title, exc_info=exc_info, **kwargs)
    
    def cri(self, message, title=None, exc_info=False, **kwargs):
        """
        记录严重错误级别日志（别名）
        
        Args:
            message: 日志消息
            title: 日志标题，默认为调用函数名
            exc_info: 是否包含异常信息
            **kwargs: 其他日志参数
        """
        self.critical(message, title, exc_info, **kwargs)
    
    def _log(self, level, message, title, **kwargs):
        """通用日志记录方法"""
        try:
            if title:
                log_message = f"{title}: {message}"
            else:
                log_message = message
            
            self.logger.log(level, log_message, **kwargs)
        except Exception as e:
            # 日志记录失败时的降级处理
            print(f"日志记录失败: {e}, 原始消息: {message}")
    
    def set_level(self, console_level=None, file_level=None):
        """动态设置日志级别"""
        if console_level is not None:
            for handler in self.logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setLevel(self._get_level(console_level))
        
        if file_level is not None:
            for handler in self.logger.handlers:
                if isinstance(handler, RotatingFileHandler):
                    handler.setLevel(self._get_level(file_level))
    
    def add_handler(self, handler):
        """添加自定义处理器"""
        self.logger.addHandler(handler)
    
    def remove_handler(self, handler):
        """移除处理器"""
        if handler in self.logger.handlers:
            self.logger.removeHandler(handler)


# 装饰器：自动记录函数调用日志（包含运行时间）
def logCall(logger=None):
    """
    自动记录函数调用的装饰器，包含运行时间统计
    
    Args:
        logger: HandleLog实例，如果为None则使用默认实例
    
    Returns:
        decorator: 装饰器函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time
            
            # 使用传入的logger或创建默认logger
            log_instance = logger if logger else HandleLog(func.__module__)
            
            # 记录函数开始调用和开始时间
            start_time = time.perf_counter()
            log_instance.info(f"开始执行，参数: args={args}, kwargs={kwargs}")
            
            try:
                result = func(*args, **kwargs)
                
                # 计算运行时间
                end_time = time.perf_counter()
                execution_time = end_time - start_time
                
                # 记录函数执行成功和运行时间
                log_instance.info(
                    f"执行成功，返回值: {result}，运行时间: {execution_time:.2f}秒"
                )
                return result
            except Exception as e:
                # 计算异常情况下的运行时间
                end_time = time.perf_counter()
                execution_time = end_time - start_time
                
                # 记录函数执行失败和运行时间
                log_instance.error(
                    f"执行失败: {e}，运行时间: {execution_time:.2f}秒", 
                    exc_info=True
                )
                raise
        return wrapper
    return decorator



# # 使用示例
# if __name__ == "__main__":
#     try:
#         # 初始化日志器
#         logger = HandleLog(
#             s_name="MyApp",
#             console_level='INFO',
#             file_level='DEBUG',
#             max_bytes=10*1024*1024,  # 10MB
#             backup_count=10,
#             auto_clean_days=7
#         )
        
#         def example_function():
#             """示例函数，演示自动获取函数名作为title"""
#             logger.debug("这是一条调试信息，自动使用函数名作为title")
#             logger.info("这是一条普通信息")
            
#             # 手动指定title会覆盖自动获取的函数名
#             logger.warning("这是一条警告信息", title="自定义标题")
            
#             # 调用其他函数
#             process_data([1, 2, 3, 4, 5])
        
#         @logCall(logger)
#         def process_data(data):
#             """处理数据的函数，使用装饰器自动记录"""
#             logger.info(f"处理数据: {data}")
#             return [x * 2 for x in data]
        
#         def simulate_error():
#             """模拟错误情况"""
#             try:
#                 logger.info("尝试执行可能出错的操作")
#                 1/0
#             except Exception as e:
#                 logger.error(f"发生错误: {e}", exc_info=True)
        
#         # 执行示例
#         print("=== 开始日志示例 ===")
#         example_function()
#         simulate_error()
        
#         print("\n=== 日志记录完成 ===")
#         print(f"日志文件保存在: {os.path.join(os.getcwd(), 'logs')}")
        
#     except Exception as e:
#         print(f"程序运行出错: {e}")