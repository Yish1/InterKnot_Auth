from PyQt5.QtCore import QThreadPool, pyqtSignal, QRunnable

from modules.State import global_state
from modules.Working_signals import WorkerSignals

import subprocess
import os 
# import debugpy

state = global_state()

class easytier_thread(QRunnable):
    def __init__(self, main_window, mode):
        super().__init__()
        self.signals = WorkerSignals()
        self.main_window = main_window
        self.mode = mode
    def check_config_exist(self):
        easytier_config_path = os.path.join(state.config_dir, "easytier.toml")

        if self.mode == "server":

            toml = f'''
instance_name = "InterKnot"
ipv4 = "10.129.114.10/24"
dhcp = false
listeners = ["wg://0.0.0.0:{state.et_port}"]

[network_identity]
network_name = "InterKnot"
network_secret = "{state.et_secret_key}"

[flags]
bind_device = {"true" if state.et_bind_device == "1" else "false"}
dev_name = "InterKnot"
enable_exit_node = true
enable_ipv6 = {"true" if state.et_enable_ipv6 == "1" else "false"}
''' 
        elif self.mode == "client":
            toml = f'''
instance_name = "InterKnot"
dhcp = true
exit_nodes = ["10.129.114.10"]

[network_identity]
network_name = "InterKnot"
network_secret = "{state.password}"

[[peer]]
uri = "wg://{state.username}:51145"

[flags]
dev_name = "InterKnot"
'''
        
        with open(easytier_config_path, "w") as f:
            f.write(toml)

    def check_et_exist(self):
        self.easytier_executable = os.path.join(os.getcwd(), "easytier", "easytier-core.exe")
        if not os.path.exists(self.easytier_executable):
            self.print_to_all("错误：找不到 EasyTier Core！请重新安装绳网！")
            self.main_window.et_process = None 
            self.signals.finished.emit()
            return False
        return True
    
    def add_route(self):
        cmd = [
            "route",
            "add",
            "0.0.0.0",
            "mask",
            "0.0.0.0",
            "10.129.114.10",
            "metric",
            "1"
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        if result.returncode == 0:
            self.print_to_all("ET:路由添加成功")
        else:
            self.print_to_all(f"ET:路由添加失败: {result.stderr}")

    def remove_et_route(self):
        cmd = [
            "route",
            "delete",
            "0.0.0.0",
            "10.129.114.10"
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        if result.returncode == 0:
            self.update_list("ET:路由删除成功")
        else:
            self.update_list(f"ET:路由删除失败: {result.stderr}")

    def print_to_all(self, text):
        self.signals.print_text_et.emit(text)
        self.signals.print_text.emit(text)

    def run(self):
        self.check_config_exist()
        r = self.check_et_exist()
        if not r:
            return # 找不到EasyTier Core
        
        self.print_to_all(f"ET:启动绳网共享进程...")

        if hasattr(self.main_window, 'et_process') and self.main_window.et_process is not None:
            if isinstance(self.main_window.et_process, subprocess.Popen) and self.main_window.et_process.poll() is None:
                self.print_to_all("隧道故障：进程重复运行，尝试重启...")
                self.main_window.et_process.terminate()
                try:
                    self.main_window.et_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.main_window.et_process.kill()

        self.main_window.et_process = subprocess.Popen(
            [self.easytier_executable,
            "-c",
            os.path.join(state.config_dir, "easytier.toml")],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        output = True
        failure_time = 0

        for line in self.main_window.et_process.stdout:
            line = line.strip()
            lower_line = line.lower()

            # 先检测错误
            if any(k in lower_line for k in ("panic", "stopping", "error")):
                self.signals.print_text.emit(
                    f"隧道故障：{line}，请切换至'隧道日志'查看详情！"
                )

                if "stopping" in lower_line:
                    self.signals.finished.emit()

            # 控制 TOML 屏蔽区
            if "############### TOML ###############" in line:
                output = False
                continue

            if "-----------------------------------" in line:
                output = True
                continue

            # 成功启动
            text = "ET:共享隧道已创建成功，可切换至'隧道日志'查看详情！" if self.mode == "server" else "正在连接到绳网...可切换至'隧道日志'查看详情！"
            if "starting easytier" in lower_line:
                self.signals.print_text.emit(text)

            if "tun device ready" in lower_line and self.mode == "client":
                self.signals.print_text.emit("ET:TUN已就绪，即将添加路由...")
                self.add_route()

            if "remote_addr" in lower_line and self.mode == "server":
                self.signals.print_text.emit(f"ET:{line.split('remote_addr: Some(Url { url: "wg://')[1].strip().split(':')[0]} 已连接到绳网！")
            
            if "connecting to" in lower_line and self.mode == "client":
                failure_time += 1
                if failure_time >= 8:
                    self.signals.print_text.emit("ET:连接绳网失败，删除路由并重试...")
                    self.remove_et_route()
                    failure_time = 0

            if "peer connection removed" in lower_line and self.mode == "client":
                self.signals.print_text.emit("ET:绳网节点失联，删除路由并重试...")
                self.remove_et_route()

            # 输出日志
            if output:
                self.signals.print_text_et.emit(line)