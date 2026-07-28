import base64
import hashlib

from Crypto.Cipher import AES


content = """
xxxxxxxxxx
xxxxxxxxxx
xxxxxxxxxx
""".lstrip("\n")    # 去掉代码里三引号后的第一个换行

password = "ReTURNT0G2US"

def derive_key(password: str) -> bytes:
    return hashlib.sha256(password.encode("utf-8")).digest()


def encrypt_text(text: str, password: str) -> str:
    key = derive_key(password)
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(text.encode("utf-8"))
    payload = cipher.nonce + tag + ciphertext
    return base64.b64encode(payload).decode("utf-8")


encrypted = encrypt_text(content, password)
print("加密后的内容：{}".format(encrypted))