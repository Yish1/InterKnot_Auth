import subprocess
import hashlib
from Crypto.Cipher import AES
import base64
import os
import winreg
import ctypes
from ctypes import wintypes
from modules import global_state, Config_Manager

state = global_state()


pwd_path = os.path.join(state.config_dir, "Secret.dat")

class DatManager:
    @staticmethod
    def read_file():
        return Config_Manager.read_config_file(pwd_path)

    @staticmethod
    def get_password(username):
        config = DatManager.read_file()
        if username in config:
            return config[username]
        return None

    @staticmethod
    def set_password(username, password):
        Config_Manager.update_entry(username, password, pwd_path)

    @staticmethod
    def delete_password(username):
        Config_Manager.update_entry(username, None, pwd_path)

    @staticmethod
    def list_usernames():
        config = DatManager.read_file()
        return [username for username in config.keys()]


class SecurityManager:
    @staticmethod
    def get_machine_guid():
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            )

            guid, _ = winreg.QueryValueEx(key, "MachineGuid")

        except Exception as e:
            raise RuntimeError(f"Failed to read MachineGuid: {e}")

        guid = guid.replace("-", "")

        return guid

    @staticmethod
    def get_encryption_key():
        guid = SecurityManager.get_machine_guid()

        # 加盐
        salt = "InterKnot2026"

        key = hashlib.sha256((guid + salt).encode()).digest()
        # print("Encryption key:", key.hex())

        return key

    @staticmethod
    def encrypt(data: str, key: bytes) -> str:
        cipher = AES.new(key, AES.MODE_GCM)

        ciphertext, tag = cipher.encrypt_and_digest(data.encode())

        result = cipher.nonce + tag + ciphertext

        return base64.b64encode(result).decode()

    @staticmethod
    def decrypt(token: str, key: bytes) -> str:
        try:
            raw = base64.b64decode(token)

            nonce = raw[:16]
            tag = raw[16:32]
            ciphertext = raw[32:]

            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)

            data = cipher.decrypt_and_verify(ciphertext, tag)

            return data.decode()
        
        except Exception as e:
            print(f"Failed to decrypt token: {e}")
            return ""

    @staticmethod
    def save_password(username: str, password: str):
        key = SecurityManager.get_encryption_key()

        encrypted_password = SecurityManager.encrypt(password, key)

        DatManager.set_password(username, encrypted_password)
        print(f"Password for {username} saved securely.")

    @staticmethod
    def get_password(username: str) -> str:
        key = SecurityManager.get_encryption_key()

        encrypted_password = DatManager.get_password(username)

        if encrypted_password is None:
            return None

        try:
            decrypted_password = SecurityManager.decrypt(
                encrypted_password, key)
        except Exception as e:
            print(f"Error decrypting password for {username}: {e}")
            DatManager.delete_password(username)
            return ""

        return decrypted_password

    @staticmethod
    def delete_password(username: str):
        try:
            DatManager.delete_password(username)
            print(f"Password for {username} deleted.")
        except:
            pass
