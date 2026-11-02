"""RSA 加解密工具模块

密钥来源于项目根目录的《境外前台、翻译服务密钥.txt》
- 私钥为 PKCS#1 格式，公钥为 SubjectPublicKeyInfo 格式
- 使用 OAEP + SHA256 padding（需与对方确认，Java 默认是 PKCS1v15）
"""

import os
import base64
import logging
import json
from typing import cast

from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPrivateKey,
    RSAPublicKey,
)

logger = logging.getLogger(__name__)


def _clean_b64(value: str) -> str:
    """去掉 Base64 字符串中的所有换行和空白符"""
    return "".join(value.split())


def _load_keys() -> tuple[RSAPrivateKey, RSAPublicKey]:
    """从环境变量加载密钥

    - RSA_DECRYPT_PRIVATE_KEY: 我们的私钥，解对方用 RSA_DECRYPT_PUBLIC_KEY 加密的入站
    - RSA_ENCRYPT_PUBLIC_KEY: 对方的公钥，加密后对方用 RSA_ENCRYPT_PRIVATE_KEY 解密
    """
    # 解密入站：对方用 RSA_DECRYPT_PUBLIC_KEY 加密 → 我们用 RSA_DECRYPT_PRIVATE_KEY 解密
    priv_b64 = _clean_b64(os.environ["RSA_DECRYPT_PRIVATE_KEY"])
    private_key = cast(
        RSAPrivateKey,
        serialization.load_der_private_key(
            base64.b64decode(priv_b64), password=None
        ),
    )

    # 加密出站：我们用 RSA_ENCRYPT_PUBLIC_KEY 加密 → 对方用 RSA_ENCRYPT_PRIVATE_KEY 解密
    pub_b64 = _clean_b64(os.environ["RSA_ENCRYPT_PUBLIC_KEY"])
    public_key = cast(
        RSAPublicKey,
        serialization.load_der_public_key(
            base64.b64decode(pub_b64)
        ),
    )

    logger.info(
        f"RSA 密钥加载成功: decrypt_private={private_key.key_size}bit, "
        f"encrypt_public={public_key.key_size}bit"
    )
    return private_key, public_key


# 模块加载时初始化（单例）
_private_key: RSAPrivateKey
_public_key: RSAPublicKey

_private_key, _public_key = _load_keys()

# ========= Padding 配置 =========
# TODO: 如果加解密不通，切换为 PKCS1v15（Java 默认）
_PADDING = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)

# RSA-2048 分段参数
_KEY_SIZE_BYTES = _private_key.key_size // 8  # 256
_MAX_ENCRYPT_CHUNK = _KEY_SIZE_BYTES - 64 - 2  # OAEP SHA256 最大加密块 = 190

def rsa_decrypt(ciphertext_b64: str) -> str:
    """RSA 分段解密（解密入站请求：前台用公钥加密→我们用私钥解密）

    Args:
        ciphertext_b64: Base64 编码的密文

    Returns:
        解密后的 UTF-8 明文字符串
    """
    ciphertext = base64.b64decode(ciphertext_b64)
    plaintext = bytearray()

    for i in range(0, len(ciphertext), _KEY_SIZE_BYTES):
        chunk = ciphertext[i:i + _KEY_SIZE_BYTES]
        decrypted = _private_key.decrypt(chunk, _PADDING)
        plaintext.extend(decrypted)

    return plaintext.decode("utf-8")

def rsa_encrypt(plaintext: str) -> str:
    """RSA 分段加密（加密出站响应：我们用公钥加密→前台用私钥解密）

    Args:
        plaintext: 要加密的明文字符串

    Returns:
        Base64 编码的密文字符串
    """
    plaintext_bytes = plaintext.encode("utf-8")
    ciphertext = bytearray()

    for i in range(0, len(plaintext_bytes), _MAX_ENCRYPT_CHUNK):
        chunk = plaintext_bytes[i:i + _MAX_ENCRYPT_CHUNK]
        encrypted = _public_key.encrypt(chunk, _PADDING)
        ciphertext.extend(encrypted)

    return base64.b64encode(bytes(ciphertext)).decode("utf-8")

def encrypt_data(obj: any) -> str:
    """把响应对象序列化为 JSON 后 RSA 加密返回"""
    json_str = json.dumps(jsonable_encoder(obj), ensure_ascii=False)
    encrypted = rsa_encrypt(json_str)
    return encrypted

def decrypt_data(encrypted: str) -> any:
    """把 RSA 解密后的 JSON 字符串反序列化为对象"""
    decrypted = rsa_decrypt(encrypted)
    return json.loads(decrypted)