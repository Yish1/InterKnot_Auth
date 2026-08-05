import requests
import json
from PyQt5.QtCore import QRunnable

from modules.State import global_state
from modules.Working_signals import WorkerSignals
from modules.Decrypt_cmxztunnel import decrypt_cmxztunnel

state = global_state()


class TunnelThread(QRunnable):
    def __init__(self, password, url):
        super().__init__()
        self.signals = WorkerSignals()
        self.password = password
        self.url = url

    def run(self):

        try:
            filename = self.url.rsplit("/", 1)[-1]
        except:
            filename = self.url

        headers = {
            'User-Agent': 'CMXZ-SAC_%s_%s' % (state.version, filename)
        }

        try:
            r = requests.post(
                url=self.url,
                data={"password": self.password},
                headers=headers,
                timeout=5,
                proxies={"http": None, "https": None},
            )

            r.raise_for_status()

            # 解析 JSON
            try:
                data = r.json()
            except Exception:
                raise Exception(
                    f"服务器返回非法内容: {r.text[:200]}"
                )

            if data.get("status") != "success":
                raise Exception(data.get("message", "服务器返回错误"))

            # 获取节点说明
            description = data.get("description", "")
            print(f"隧道描述: {description}")

            # 解码配置
            config = decrypt_cmxztunnel(data["config"], self.password)

            if config is None:
                raise Exception("解密后的内容为None，可能是密钥错误或已吊销")

            self.signals.tunnel_config.emit(
                "success",
                config,
                self.password,
                self.url,
                description
            )

        except Exception as e:
            if "403" in str(e):
                self.signals.show_message.emit(
                    "密钥错误或已吊销，请重新输入密钥！",
                    "错误"
                )
            else:
                self.signals.show_message.emit(
                    f"获取隧道配置失败: {e}",
                    "错误"
                )

            self.signals.tunnel_config.emit(
                "fail",
                str(e),
                self.password,
                self.url,
                ""
            )

        self.signals.finished.emit()