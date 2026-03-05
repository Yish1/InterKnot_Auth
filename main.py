import re
import os
import sys
import ctypes
import requests
import rsa
import json
import time
import win32com.client
import msvcrt
import ipaddress
# import debugpy
import builtins
import threading
import binascii
import subprocess
from io import BytesIO
from PIL import Image, ImageFilter
import ddddocr
import webbrowser as web
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QSystemTrayIcon, QMenu, QAction, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt5.QtCore import QThreadPool, pyqtSignal, QRunnable, QObject
from Ui.Main_UI import Ui_MainWindow  # 导入ui文件
from Ui.Settings import Ui_sac_settings

from modules import *

state = global_state()
# debugpy.listen(("0.0.0.0", 5678))
# debugpy.wait_for_client()  # 等待调试器连接


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.setWindowTitle(f"绳网 {state.version}")
        self.setWindowIcon(QtGui.QIcon(':/icon/yish.ico'))
        self.menubar.removeAction(self.menu.menuAction())
        self.run_settings_action = QtWidgets.QAction("设置", self)
        self.menubar.addAction(self.run_settings_action)

    def __init__(self):

        super().__init__()
        self.setupUi(self)  # 初始化UI
        # self.setMinimumSize(QtCore.QSize(296, 705))
        self.progressBar.hide()

        self.tray_icon = QSystemTrayIcon(QtGui.QIcon(':/icon/yish.ico'), self)
        self.tray_icon.setToolTip(f"InterKnot_Auth {state.version}")
        # 连接单击托盘图标的事件
        self.tray_icon.activated.connect(self.on_tray_icon_clicked)

        # 托盘菜单
        tray_menu = QMenu(self)
        restore_action = QAction("恢复", self)
        quit_action = QAction("退出", self)
        self.close_now = False
        restore_action.triggered.connect(self.showNormal)
        quit_action.triggered.connect(
            lambda: (setattr(self, 'close_now', True), self.close()))

        tray_menu.addAction(restore_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # 启动前运行
        self.read_config()
        self.init_save_password()
        self.try_auto_connect()

        # 初始化Setting
        self.settings_window = settingsWindow(self)

        # 绑定按钮功能
        self.pushButton.clicked.connect(self.login)
        self.pushButton_2.clicked.connect(self.logout)
        self.checkBox.clicked.connect(lambda: self.update_config(
            "save_pwd", 1 if self.checkBox.isChecked() else 0))
        self.checkBox_2.clicked.connect(lambda: self.update_config(
            "auto_connect", 1 if self.checkBox_2.isChecked() else 0) or (
                self.update_list("开机将自启，并自动登录，需要记住密码\n看门狗每10分钟检测一次网络连接情况\n下次自动登录成功时，将启动看门狗") if self.checkBox_2.isChecked() else None) or (
                self.checkBox.setChecked(True) if self.checkBox_2.isChecked() else None) or (
                    self.add_to_startup() if self.checkBox_2.isChecked() else self.add_to_startup(1)) or (self.update_config("save_pwd", 1))
        )
        self.checkBox_auto_share.clicked.connect(lambda checked: self.enable_auto_share(checked))

        self.checkBox_t.clicked.connect(lambda: self.change_login_mode(1 if self.checkBox_t.isChecked() else 0))

        self.checkBox_dog.clicked.connect(lambda: self.update_config(
            "enable_watch_dog", 1 if self.checkBox_dog.isChecked() else 0) or (self.update_list("看门狗将在下次登录时开启，持续监测网络状态，根据网卡状态智能重连") if self.checkBox_dog.isChecked() else self.update_list("看门狗已禁用")))
        
        self.pushButton_3.clicked.connect(
            lambda: web.open_new("https://cmxz.top"))
        self.run_settings_action.triggered.connect(self.run_settings)
        self.pushButton_4.clicked.connect(self.settings_window.mulit_login_now)
        self.pushButton_enable_share.clicked.connect(lambda: self.start_easytier(True))

        self.update_list("欢迎加入绳网（InterKnot）！")

        # 启动后运行
        self.start_easytier()

    def on_tray_icon_clicked(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # 仅响应左键单击
            self.showNormal()
            self.activateWindow()

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.WindowStateChange:
            if self.isMinimized():
                self.hide()  # 隐藏窗口
                self.tray_icon.showMessage(
                    f"InterKnot_Auth {state.version}",
                    "程序已最小化到托盘",
                    QSystemTrayIcon.Information,
                    2000
                )
        super(MainWindow, self).changeEvent(event)

    def closeEvent(self, event):
        if self.close_now == False:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("退出确认")
            msg_box.setText("您需要退出程序 还是最小化到托盘？")
            msg_box.setIcon(QMessageBox.Question)

            btn_quit = msg_box.addButton("退出", QMessageBox.YesRole)
            btn_minimize = msg_box.addButton("最小化到托盘", QMessageBox.NoRole)

            msg_box.exec_()

            if msg_box.clickedButton() == btn_minimize:
                if state.settings_flag != None:
                    self.update_list("请先关闭设置界面再最小化！")
                    event.ignore()
                    return
                event.ignore()  # 最小化到托盘
                self.hide()  # 隐藏窗口
                self.tray_icon.showMessage(
                    f"InterKnot_Auth {state.version}",
                    "程序已最小化到托盘",
                    QSystemTrayIcon.Information,
                    2000
                )
                return

        # 关闭其他窗口的代码
        try:
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QWidget) and widget != self:
                    widget.close()
        except:
            pass
        state.stop_watch_dog = True
        self.stop_easytier()
        event.accept()

    def init_save_password(self):
        if state.save_pwd == "1" and state.password:
            decrypted_password = ''.join(
                chr(ord(char) - 10) for char in state.password)
            if self.lineEdit_2.text() != "":
                pass
            else:
                self.lineEdit_2.setText(decrypted_password)
        else:
            pass
        self.lineEdit.setText(state.username)

    def add_to_startup(self, mode=None):

        TASK_NAME = "InterKnot_Auth"
        def run(cmd):
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        
        # 当前程序路径
        app_path = sys.argv[0]

        # 检查任务是否存在
        exists = run(["schtasks", "/Query", "/TN", TASK_NAME]).returncode == 0

        if mode == 1:
            # 关闭开机自启
            if exists:
                r = run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
                if r.returncode == 0:
                    self.update_list("开机自启已关闭")
                else:
                    self.update_list(f"关闭失败：{r.stderr or r.stdout}\n尝试以管理员权限运行软件")
            else:
                self.update_list("开机自启项不存在，无需删除。")
            return

        # 开启开机自启
        if exists:
            self.update_list("开机自启已存在")
            return

        cmd = [
            "schtasks",
            "/Create",
            "/TN", TASK_NAME,
            "/TR", f'"{app_path}"',
            "/SC", "ONLOGON",      # 开机启动
            "/RL", "HIGHEST",      # 最高权限
            "/F"
        ]

        r = run(cmd)

        if r.returncode == 0:
            self.update_list(f"已添加 {app_path} 开机自启")
        else:
            self.update_list(f"创建失败：{r.stderr or r.stdout}\n尝试以管理员权限运行软件")

    def try_auto_connect(self):

        self.read_config()
        if state.auto_connect == "1":
            self.update_list("正在尝试自动连接...")

            # 如果登录的方式是隧道，且开启了自动共享，将不会自动登录
            if self.is_ipv4(state.username):
                if state.auto_share:
                    self.update_list("警告：自动共享开启且登录方式为隧道时，将不会自动连接！")
                    return
                
                self.connect_et()
                return

            if not state.username.startswith('t') and state.login_mode == 0:
                state.jar_login = True
            if state.jar_login:
                self.login()
                return

            self.auto_thread = login_Retry_Thread(5)
            self.auto_thread.signals.enable_buttoms.connect(
                self.enable_buttoms)
            self.auto_thread.signals.thread_login.connect(self.login)
            self.auto_thread.signals.finished.connect(
                lambda: self.update_list("结束自动登录线程"))
            state.threadpool.start(self.auto_thread)
            state.retry_thread_started = True
            self.add_to_startup()

        else:
            pass

    def reconnect(self):
        '''重连调用此函数'''
        if state.mulit_login_active == True:
            self.settings_window.mulit_login_now()
        else:
            self.login()

    def mulit_login_mode(self, ip=None, user=None, pwd=None):
        try:
            self.login("mulit", ip, user, pwd)
            state.mulit_login_active = True
        except Exception as e:
            self.update_list(e)

    def run_settings(self):

        if self.settings_window is not None and self.settings_window.isVisible() == False:
            try:
                self.settings_window = settingsWindow(self)
                self.settings_window.run_settings_window()
            except Exception as e:
                self.update_list(f"无法打开设置界面{e}")

        elif self.settings_window is not None and self.settings_window.isVisible() == True:
            print("设置界面已打开，无需重复打开！")
            self.settings_window.activateWindow()

    def read_config(self):
        config = {}

        config = read_config_file(state.config_path)

        # 配置项定义: (属性名, 默认值, 类型转换函数)
        config_maps = [
            ('first_run', 1, int),
            ('username', "", str),
            ('password', "", str),
            ('wlanacip', "0.0.0.0", str),
            ('wlanuserip', "0.0.0.0", str),
            ('esurfingurl', "0.0.0.0:0", str),
            ('save_pwd', "1", str),
            ('auto_connect', "0", str),
            ('wtg_timeout', 5, int),
            ('mulit_login', 1, int),
            ('login_mode', 0, int),
            ('enable_watch_dog', "1", str),
            ('auto_share', "0", str),
            # Easytier
            ('et_secret_key', "Hello_InterKnot", str),
            ('et_enable_ipv6', 0, int)
        ]

        # try:
        for key, default, converter in config_maps:
            value = config.get(key)
            if value:
                setattr(state, key, converter(value))
            else:
                self.update_config(key, default, "w!")
                setattr(state, key, default)

        # 更新UI状态
        self.checkBox.setChecked(state.save_pwd == "1")
        self.checkBox_2.setChecked(state.auto_connect == "1")
        self.checkBox_t.setChecked(state.login_mode != 0)
        self.checkBox_dog.setChecked(state.enable_watch_dog == "1")
        self.checkBox_auto_share.setChecked(state.auto_share == "1")

        if state.first_run == 1:
            self.show_message(message=
                            '欢迎加入绳网（InterKnot）！\n'
                            '在无形的数据洪流之中，我们以结为契，以绳为网，将零散的节点重新编织。绳网源于对效率与自由的追求——让繁琐的认证流程化作一次优雅的连接。\n\n'
                            '借助 EasyTier 的组网能力，已连接的设备还可作为出口节点，在封闭的边界之中，悄然编织属于自己的通路。\n\n'
                            '<a href="https://github.com/Yish1/InterKnot_Auth">'
                            'InterKnot项目地址: Yish1/InterKnot_Auth'
                            '</a>',
                            title="欢迎",
                            first=1)
            self.update_config("first_run", 0)

        # except Exception as e:
        #     self.update_list(f"配置读取失败，已重置为默认值！{e} ")
        #     os.remove(state.config_path)
        #     self.read_config()

        return config

    def update_config(self, variable, new_value, mode=None):
        # delegate to config manager
        update_entry(variable, str(new_value)
                     if new_value is not None else None, state.config_path)
        print(f"更新配置文件：[{variable}]={new_value}\n")

        if mode == "w!":
            pass
        else:
            self.read_config()

    def is_ipv4(self, text):
        try:
            ipaddress.IPv4Address(text)
            return True
        except ipaddress.AddressValueError:
            return False

    def login(self, mode=None, ip=None, user=None, pwd=None):

        username = self.lineEdit.text()
        password = self.lineEdit_2.text()

        if mode == "mulit":
            username = user
            password = pwd
            state.wlanuserip = ip
            current_ip = ip

        state.username = username
        state.password = password

        ipv4_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
        if ipv4_pattern.match(username): # z正则判断是否是ip
            is_ip = self.is_ipv4(username)
            if is_ip:
                self.connect_et()
                # 保存账号密码
                self.save_password()
                self.update_config("username", username)
                return
            else:
                self.update_list("输的啥玩意啊？IP地址有这样写的吗？")
                return
        
        if state.esurfingurl == "0.0.0.0:0" or state.esurfingurl == "自动获取失败,请检查网线连接":
            self.run_settings()
            self.update_list("请先获取或手动填写参数！")
            return
        if not username:
            self.update_list("账号都不输入登录个锤子啊！")
            return
        if not password or password == "0":
            self.update_list("你账号没有密码的吗？？？")
            return

        # 判断是否以 't' 开头，仅适用于SEIG
        if not username.startswith('t') and state.login_mode == 0:
            self.login_jar(username, password,
                           state.wlanuserip, state.wlanacip)
            state.jar_login = True
            return

        def login_status(response):
            data = response.json()
            status = ""
            if data['resultCode'] == "0" or data['resultCode'] == "13002000":
                status = "登录成功"
                state.signature = response.cookies["signature"]
                state.connected = True
                state.stop_retry_thread = False

                self.check_new_version()

                if state.watch_dog_thread_started != True and mode != "mulit":
                    self.run_watch_dog()

            elif data['resultCode'] == "13018000":
                status = "登录失败：已办理一人一号多终端业务的用户，请使用客户端登录"
                self.update_list("已办理一人一号多终端业务的用户，请使用客户端登录")

            else:
                status = f"登录失败: {data['resultInfo']}"
                self.update_list(status)

                if data['resultInfo'] == "用户认证失败" or data['resultInfo'] == "密码错误":
                    state.stop_watch_dog = True
                    state.stop_retry_thread = True
                    if getattr(state, 'retry_thread_started') == True:
                        self.update_list("密码错误，取消自动重试")
                    return

                if data['resultInfo'] == "验证码错误":
                    if mode == "mulit":
                        pass
                    else:
                        try:
                            if state.retry_thread_started == False:
                                state.connected = False
                                self.update_list("验证码识别错误，即将重试...")
                                self.retry_thread = login_Retry_Thread(5, self)
                                self.retry_thread.signals.enable_buttoms.connect(
                                    self.enable_buttoms)
                                self.retry_thread.signals.thread_login.connect(
                                    self.login)
                                self.retry_thread.signals.print_text.connect(
                                    self.update_list)
                                self.retry_thread.signals.finished.connect(
                                    lambda: self.update_list("结束RETRY线程"))
                                state.threadpool.start(self.retry_thread)
                                state.retry_thread_started = True
                        except Exception as e:
                            print(e)

            if mode == "mulit":
                state.mulit_status[current_ip] = status

                if len(state.mulit_status) == len(state.mulit_info):
                    self.update_list("***多拨登录结果汇总***")
                    success = False

                    for ip, stat in state.mulit_status.items():
                        self.update_list(f"{ip} : {stat}")
                        if stat == "登录成功":
                            success = True

                    state.mulit_status = {}
                    if success:
                        self.run_watch_dog()

            else:
                # 保存账号密码
                self.save_password()
                self.update_config("username", username)

        login_thread = login_Thread()
        login_thread.signals.enable_buttoms.connect(
            self.enable_buttoms)
        login_thread.signals.thread_login.connect(
            self.login)
        login_thread.signals.print_text.connect(
            self.update_list)
        login_thread.signals.login_status.connect(
            login_status)
        login_thread.signals.run_settings.connect(
            self.run_settings)
        login_thread.signals.finished.connect(
            lambda: self.update_list("结束登录线程"))
        state.threadpool.start(login_thread)

    def run_watch_dog(self):
        state.stop_watch_dog = False
        watchdog_thread = watch_dog()
        watchdog_thread.signals.update_progress.connect(
            self.update_progress_bar)
        watchdog_thread.signals.print_text.connect(
            self.update_list)
        watchdog_thread.signals.thread_login.connect(
            self.reconnect)
        state.threadpool.start(watchdog_thread)

    def login_jar(self, username, password, userip, acip):
        self.update_list("即将登录: " + username + " IP: " + userip)
        self.enable_buttoms(0)
        try:
            os.remove("logout.signal")
        except:
            pass
        try:
            self.jar_Thread = jar_Thread(
                username, password, userip, acip, mainWindow=self)
            self.jar_Thread.signals.enable_buttoms.connect(self.enable_buttoms)
            # self.jar_Thread.signals.connected_success.connect(
            #     self.update_progress_bar)
            self.jar_Thread.signals.print_text.connect(self.update_list)
            self.jar_Thread.signals.update_check.connect(
                self.check_new_version)
            self.jar_Thread.signals.jar_login_success.connect(
                self.save_password)
            state.threadpool.start(self.jar_Thread)
        except Exception as e:
            self.update_list(f"登录失败：{e}")
            self.enable_buttoms(1)

    def save_password(self):
        if self.checkBox.isChecked():
            password = self.lineEdit_2.text()
            encrypted_password = ''.join(
                chr(ord(char) + 10) for char in password)
            self.update_config("password", encrypted_password)

    def logout(self):

        if hasattr(self, "et_connected") and self.et_connected == True:
            self.stop_easytier()
            return

        state.username = self.lineEdit.text()
        if state.jar_login:
            if not os.path.exists('logout.signal'):
                with open('logout.signal', 'w', encoding='utf-8') as file:
                    file.write("")
            jar_Thread.term_all_processes()
            self.update_list("执行下线操作中, 请稍后...")
            state.jar_login = False
            return

        if state.username and state.signature:
            try:
                response = requests.post(
                    url=f'http://{state.esurfingurl}/ajax/logout',
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0',
                        'Cookie': f'signature={state.signature}; loginUser={state.username}',
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
                    },
                    data=f"wlanuserip={state.wlanuserip}&wlanacip={state.wlanacip}",
                    timeout=3,
                    proxies={"http": None, "https": None},
                    verify=False
                )

                if response.status_code == 200:
                    data = response.json()
                    self.update_list("成功发送下线请求")
                    if data['resultCode'] == "0" or data['resultCode'] == "13002000":
                        state.stop_watch_dog = True
                        self.update_list("下线成功")
                    else:
                        self.update_list(f"下线失败: {data['resultInfo']}")
                else:
                    self.update_list(f"请求失败，状态码：{response.status_code}")
            except Exception as e:
                self.update_list(f"下线失败：{e}")
        else:
            self.update_list("您尚未登录，无需下线！")

    def enable_buttoms(self, mode):
        if mode == 0:
            self.lineEdit.setEnabled(False)
            self.lineEdit_2.setEnabled(False)
            self.pushButton.setEnabled(False)
            self.pushButton_2.setEnabled(False)
        if mode == 1:
            self.lineEdit.setEnabled(True)
            self.lineEdit_2.setEnabled(True)
            self.pushButton.setEnabled(True)
            self.pushButton_2.setEnabled(True)

    def update_progress_bar(self, mode, value, value2):
        self.progressBar.setValue(value)
        self.progressBar.setMaximum(value2)
        if mode == 1:
            self.progressBar.show()
        elif mode == 0:
            self.progressBar.hide()

    def update_list(self, text):

        # 超过 1000 行，就从前面开始删除
        if self.listWidget.count() >= 1000:
            self.listWidget.takeItem(0)

        self.listWidget.addItem(text)
        self.listWidget.setCurrentRow(self.listWidget.count() - 1)
        print(text)

    def update_et_list(self, text):
        
        # 超过 1000 行，就从前面开始删除
        if self.listWidget_easytier.count() >= 1000:
            self.listWidget_easytier.takeItem(0)

        self.listWidget_easytier.addItem(text)
        self.listWidget_easytier.setCurrentRow(self.listWidget_easytier.count() - 1)
        print(text)

    def check_new_version(self):
        if state.new_version_checked: return
        
        self.update_thread = UpdateThread()
        state.threadpool.start(self.update_thread)
        self.update_thread.signals.show_message.connect(
            self.update_message)
        self.update_thread.signals.print_text.connect(
            self.update_list)
        self.update_thread.signals.logout.connect(self.logout)
        # self.update_thread.signals.finished.connect(
        #     lambda: self.update_list("检查更新线程结束"))

    def update_message(self, message):  # 更新弹窗
        msgBox = QMessageBox()
        msgBox.setWindowTitle("检测到新版本！")
        msgBox.setText(message)
        msgBox.setWindowIcon(QtGui.QIcon(':/icon/yish.ico'))
        okButton = msgBox.addButton("立刻前往", QMessageBox.AcceptRole)
        noButton = msgBox.addButton("下次一定", QMessageBox.RejectRole)
        msgBox.exec_()
        clickedButton = msgBox.clickedButton()
        if clickedButton == okButton:
            os.system("start https://cmxz.top/SAC")
        else:
            self.update_list("检测到新版本！")

    def show_message(self, message, title, first=None):
        msgBox = QMessageBox()
        msgBox.setWindowTitle(title)
        msgBox.setWindowIcon(QtGui.QIcon(':/icon/yish.ico'))
        if message is None:
            message = "未知错误"
        message = str(message)
        
        if first == 1:
            msgBox.setIconPixmap(QtGui.QIcon(
                ':/icon/yish.ico').pixmap(100, 100))
            msgBox.setTextFormat(QtCore.Qt.RichText)
            lines = message.split('\n', 1)
            remaining = lines[1].replace('\n', '<br>')
            message = f'<h2 style="margin: 0; padding: 0;">{lines[0]}</h2><br>{remaining}'
    
        msgBox.setText(message)
        msgBox.exec_()

    def change_login_mode(self, mode):

        if mode == 0:
            self.update_list("已切换为自动识别模式")
            state.login_mode = 0
            self.update_config("login_mode", "0")
        elif mode == 1:
            self.update_list("已切换为t模式")
            state.login_mode = 1
            self.update_config("login_mode", "1")

    def start_easytier(self, start=False):
        if state.auto_share == "1" or start:
            if hasattr(self, "et_connected") and self.et_connected == True:
                self.show_message(message="您已连接隧道，如需启动共享需先断开隧道!", title="错误")
                return
            
            try:
                self.pushButton_enable_share.setText("停止共享")
                self.pushButton_enable_share.clicked.disconnect()
                self.pushButton_enable_share.clicked.connect(lambda: self.stop_easytier())

                self.easytier_thread = easytier_thread(self, mode = "server")
                self.easytier_thread.signals.print_text.connect(self.update_list)
                self.easytier_thread.signals.print_text_et.connect(self.update_et_list)
                self.easytier_thread.signals.finished.connect(self.stop_easytier)
                state.threadpool.start(self.easytier_thread)
            except Exception as e:
                self.update_list(f"启动隧道失败：{e}")

    def stop_easytier(self):
        try:
            if hasattr(self.et_process, "terminate"):
                self.et_process.terminate()
                self.et_process = None
                self.update_list("ET: 已停止隧道")
        
                self.pushButton_enable_share.setText("启用共享")
                self.pushButton_enable_share.clicked.disconnect()
                self.pushButton_enable_share.clicked.connect(lambda: self.start_easytier(True))
                self.pushButton.setEnabled(True)

                if hasattr(self, 'et_connected') and self.et_connected:
                    self.remove_et_route()
                    
                self.et_connected = False
                
        except Exception as e:
            self.update_list(f"ET: 停止隧道失败：{e}")

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
            self.update_list("ET: 路由删除成功")
        else:
            self.update_list(f"ET: 路由删除失败: {result.stderr}")

    def connect_et(self):
        try:
            # 检查是否有启动服务端
            if hasattr(self, 'et_process') and self.et_process != None:
                self.show_message(message="您已启动共享，如需连接隧道需先停止共享!", title="错误")
                self.pushButton.setEnabled(True)
                return

            # 禁用登录按钮
            self.pushButton.setEnabled(False)

            self.easytier_thread = easytier_thread(self, mode = "client")
            self.easytier_thread.signals.print_text.connect(self.update_list)
            self.easytier_thread.signals.print_text_et.connect(self.update_et_list)
            self.easytier_thread.signals.finished.connect(self.stop_easytier)
            state.threadpool.start(self.easytier_thread)
            self.et_connected = True

        except Exception as e:
            self.update_list(f"连接隧道失败：{e}")

    def enable_auto_share(self, checked):
        self.update_config("auto_share", 1 if self.checkBox_auto_share.isChecked() else 0)
        self.update_list("已开启自动共享，启动时将自动启动隧道") if self.checkBox_auto_share.isChecked() else self.update_list("已关闭自动共享")

        # 如果账号框里时ip，弹出警告
        if self.is_ipv4(self.lineEdit.text()) and checked:
            self.show_message(message="当前登录方式为隧道，开启自动共享后自动登录将不会连接隧道！\n\n连接隧道与共享网络是冲突的！", title="警告")

