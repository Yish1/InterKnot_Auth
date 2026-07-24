from PyQt5.QtCore import QThreadPool, pyqtSignal, QRunnable

from pathlib import Path
from modules.State import global_state
from modules.Working_signals import WorkerSignals
from .WebUI import WebUIThread
from modules.SecurityManager import *

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

    def check_config_exist(self, path):
        easytier_config_path = path

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
rpc_portal = "15888"
bind_device = true
dev_name = "InterKnot"
enable_exit_node = true
enable_ipv6 = {"true" if state.et_enable_ipv6 == 1 else "false"}
speed_limit = {state.et_speed_limit}
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
rpc_portal = "15888"
dev_name = "InterKnot"
enable_ipv6 = {"true" if state.et_enable_ipv6 == 1 else "false"}
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

    def start_webui(self):
        if state.webui_thread is None:
            state.webui_thread = WebUIThread(self.main_window)
            state.webui_thread.start()

    def run(self):
        if state.et_en_userconf == 1:
            config_path = state.et_userconf_path
            # 如果文件名是 encrypted_userconf.toml，则尝试解密
            if os.path.basename(config_path) == "encrypted_userconf.toml":
                try:
                    content = Path(config_path).read_text(encoding="utf-8")
                    decrypted_content = SecurityManager.decrypt(content, SecurityManager.get_encryption_key())
                    # 在系统temp下创建tunnel.toml文件
                    temp_dir = Path(os.getenv("TEMP", "/tmp"))
                    decrypted_path = temp_dir / "tunnel.toml"
                    decrypted_path.write_text(decrypted_content, encoding="utf-8")
                    config_path = str(decrypted_path)

                except Exception as e:
                    self.print_to_all(f"ET: 解密自定义配置文件失败\n可能是文件损坏或更换了设备，密钥由设备唯一机器码生成\n: {e}")
                    self.signals.finished.emit()
                    return
                
            if not os.path.exists(config_path):
                self.print_to_all(f"错误：找不到用户配置文件 {config_path}！\n请重新设置文件路径或在设置中关闭自定义配置模式！")
                self.signals.finished.emit()
                return
        else:
            config_path = os.path.join(state.config_dir, "easytier.toml")
            self.check_config_exist(config_path)

        r = self.check_et_exist()
        if not r:
            return  # 找不到EasyTier Core

        if state.et_en_userconf == 1:
            self.print_to_all(f"ET: 启动Easytier，使用自定义配置文件 {config_path}...")
        else:
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
             config_path],
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

            if any(k in line for k in ("network_secret = ", "instance_name", "uri", "network_name = ")):
                continue

            # 成功启动
            text = "ET: 共享隧道已创建成功，可切换至'隧道日志'查看详情！\nET: 分享时请告知对方您的IP地址以及密码" if self.mode == "server" else "正在连接到绳网...可切换至'隧道日志'查看详情！"
            if "starting easytier" in lower_line:
                self.signals.print_text.emit(text)
                connect_times = 0
                self.start_webui()
                os.remove(config_path) if state.et_en_userconf == 1 and os.path.basename(config_path) == "tunnel.toml" else None

            if "new peer connection added" in lower_line and self.mode == "client":
                self.signals.print_text.emit("ET: 已连接到绳网节点，即将添加路由...\nET: 正在创建TUN网卡，请耐心等待...")
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
                    self.signals.print_text.emit("ET: 绳网节点无响应，重新连接中...")
                
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
                    try:
                        self.signals.print_text.emit(
                            f"""ET: {line.split('remote_addr: Some(Url { url: "wg://')[1].split(':')[0]} 已断开连接！""")
                    except Exception:
                        self.signals.print_text.emit("ET: 节点已断开连接！")

            # 检测错误
            if any(k in lower_line for k in ("panic", "stopping", "error")) and output:
                self.signals.print_text.emit(
                    f"隧道故障：{line}，请切换至'隧道日志'查看详情！"
                )

                if "stopping" in lower_line:
                    self.signals.finished.emit()

            self.signals.print_text_et.emit(line)
