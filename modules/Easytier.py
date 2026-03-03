from PyQt5.QtCore import QThreadPool, pyqtSignal, QRunnable

from modules.State import global_state
from modules.Working_signals import WorkerSignals

import subprocess
import os 

state = global_state()

class easytier_thread(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()
    def check_config_exist(self):
        easytier_config_path = os.path.join(state.config_dir, "easytier.toml")

        toml = f'''
instance_name = "InterKnot"
ipv4 = "10.114.114.10/24"
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
        with open(easytier_config_path, "w") as f:
            f.write(toml)

    def check_et_exist(self):
        self.easytier_executable = os.path.join(os.getcwd(), "easytier", "easytier-core.exe")
        if not os.path.exists(self.easytier_executable):
            self.signals.print_text_et.emit("错误：找不到 EasyTier Core！请重新安装绳网！")
            self.signals.print_text.emit("错误：找不到 EasyTier Core！请重新安装绳网！")
            self.signals.finished.emit()
            return False
        return True
    def run(self):
        self.check_config_exist()
        r = self.check_et_exist()
        if not r:
            return # 找不到EasyTier Core
        
        self.signals.print_text_et.emit(f"启动绳网共享进程...")

        process = subprocess.Popen(
            [self.easytier_executable,
            "-c",
            os.path.join(state.config_dir, "easytier.toml")],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            text=True
        )

        output = True

        for line in process.stdout:
            line = line.strip()
            lower_line = line.lower()

            # 先检测错误（不受 output 控制）
            if "panic" in lower_line or "stopping" in lower_line:
                self.signals.print_text.emit(
                    f"隧道出错：{line}，请切换至'隧道日志'查看详情！"
                )

            # 控制 TOML 屏蔽区
            if "############### TOML ###############" in line:
                output = False
                continue

            if "-----------------------------------" in line:
                output = True
                continue

            # 成功检测
            if "starting easytier" in lower_line:
                self.signals.print_text.emit(
                    "共享隧道已创建成功，可切换至'隧道日志'查看详情！"
                )

            # 输出日志
            if output:
                self.signals.print_text_et.emit(line)