class login_Retry_Thread(QRunnable):
    def __init__(self, times, parent=None):
        super().__init__()
        self.signals = WorkerSignals()
        self.times = times
        # self.parent = parent

    def run(self):

        # debugpy.breakpoint()
        self.signals.enable_buttoms.emit(0)

        while self.times > 0 and state.stop_retry_thread == False:
            time.sleep(3)
            if state.connected == True:
                state.retry_thread_started = False
                self.signals.enable_buttoms.emit(1)
                self.signals.finished.emit()
                return

            # if hasattr(self.parent, 'thread_stop_flag') and self.parent.thread_stop_flag == True: # 外部停止线程
            #     self.signals.enable_buttoms.emit(1)
            #     state.retry_thread_started = False
            #     self.signals.finished.emit()
            #     self.signals.print_text.emit(f"验证码错误，但此账号认证失败，因此不重试")
            #     return

            self.signals.print_text.emit(f"登录失败,还剩{self.times}次尝试")
            self.times -= 1
            self.signals.thread_login.emit()

        if state.connected == False:
            state.retry_thread_started = False
            self.signals.print_text.emit("已多次尝试无法获取验证码，这一般不是验证码的问题，请重试或者反馈")

        self.signals.enable_buttoms.emit(1)
        self.signals.finished.emit()


