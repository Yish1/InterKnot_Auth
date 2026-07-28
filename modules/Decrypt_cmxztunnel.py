import base64
import hashlib
from pathlib import Path
from Crypto.Cipher import AES
from PyQt5.QtWidgets import QMessageBox
from PyQt5 import QtGui



def show_message(message, title):
    msgBox = QMessageBox()
    msgBox.setWindowTitle(title)
    msgBox.setWindowIcon(QtGui.QIcon(':/icon/yish.ico'))
    if message is None:
        message = "未知错误"
    message = str(message)
    msgBox.setText(message)
    msgBox.exec_()

def decrypt_cmxztunnel(content, password):
    try:
        raw_data = base64.b64decode(content)
    except Exception as e:
        show_message(f"解码 cmxztunnel 内容失败: {e}", "错误")
        return None

    password_key = hashlib.sha256(password.encode("utf-8")).digest()
    candidates = [raw_data]

    try:
        decoded = base64.b64decode(raw_data, validate=True)
        if decoded:
            candidates.insert(0, decoded)
    except Exception:
        pass


    for candidate in candidates:
        if len(candidate) <= 32:
            continue

        try:
            nonce = candidate[:16]
            tag = candidate[16:32]
            ciphertext = candidate[32:]
            cipher = AES.new(password_key, AES.MODE_GCM, nonce=nonce)
            plain_text = cipher.decrypt_and_verify(ciphertext, tag).decode("utf-8")
            if "peer" in plain_text:
                return plain_text
        except Exception:
            continue

    return None
