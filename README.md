<div align="center">

# InterKnot_Auth (绳网认证)

[![GitHub release](https://img.shields.io/github/v/release/Yish1/InterKnot_Auth?label=latest%20release)](https://github.com/Yish1/InterKnot/releases)
[![GitHub all releases](https://img.shields.io/github/downloads/Yish1/InterKnot_Auth/total?label=total%20downloads)](https://github.com/Yish1/InterKnot_Auth/releases)
[![GitHub repo size](https://img.shields.io/github/repo-size/Yish1/InterKnot_Auth)](https://github.com/Yish1/InterKnot_Auth)

</div>

**中文** | [English](README_EN.md)

> [!WARNING]
> 为了保证项目安全，请勿在大型公共平台广泛传播，建议低调使用。

## 项目介绍

InterKnot_Auth 是一个面向校园网 ESurfing 认证场景的 Windows 桌面客户端。

当前版本核心能力：

- 学生/教师账号：开袋即食。
- 指定登录 IP：适合多拨/异地临时联网；学生模式下指定ip会心跳失败(可忽略)。
- 一键多拨：根据配置批量登录，在路由器上配置多拨可实现网速翻倍。
- 看门狗：实时监测网卡状态，有ip且所有检测点均不可达时，自动重连。
- 网络共享：基于EasyTier实现，可将本机网络不限量共享给其他设备。
- 隧道连接：基于EasyTier实现，可连接至开启了共享网络的设备。
- WebUI：http://localhost:50000 本机访问为隧道数据大屏，非本机访问为绳网下载页面。
- 密码保存：使用机器码绑定方式进行加密保存，密码不会上传至服务器。
- 自动登录：支持开机自启，自动登录。

## 下载

- 最新版本下载页：
	https://github.com/Yish1/InterKnot_Auth/releases/latest

- 全部版本下载页：
	https://github.com/Yish1/InterKnot_Auth/releases
    
    [![GitHub all releases](https://img.shields.io/github/downloads/Yish1/InterKnot_Auth/total?label=total%20downloads)](https://github.com/Yish1/InterKnot_Auth/releases)

    [![GitHub release downloads](https://img.shields.io/github/downloads/Yish1/InterKnot_Auth/latest/total?label=latest%20release%20downloads)](https://github.com/Yish1/InterKnot_Auth/releases)


### 使用说明

1. 从 Releases 页面下载最新压缩包安装，如遇杀毒软件查杀，请信任并还原(含提权代码以实现开机自启和隧道)。
2. 解压后以管理员权限运行主程序。
3. 首次运行输入账号密码，按需开启“记住密码 / 自动登录 / 看门狗”。
4. 登录成功后，程序可最小化到托盘后台运行。

## 源码编译

1. 准备 Python 3.10+（建议使用虚拟环境）。
2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 运行：

```bash
python main.py
```


### 打包方式（Nuitka）

当前项目使用 Nuitka 在 Windows 下打包，示例命令如下：

```powershell
nuitka --standalone --lto=yes --clang --msvc=latest --windows-console-mode=disable --windows-uac-admin --enable-plugin=pyqt5,upx,anti-bloat --upx-binary="F:/Programs/upx/upx.exe(替换成本机的upx地址)" --include-data-dir=ddddocr=ddddocr --include-data-dir=jre=jre --include-data-dir=easytier=easytier --include-data-file=login.jar=login.jar --include-package=modules --nofollow-import-to=unittest --nofollow-import-to=debugpy --nofollow-import-to=pytest --nofollow-import-to=pydoc --nofollow-import-to=tkinter --nofollow-import-to=PyQt5.QtWebEngine --nofollow-import-to=PyQt5.QtNetwork --nofollow-import-to=PyQt5.QtQml --nofollow-import-to=PyQt5.QtQuick --noinclude-qt-translations --noinclude-setuptools-mode=nofollow --python-flag=no_docstrings,static_hashes --output-dir=SAC --output-filename=绳网认证.exe --windows-icon-from-ico=yish.ico --remove-output --assume-yes-for-downloads main.py
```

打包后检查项：

- 确认输出目录中包含 ddddocr、jre、easytier、login.jar。
- 启用 UPX 后出现 Pyqt5 插件异常，需手动将仓库的 Pyqt5 文件夹替换进去
- 在纯净 Windows 环境做一次登录测试（学生/教师/隧道）。

## 致谢

- 登录参数处理参考了 Pandaft 的 ESurfingPy-CLI：
	https://github.com/Pandaft/ESurfingPy-CLI
- 学生端登录方式使用了 Rsplwe 的 ESurfingDialer：
	https://github.com/Rsplwe/ESurfingDialer


## 界面截图

### 主界面
![main](res/img/main.webp)

### 登录参数配置
![loginconfig](res/img/loginconfig.webp)

### 多拨
![mulitlogin](res/img/mulitlogin.webp)

### 隧道配置
![easytier](res/img/easytier.webp)

### 隧道连接
![etconnect](res/img/etconnect.webp)


### WebUI
![share](res/img/share.webp)