if __name__ == "__main__":
    try:
        # 防止重复运行
        lock_file = os.path.expanduser("~/.Seig-auto-connect.lock")
        fd = os.open(lock_file, os.O_RDWR | os.O_CREAT)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            os.close(fd)
            user32 = ctypes.windll.user32
            result = user32.MessageBoxW(
                None,
                "另一个绳网认证器正在运行。\n是否继续运行？\n\nAnother InterKnot_Auth is already running.\nDo you want to continue?",
                "Warning!",
                0x31
            )
            if result == 2:
                sys.exit()  # 退出程序
            elif result == 1:
                print("用户选择继续运行。")

        # 启用 Windows DPI 感知（优先 Per-Monitor V2，回退到 System Aware）
        if sys.platform == "win32":
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(
                    2)  # PROCESS_PER_MONITOR_DPI_AWARE
            except Exception:
                try:
                    print("启用 Windows DPI 感知失败，尝试回退到系统感知。")
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

        # Qt 高 DPI 设置（需在创建 QApplication 之前）
        # 自动根据屏幕缩放因子调整
        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
        # 缩放舍入策略（Qt 5.14+ 生效）
        # 注意：在 Windows 7 上启用 PassThrough 会导致文字不显示，这里仅在 Win10+ 启用
        if hasattr(QtGui, "QGuiApplication") and hasattr(QtCore.Qt, "HighDpiScaleFactorRoundingPolicy"):
            try:
                ok_to_set = True
                if sys.platform == "win32":
                    try:
                        v = sys.getwindowsversion()
                        # 仅在 Windows 10 及以上启用（Windows 7/8/8.1 跳过）
                        ok_to_set = (v.major >= 10)
                    except Exception:
                        ok_to_set = False
                if ok_to_set:
                    QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
                        QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
                    )
                else:
                    print("跳过设置 HighDpiScaleFactorRoundingPolicy")
            except Exception:
                pass

        if hasattr(QtCore.Qt, "AA_EnableHighDpiScaling"):
            QtWidgets.QApplication.setAttribute(
                QtCore.Qt.AA_EnableHighDpiScaling, True)
        # 启用高DPI自适应
        if hasattr(QtCore.Qt, "AA_UseHighDpiPixmaps"):
            QtWidgets.QApplication.setAttribute(
                QtCore.Qt.AA_UseHighDpiPixmaps, True)

        app = QtWidgets.QApplication(sys.argv)
        mainWindow = MainWindow()
        mainWindow.show()
        sys.exit(app.exec_())

    except Exception as e:
        user32 = ctypes.windll.user32
        user32.MessageBoxW(None, f"程序启动时遇到严重错误:{e}", "Warning!", 0x30)
        sys.exit()

# 编译指令
# '''nuitka --standalone --lto=yes --msvc=latest --disable-ccache `
# --windows-console-mode=disable `
# --windows-uac-admin `
# --enable-plugin=pyqt5,upx `
# --upx-binary="F:/Programs/upx/upx.exe" `
# --include-data-dir=ddddocr=ddddocr `
# --include-data-dir=jre=jre `
# --include-data-dir=easytier=easytier `
# --include-data-file=easytier\easytier-core.exe=easytier\easytier-core.exe `
# --include-data-file=easytier\Packet.dll=easytier\Packet.dll `
# --include-data-file=easytier\wintun.dll=easytier\wintun.dll `
# --include-data-file=login.jar=login.jar `
# --include-package=modules `
# --output-dir=SAC `
# --windows-icon-from-ico=yish.ico `
# --nofollow-import-to=unittest `
# --output-filename=绳网认证.exe `
# --remove-output `
# --assume-yes-for-downloads `
# --python-flag=no_docstrings `
# main.py'''