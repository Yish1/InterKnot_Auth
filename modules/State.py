# 管理全局变量
import os
from PyQt5.QtCore import QThreadPool


class global_state:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True

        self.version = 1.67

        # 获取用户 AppData\Roaming 路径
        self.config_path = None
        # 通常是 C:\Users\<用户名>\AppData\Roaming
        appdata_dir = os.getenv("APPDATA")
        self.config_dir = os.path.join(appdata_dir, "SAC")
        self.config_path = os.path.join(self.config_dir, "config.ini")
        self.log_path = os.path.join(self.config_dir, "log.txt")

        # 配置类变量
        self.first_run = 1
        self.username = None
        self.password = None
        self.esurfingurl = None
        self.wlanacip = None
        self.wlanuserip = None
        self.save_pwd = None
        self.auto_connect = None
        self.wtg_timeout = None
        self.enable_watch_dog = True
        self.login_mode = 0
        self.mulit_login = 1
        self.mulit_info = {}
        self.enable_easytier = None
        self.auto_share = False
        self.auto_update_userip = None # 自动检查用户IP是否变化的开关位

        # EasyTier相关配置
        self.et_port = 51145
        self.et_webui_port = 50000
        self.et_secret_key = "Hello_InterKnot"
        self.et_enable_ipv6 = False
        self.et_enable_webdl = True

        # 运行时变量
        self.stop_watch_dog = False
        self.connected = False
        self.jar_login = False
        self.signature = ""
        self.retry_thread_started = False
        self.stop_retry_thread = False
        self.watch_dog_thread_started = False
        self.new_version_checked = False
        self.login_thread_finished = False
        self.mulit_status = {}
        self.mulit_login_active = False
        self.settings_flag = None
        self.webui_thread = None
        self.login_in_progress = False

        # 初始化线程池
        self.threadpool = QThreadPool()

        # RSA公钥
        self.rsa_public_key = """
            -----BEGIN PUBLIC KEY-----
            MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCyhncn4Z4RY8wITqV7n6hAapEM
            ZwNBP6fflsGs3Ke5g6Ji4AWvNflIXZLNTGIuykoU1v2Bitylyuc9nSKLTvBdcytB
            +4X4CvV4oVDr2aLrXs7LhTNyykcxyhyGhokph0Cb4yR/mybK6OeH2ME1/AZS7AZ4
            pe2gw9lcwXQVF8DJwwIDAQAB
            -----END PUBLIC KEY-----
            """


app_state = global_state()
