from PyQt5.QtCore import QThreadPool, pyqtSignal, QRunnable

from modules.State import global_state
from modules.Working_signals import WorkerSignals

import subprocess
import os
import sys
# import debugpy

state = global_state()


class easytier_thread(QRunnable):
    def __init__(self, main_window, mode):
        super().__init__()
        self.signals = WorkerSignals()
        self.main_window = main_window
        self.mode = mode
        self.route_added = False

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
bind_device = true
dev_name = "InterKnot"
enable_exit_node = true
enable_ipv6 = {"true" if state.et_enable_ipv6 == 1 else "false"}
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
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        self.easytier_executable = os.path.join(
            base_dir,
            "easytier",
            "easytier-core.exe"
        )

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
            self.print_to_all("ET: 路由添加成功")
            self.route_added = True

        else:
            self.print_to_all(f"ET: 路由添加失败: {result.stderr}")

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
            self.signals.print_text.emit("ET: 路由删除成功")
            self.route_added = False
        else:
            self.signals.print_text.emit(f"ET: 路由删除失败: {result.stderr}")

    def print_to_all(self, text):
        self.signals.print_text_et.emit(text)
        self.signals.print_text.emit(text)

    def run(self):
        self.check_config_exist()
        r = self.check_et_exist()
        if not r:
            return  # 找不到EasyTier Core

        self.print_to_all(f"ET: 启动绳网共享进程...")

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

        failure_time = 0
        connect_times = 0
        tun_ok = False

        for line in self.main_window.et_process.stdout:
            output = True
            line = line.strip()
            lower_line = line.lower()

            if "network_secret = " in line:
                continue

            # 成功启动
            text = "ET: 共享隧道已创建成功，可切换至'隧道日志'查看详情！\nET: 分享时请告知对方您的IP地址以及密码" if self.mode == "server" else "正在连接到绳网...可切换至'隧道日志'查看详情！"
            if "starting easytier" in lower_line:
                self.signals.print_text.emit(text)
                connect_times = 0

            if "new peer connection added" in lower_line and self.mode == "client":
                self.signals.print_text.emit("ET: 已连接到绳网节点，即将添加路由...\nET: 正在等待TUN网卡...")
                if tun_ok and not self.route_added:
                    self.add_route()

            if "tun device ready" in lower_line and self.mode == "client":
                tun_ok = True
                if not self.route_added:
                    self.add_route()

            if "remote: wg://" in lower_line and self.mode == "server":
                self.signals.print_text.emit(
                    f"ET: {line.split('remote: wg://')[1].strip().split(':')[0]} 已连接到绳网！")

            if "connecting to peer" in lower_line and self.mode == "client":
                connect_times += 1
                if connect_times % 5 == 0 and connect_times < 50:
                    self.signals.print_text.emit("ET: 绳网节点无响应，仍在尝试中...")
                
                if connect_times >= 500:
                    connect_times = 0

            if "connect to peer error" in lower_line and self.mode == "client":
                failure_time += 1
                output = False
                if failure_time >= 5 and self.route_added:
                    self.signals.print_text.emit("ET: 连接绳网失败，删除路由并重试...")
                    self.remove_et_route()
                    failure_time = 0

            if "peer connection removed" in lower_line:
                if self.mode == "client":
                    self.signals.print_text.emit("ET: 绳网节点失联，删除路由并重试...")
                    self.remove_et_route()

                elif self.mode == "server":
                    self.signals.print_text.emit(
                        f"ET: {line.split('remote_addr: Some(Url { url: "wg://')[1].split(':')[0]} 已断开连接！")

            # 检测错误
            if any(k in lower_line for k in ("panic", "stopping", "error")) and output:
                self.signals.print_text.emit(
                    f"隧道故障：{line}，请切换至'隧道日志'查看详情！"
                )

                if "stopping" in lower_line:
                    self.signals.finished.emit()

            self.signals.print_text_et.emit(line)
