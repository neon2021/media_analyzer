import unittest
import sys
import io
import logging
from contextlib import redirect_stdout, redirect_stderr

class TestOutputCapture(unittest.TestCase):
    """测试输出捕获机制"""

    def test_print_capture(self):
        """测试标准输出捕获"""
        # 用StringIO捕获标准输出
        captured_output = io.StringIO()
        with redirect_stdout(captured_output):
            print("这是一个标准输出测试")
        
        # 获取捕获的输出
        output = captured_output.getvalue()
        print(f"实际捕获到的输出: '{output}'")
        self.assertEqual(output, "这是一个标准输出测试\n")
    
    def test_stderr_capture(self):
        """测试标准错误捕获"""
        # 用StringIO捕获标准错误
        captured_error = io.StringIO()
        with redirect_stderr(captured_error):
            sys.stderr.write("这是一个标准错误测试\n")
        
        # 获取捕获的错误输出
        error_output = captured_error.getvalue()
        print(f"实际捕获到的错误: '{error_output}'")
        self.assertEqual(error_output, "这是一个标准错误测试\n")
    
    def test_logger_capture(self):
        """测试日志输出捕获"""
        # 设置一个自定义的日志处理器
        logger = logging.getLogger("test_logger")
        logger.setLevel(logging.DEBUG)
        
        # 创建一个StringIO对象来捕获日志输出
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        # 清除现有处理器并添加新的自定义处理器
        logger.handlers = []
        logger.addHandler(handler)
        
        # 输出日志消息
        logger.debug("这是一条调试日志")
        logger.info("这是一条信息日志")
        logger.warning("这是一条警告日志")
        
        # 获取捕获的日志输出
        log_output = log_capture.getvalue()
        print(f"实际捕获到的日志: '{log_output}'")
        self.assertIn("DEBUG - 这是一条调试日志", log_output)
        self.assertIn("INFO - 这是一条信息日志", log_output)
        self.assertIn("WARNING - 这是一条警告日志", log_output)
    
    def test_mixed_output(self):
        """测试混合输出捕获"""
        # 同时捕获标准输出和标准错误
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            print("标准输出消息")
            sys.stderr.write("标准错误消息\n")
            
            # 设置日志同时输出到标准输出
            logging.basicConfig(
                level=logging.INFO,
                format='%(levelname)s: %(message)s',
                stream=sys.stdout  # 输出到标准输出
            )
            logging.info("日志信息消息")
        
        # 检查捕获的输出
        stdout_output = stdout_capture.getvalue()
        stderr_output = stderr_capture.getvalue()
        
        print(f"捕获的标准输出: '{stdout_output}'")
        print(f"捕获的标准错误: '{stderr_output}'")
        
        self.assertIn("标准输出消息", stdout_output)
        self.assertIn("INFO: 日志信息消息", stdout_output)  # 日志被定向到stdout
        self.assertEqual(stderr_output, "标准错误消息\n")

if __name__ == "__main__":
    unittest.main() 