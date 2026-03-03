from PyQt5.QtCore import QThreadPool, pyqtSignal, QRunnable

from modules.State import global_state
from modules.Working_signals import WorkerSignals

import subprocess
import os 

state = global_state()

class EasyTier(QRunnable):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()
    def check_config_exist(self):
        easytier_config_path = os.path.join(state.config_dir, "easytier.toml")

        if os.path.exists(easytier_config_path) is False:
            toml = f'''
                instance_name = "Misaka_Network"
                ipv4 = "10.114.114.10/24"
                dhcp = false
                listeners = ["wg://0.0.0.0:{state.et_port}"]

                [network_identity]
                network_name = "Misaka_Network"
                network_secret = "{state.et_secret_key}"

                [flags]
                bind_device = {state.et_bind_device}
                dev_name = "Misaka_Network"
                enable_exit_node = true
                enable_ipv6 = {state.et_enable_ipv6}
                '''
            with open(easytier_config_path, "w") as f:
                f.write(toml)

    def run(self):
        self.check_config_exist()
