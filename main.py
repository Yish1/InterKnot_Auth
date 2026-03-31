import re
import os
import sys
import ctypes
import requests
import time
import msvcrt
import ipaddress
# import debugpy
import zipfile
import threading
import subprocess
import tempfile
import shutil
import traceback
import webbrowser as web
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QSystemTrayIcon, QMenu, QAction, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt5.QtCore import QThreadPool, pyqtSignal, QRunnable, QObject, Qt
from PyQt5.QtGui import QColor

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
        self.menubar.insertAction(None, self.run_settings_action)
        self.menu_2.menuAction().setVisible(False)
        self.action_3.triggered.connect(
            lambda: os.system("start http://localhost:50000"))

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
        try:
            self.init_log()
            self.update_list(f"欢迎加入绳网（InterKnot）！\nV{state.version}")
            self.read_config()
            self.get_password()
            self.add_account_to_combox()

            # 初始化Setting
            self.settings_window = settingsWindow(self)

            # 绑定按钮功能
            self.pushButton.clicked.connect(self.login)
            self.pushButton_2.clicked.connect(self.logout)
            self.checkBox.clicked.connect(lambda checked: (self.update_config(
                "save_pwd", "1" if checked else "0") or self.init_save_password(checked)))

            self.checkBox_2.clicked.connect(lambda: self.update_config(
                "auto_connect", 1 if self.checkBox_2.isChecked() else 0) or (
                    self.checkBox.setChecked(True) if self.checkBox_2.isChecked() else None) or (
                        self.add_to_startup() if self.checkBox_2.isChecked() else self.add_to_startup(1)) or (self.update_config("save_pwd", 1))
            )
            self.checkBox_auto_share.clicked.connect(
                lambda checked: self.enable_auto_share(checked))

            self.checkBox_t.clicked.connect(lambda: self.change_login_mode(
                1 if self.checkBox_t.isChecked() else 0))

            self.checkBox_dog.clicked.connect(lambda: self.update_config(
                "enable_watch_dog", 1 if self.checkBox_dog.isChecked() else 0) or (self.update_list("看门狗将在下次登录时开启，持续监测网络状态，根据网卡状态智能重连") if self.checkBox_dog.isChecked() else self.update_list("看门狗已禁用")))

            self.pushButton_3.clicked.connect(
                lambda: web.open_new("https://cmxz.top"))
            self.run_settings_action.triggered.connect(self.run_settings)
            self.pushButton_4.clicked.connect(self.settings_window.mulit_login_now)
            self.pushButton_enable_share.clicked.connect(
                lambda: self.start_easytier(True))

            self.comboBox_username.currentTextChanged.connect(self.on_user_changed)
            view = self.comboBox_username.view()
            view.setContextMenuPolicy(Qt.CustomContextMenu)
            view.customContextMenuRequested.connect(self.show_combo_menu)

            # 启动后运行
            self.try_auto_connect()
            self.start_easytier()

        except Exception as e:
            trace = traceback.format_exc()
            detail = (
                "启动时发生严重错误：请尝试清除配置文件、重装程序，或者联系开发者(Github/Yish1)。"
                f"\n\n详细信息：\n{trace}"
            )
            self.write_to_log(detail)
            self.show_message(detail, "错误")
            sys.exit()

    def init_log(self):
        os.makedirs(state.config_dir, exist_ok=True)
        with open(state.log_path, "w", encoding="utf-8") as f:
            f.write("")

    def write_to_log(self, text):
        os.makedirs(state.config_dir, exist_ok=True)
        with open(state.log_path, "a", encoding="utf-8") as f:
            f.write(text + "\n")
        print(text)

    def show_combo_menu(self, pos):
        view = self.comboBox_username.view()
        index = view.indexAt(pos)

        if not index.isValid():
            return

        row = index.row()
        username = self.comboBox_username.itemText(row)

        reply = QMessageBox.question(
            self,
            "删除保存的账号",
            f"确定删除账号 {username} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 删除UI项
            self.comboBox_username.blockSignals(True)
            self.comboBox_username.removeItem(row)
            self.comboBox_username.blockSignals(False)
            # 删除凭据管理器中的密码
            SecurityManager.delete_password(username)

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
        self.cleanup_temp_interknot()
        event.accept()

    def cleanup_temp_interknot(self):
        temp_dir = os.path.join(tempfile.gettempdir(), "InterKnot")
        if not os.path.exists(temp_dir):
            return

        try:
            shutil.rmtree(temp_dir)
            self.update_list(f"已清理临时目录: {temp_dir}")
        except Exception as e:
            self.update_list(f"清理临时目录失败: {e}")

    def get_password(self):
        if state.save_pwd != "1":
            return

        aes_key = SecurityManager.get_encryption_key()

        if state.password != aes_key.hex() and state.password != "":
            self.update_list(
                "检测到设备已更换或未保存有效密码，请重新输入密码！\nInterKnot_Auth 密码采用机器指纹加密，与设备绑定，设备变化将无法解密")

        elif state.password == aes_key.hex():
            password = SecurityManager.get_password(state.username)
            self.lineEdit_2.setText(password if password else "")
            # print(f"成功获取密码: {password}")

    def init_save_password(self, checked=True):
        if checked and state.save_pwd == '1':
            # 新加密流程：保存hashed机器码到password项，使用hashed机器码作为密钥，真密码加密保存到windows凭据管理器，解密时调用
            try:
                aes_key = SecurityManager.get_encryption_key()
                self.update_config("password", aes_key.hex())

                password = self.lineEdit_2.text()

                username = self.comboBox_username.currentText()
                SecurityManager.save_password(username, password)

            except Exception as e:
                if hasattr(self, "auto_connect_flag_for_pwd") and self.auto_connect_flag_for_pwd:  # 忽略开机自启时出现的错误
                    self.auto_connect_flag_for_pwd = False
                    return
                # 1312, 'credwrite', '指定的登录会话不存在。可能已被终止
                e = f"保存密码失败：{e}\n如果当前程序是开机自启的，可以稍等一会，或尝试关闭重开，如无法解决，请带上报错发送issues" # 开机自启时，密码会保存失败一次，后续一般没有问题
                self.update_list(e)

        elif checked == False:
            all_account = DatManager.list_usernames()
            for account in all_account:
                SecurityManager.delete_password(account)
            self.update_config("password", "")

    def add_account_to_combox(self):
        # 获取所有已保存的账号
        current_accounts = self.comboBox_username.currentText()

        # 清除列表
        self.comboBox_username.clear()

        accounts = DatManager.list_usernames()
        if accounts is not None:  # 将保存的账号添加到下拉框中
            for username in accounts:
                self.comboBox_username.addItem(username)

            if current_accounts != '':
                self.comboBox_username.setCurrentText(current_accounts)

            elif state.username in accounts:  # 选择配置文件中的账号
                index = self.comboBox_username.findText(state.username)
                if index != -1:
                    self.comboBox_username.setCurrentIndex(index)

            else:
                self.comboBox_username.setCurrentText(state.username)

            # 添加提示
            self.comboBox_username.addItem("—右键单击可删除账号—")

            # 禁用提示
            item = self.comboBox_username.model().item(self.comboBox_username.count() - 1)
            item.setEnabled(False)
            item.setForeground(QColor(150, 150, 150))

    def on_user_changed(self, username):
        if username == "":
            return

        password = SecurityManager.get_password(username)
        self.lineEdit_2.setText(password if password else "")

        self.comboBox_username.blockSignals(True)
        self.add_account_to_combox()
        self.comboBox_username.blockSignals(False)

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
                    self.update_list(
                        f"关闭失败：{r.stderr or r.stdout}\n尝试以管理员权限运行软件")
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
            self.update_list(f"已添加 {app_path} 开机自启，并自动登录。")

        else:
            self.update_list(f"创建开机自启失败：{r.stderr or r.stdout}\n尝试以管理员权限运行软件")

    def update_login_config(self):
        self.update_list("正在重新获取登录IP......")
        self.settings_window.get_default()
        self.update_config('esurfingurl', str(state.esurfingurl))
        self.update_config('wlanuserip', str(state.wlanuserip))
        self.update_config('wlanacip', str(state.wlanacip))

    def try_auto_connect(self):

        self.read_config()
        if state.auto_update_userip == "1":
            self.update_login_config()

        if state.auto_connect == "1":
            self.update_list("正在尝试自动连接...")
            self.auto_connect_flag_for_pwd = True

            # 如果登录的方式是隧道，且开启了自动共享，将不会自动登录
            if self.is_ipv4(state.username):
                if state.auto_share == "1":
                    self.update_list("警告：自动共享开启且登录方式为隧道时，将不会自动连接！")
                    return

                self.connect_et()
                return

            if not state.username.startswith('t') and state.login_mode == 0:
                state.jar_login = True
            if state.jar_login:
                self.login()
                return

            auto_login_thread = login_Retry_Thread(5)
            auto_login_thread.signals.enable_buttoms.connect(
                self.enable_buttoms)
            auto_login_thread.signals.thread_login.connect(self.login)
            auto_login_thread.signals.print_text.connect(
                self.update_list)
            auto_login_thread.signals.finished.connect(
                lambda: self.update_list("结束自动登录线程"))
            state.threadpool.start(auto_login_thread)
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

        if hasattr(self, "settings_window") == False:
            return

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
            ('auto_update_userip', "0", str),
            # Easytier
            ('et_secret_key', "Hello_InterKnot", str),
            ('et_enable_ipv6', 0, int),
            ('et_enable_webdl', 1, int),
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
            self.show_message(message='欢迎加入绳网（InterKnot）！\n'
                              '在无形的数据洪流之中，我们以结为契，以绳为网，将零散的节点重新编织。绳网源于对效率与自由的追求——让繁琐的认证流程化作一次优雅的连接。\n\n'
                              '借助 EasyTier 的组网能力，已连接的设备还可作为出口节点，在封闭的边界之中，悄然编织属于自己的通路。\n\n'
                              '<a href="https://github.com/Yish1/InterKnot_Auth">'
                              'InterKnot项目地址: Yish1/InterKnot_Auth'
                              '</a>',
                              title="欢迎",
                              first=1)
            self.update_config("first_run", 0)
            self.remove_useless_config(state.config_path)

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

    def remove_useless_config(self, file_path):
        pattern = re.compile(r"\[line_edit_\d+_3\]")

        new_lines = []

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if pattern.match(line.strip().split("=")[0]):
                    continue
                new_lines.append(line)

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    def is_ipv4(self, text):
        try:
            ipaddress.IPv4Address(text)
            return True
        except ipaddress.AddressValueError:
            return False

    def login(self, mode=None, ip=None, user=None, pwd=None):

        username = self.comboBox_username.currentText()
        password = self.lineEdit_2.text()
        current_ip = state.wlanuserip

        if mode == "mulit":
            username = user
            password = pwd
            current_ip = ip

        state.username = username
        state.password = password

        ipv4_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
        if ipv4_pattern.match(username):  # z正则判断是否是ip
            is_ip = self.is_ipv4(username)
            if is_ip:
                self.connect_et()
                # 保存账号密码
                self.init_save_password()
                self.update_config("username", username)
                return
            else:
                self.update_list("输的啥玩意啊？IP地址有这样写的吗？")
                state.stop_retry_thread = True
                return

        if state.esurfingurl == "0.0.0.0:0" or state.esurfingurl == "自动获取失败,请检查网线连接":
            self.run_settings()
            self.update_list("请先获取或手动填写参数！")
            state.stop_retry_thread = True
            return
        if not username:
            state.stop_retry_thread = True
            self.update_list("账号都不输入登录个锤子啊！")
            return
        if not password or password == "0":
            state.stop_retry_thread = True
            self.update_list("你账号没有密码的吗？？？")
            return

        # 判断是否以 't' 开头，仅适用于SEIG
        if not username.startswith('t') and state.login_mode == 0:
            self.login_jar(username, password,
                           current_ip, state.wlanacip)
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
                error_msg = ["认证失败", "过于频繁", "没有定购此产品", "密码错误"]

                matched_key = next((key for key in error_msg if key in status), None)

                if matched_key:
                    if mode != "mulit":
                        state.stop_watch_dog = True
                        state.stop_retry_thread = True
                        if getattr(state, 'retry_thread_started', False):
                            self.update_list(f"由于{matched_key},取消自动重试")
                        return
                
                if data['resultInfo'] == "验证码错误":
                    if mode == "mulit":
                        pass
                    else:
                        try:
                            if state.retry_thread_started == False:
                                state.connected = False
                                self.update_list("验证码识别错误，即将重试...")
                                retry_thread = login_Retry_Thread(5)
                                retry_thread.signals.enable_buttoms.connect(
                                    self.enable_buttoms)
                                retry_thread.signals.thread_login.connect(
                                    self.login)
                                retry_thread.signals.print_text.connect(
                                    self.update_list)
                                retry_thread.signals.finished.connect(
                                    lambda: self.update_list("结束RETRY线程"))
                                state.threadpool.start(retry_thread)
                                state.retry_thread_started = True
                        except Exception as e:
                            print(e)

            state.login_in_progress = False

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
                self.init_save_password()
                self.update_config("username", username)

        login_thread = login_Thread(current_ip=current_ip)
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
            lambda: (setattr(state, 'login_in_progress', False), self.update_list("结束登录线程")))
        state.login_in_progress = True
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
                self.init_save_password)
            state.threadpool.start(self.jar_Thread)
        except Exception as e:
            self.update_list(f"登录失败：{e}")
            self.enable_buttoms(1)

    def logout(self):

        if hasattr(self, "et_connected") and self.et_connected == True:
            self.stop_easytier()
            return

        state.username = self.comboBox_username.currentText()
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
            self.comboBox_username.setEnabled(False)
            self.lineEdit_2.setEnabled(False)
            self.pushButton.setEnabled(False)
            self.pushButton_2.setEnabled(False)
        if mode == 1:
            self.comboBox_username.setEnabled(True)
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
        self.write_to_log(text)

    def update_et_list(self, text):

        # 超过 1000 行，就从前面开始删除
        if self.listWidget_easytier.count() >= 1000:
            self.listWidget_easytier.takeItem(0)

        self.listWidget_easytier.addItem(text)
        self.listWidget_easytier.setCurrentRow(
            self.listWidget_easytier.count() - 1)
        print(text)

    def check_new_version(self):

        self.update_thread = UpdateThread()
        state.threadpool.start(self.update_thread)
        self.update_thread.signals.show_message.connect(
            self.update_message)
        self.update_thread.signals.print_text.connect(
            self.update_list)
        self.update_thread.signals.logout.connect(self.logout)
        # self.update_thread.signals.finished.connect(
        #     lambda: self.update_list("检查更新线程结束"))
        state.new_version_checked = True

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
                self.pushButton_enable_share.clicked.connect(
                    lambda: self.stop_easytier())

                self.easytier_thread = easytier_thread(self, mode="server")
                self.easytier_thread.signals.print_text.connect(
                    self.update_list)
                self.easytier_thread.signals.print_text_et.connect(
                    self.update_et_list)
                self.easytier_thread.signals.finished.connect(
                    self.stop_easytier)
                state.threadpool.start(self.easytier_thread)
                self.menu_2.menuAction().setVisible(True)

            except Exception as e:
                self.update_list(f"启动隧道失败：{e}")
                self.menu_2.menuAction().setVisible(False)

    def stop_easytier(self):
        try:
            et_process = getattr(self, "et_process", None)
            if hasattr(et_process, "terminate"):
                self.et_process.terminate()
                self.et_process = None
                self.update_list("ET: 已停止隧道")

                self.pushButton_enable_share.setText("启用共享")
                self.pushButton_enable_share.clicked.disconnect()
                self.pushButton_enable_share.clicked.connect(
                    lambda: self.start_easytier(True))
                self.pushButton.setEnabled(True)

            if hasattr(self, 'et_connected') and self.et_connected:
                self.remove_et_route()

            self.et_connected = False
            self.menu_2.menuAction().setVisible(False)
            stop_webui_server()
            self.update_list("ET: WebUI服务端已关闭")

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
            self.menu_2.menuAction().setVisible(True)

            self.easytier_thread = easytier_thread(self, mode="client")
            self.easytier_thread.signals.print_text.connect(self.update_list)
            self.easytier_thread.signals.print_text_et.connect(
                self.update_et_list)
            self.easytier_thread.signals.finished.connect(self.stop_easytier)
            state.threadpool.start(self.easytier_thread)
            self.et_connected = True

        except Exception as e:
            self.update_list(f"连接隧道失败：{e}")
            self.menu_2.menuAction().setVisible(False)

    def enable_auto_share(self, checked):
        self.update_config(
            "auto_share", 1 if self.checkBox_auto_share.isChecked() else 0)
        self.update_list("已开启自动共享，启动时将自动启动隧道") if self.checkBox_auto_share.isChecked(
        ) else self.update_list("已关闭自动共享")

        # 如果账号框里时ip，弹出警告
        if self.is_ipv4(self.comboBox_username.currentText()) and checked:
            self.show_message(
                message="当前登录方式为隧道，开启自动共享后自动登录将不会连接隧道！\n\n连接隧道与共享网络是冲突的！", title="警告")

    def share_zip(self):
        if hasattr(self, "processing_zip") and self.processing_zip is True:
            return

        self.zip_progress = 0

        def zip_worker():

            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            temp_dir = os.path.join(tempfile.gettempdir(), "InterKnot")
            os.makedirs(temp_dir, exist_ok=True)
            temp_zip = os.path.join(temp_dir, "InterKnot.zip.temp")
            final_zip = os.path.join(temp_dir, "InterKnot.zip")

            exclude_dirs = {'.git', '.venv', 'SAC'}

            all_files = []
            for root, dirs, files in os.walk(base_dir):

                # 过滤目录
                dirs[:] = [d for d in dirs if d not in exclude_dirs]

                for file in files:
                    all_files.append(os.path.join(root, file))

            total = len(all_files)
            if total == 0:
                print("没有文件可压缩")
                return

            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as z:
                for i, file_path in enumerate(all_files, 1):
                    arcname = os.path.relpath(file_path, base_dir)
                    z.write(file_path, arcname)

                    percent = i / total * 100
                    self.zip_progress = percent
                    bar_len = 30
                    filled_len = int(bar_len * i // total)
                    bar = '█' * filled_len + '-' * (bar_len - filled_len)
                    print(
                        f"\r压缩进度: |{bar}| {percent:.1f}% ({i}/{total})", end='')

            # 原子替换
            os.replace(temp_zip, final_zip)

            self.update_list(f"\n成功创建分享压缩包: {final_zip}")
            self.processing_zip = False

        t = threading.Thread(target=zip_worker, daemon=True)
        self.processing_zip = True
        t.start()


class login_Retry_Thread(QRunnable):
    def __init__(self, times):
        super().__init__()
        self.signals = WorkerSignals()
        self.times = times
    def run(self):

        # debugpy.breakpoint()
        self.signals.enable_buttoms.emit(0)
        first_run = True

        while self.times > 0 and state.stop_retry_thread == False:

            time.sleep(3)

            if state.connected == True:
                state.retry_thread_started = False
                self.signals.enable_buttoms.emit(1)
                self.signals.finished.emit()
                return

            # 上一次登录还未结束时，继续等待。
            if getattr(state, 'login_in_progress', False):
                continue

            if first_run:
                first_run = False
                self.signals.thread_login.emit()
                continue

            self.signals.print_text.emit(f"登录失败,还剩{self.times}次尝试")
            self.times -= 1
            self.signals.thread_login.emit()

        if state.connected == False:
            state.retry_thread_started = False
            message = "自动登录失败，已达到最大重试次数！" if state.stop_retry_thread == False else "自动登录已取消！"
            self.signals.print_text.emit(message)

        self.signals.enable_buttoms.emit(1)
        self.signals.finished.emit()


if __name__ == "__main__":
    try:
        os.makedirs(state.config_dir, exist_ok=True)
        # 防止重复运行
        lock_file = os.path.expanduser("~/.InterKnot.lock")
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
        trace = traceback.format_exc()
        crash_log = os.path.join(state.config_dir, "startup_crash.log")

        try:
            with open(crash_log, "w", encoding="utf-8") as f:
                f.write("[InterKnot Startup Crash]\n")
                f.write(f"Message: {e}\n\n")
                f.write(trace)
        except Exception:
            crash_log = "写入失败"

        detail = (
            f"程序启动时遇到严重错误\n\n"
            f"详细堆栈:\n{trace}\n"
            f"崩溃日志: {crash_log}"
        )
        user32.MessageBoxW(None, detail, "Warning!", 0x30)
        print(detail)
        sys.exit()

# # 编译指令
# nuitka `
# --standalone `
# --lto=yes `
# --clang `
# --msvc=latest `
# --windows-uac-admin `
# --windows-console-mode=disable `
# --enable-plugin=pyqt5,upx `
# --upx-binary="F:\Programs\upx\upx.exe" `
# --include-data-dir=ddddocr=ddddocr `
# --include-data-dir=jre=jre `
# --include-data-dir=easytier=easytier `
# --include-data-file=login.jar=login.jar `
# --include-package=modules `
# --nofollow-import-to=unittest `
# --nofollow-import-to=debugpy `
# --nofollow-import-to=pytest `
# --nofollow-import-to=pydoc `
# --nofollow-import-to=tkinter `
# --nofollow-import-to=PyQt5.QtWebEngine `
# --nofollow-import-to=PyQt5.QtNetwork `
# --nofollow-import-to=PyQt5.QtQml `
# --nofollow-import-to=PyQt5.QtQuick `
# --noinclude-qt-translations `
# --noinclude-setuptools-mode=nofollow `
# --python-flag=no_docstrings,static_hashes `
# --output-dir=SAC `
# --output-filename=绳网认证.exe `
# --windows-icon-from-ico=yish.ico `
# --remove-output `
# --assume-yes-for-downloads `
# main.py