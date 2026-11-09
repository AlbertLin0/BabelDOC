"""验证 .env 中 RSA 私钥和公钥是否为一对"""

import os
import base64

from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives import hashes

load_dotenv()

# 三对密钥的 env 变量名
KEY_PAIRS = [
    ("RSA_ENCRYPT_PRIVATE_KEY", "RSA_ENCRYPT_PUBLIC_KEY"),
    ("RSA_SAP_DECRYPT_PRIVATE_KEY", "RSA_SAP_DECRYPT_PUBLIC_KEY"),
    ("RSA_YX_DECRYPT_PRIVATE_KEY", "RSA_SAP_DECRYPT_PUBLIC_KEY"),
]

def load_private_key(env_name: str) -> RSAPrivateKey:
    """从环境变量加载 DER 格式私钥"""
    b64 = "".join(os.environ[env_name].split())
    return serialization.load_der_private_key(base64.b64decode(b64), password=None)

def load_public_key(env_name: str) -> RSAPublicKey:
    """从环境变量加载 DER 格式公钥"""
    b64 = "".join(os.environ[env_name].split())
    return serialization.load_der_public_key(base64.b64decode(b64))

def keys_match(private_key: RSAPrivateKey, public_key: RSAPublicKey) -> bool:
    """
    验证私钥和公钥是否为一对：
    1. 从私钥推导公钥，对比公钥字节
    2. 用公钥加密、私钥解密，往返验证
    """
    # 方法1：从私钥提取公钥，序列化后对比字节
    derived_public = private_key.public_key()
    pub1 = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub2 = derived_public.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if pub1 != pub2:
        return False

    # 方法2：加密 → 解密往返测试（双重保险）
    test_data = b"BabelDOC key pair test - hello!"
    ciphertext = public_key.encrypt(test_data, padding.PKCS1v15())
    plaintext = private_key.decrypt(ciphertext, padding.PKCS1v15())
    return plaintext == test_data

def main():
    all_ok = True

    for priv_name, pub_name in KEY_PAIRS:
        print(f"\n{'=' * 60}")
        print(f"测试密钥对: {priv_name}  ↔  {pub_name}")

        if priv_name not in os.environ:
            print(f"  ⚠️  SKIP: {priv_name} 未在 .env 中设置")
            continue
        if pub_name not in os.environ:
            print(f"  ⚠️  SKIP: {pub_name} 未在 .env 中设置")
            continue

        try:
            private_key = load_private_key(priv_name)
            public_key = load_public_key(pub_name)

            if keys_match(private_key, public_key):
                print(f"  ✅ PASS: 两个 key 是一对，往返加解密验证通过")
            else:
                print(f"  ❌ FAIL: 两个 key 不匹配！")
                all_ok = False

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            all_ok = False

    print(f"\n{'=' * 60}")
    if all_ok:
        print("🎉 所有密钥对验证通过！")
    else:
        print("⚠️  存在不匹配的密钥对，请检查 .env 配置")

if __name__ == "__main__":
    main()