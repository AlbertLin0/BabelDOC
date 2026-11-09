import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa



import os 

data = "KmxsM0zt+xe+cKpZ8kvsq/YOX1G84PSC7BxMtBua8vdzKFYuVRFHMgGaCJ823S24DhSbrVzi2D9GfpCPebI3uwxjK5S89z3vPu4MSihtJkKfaRX9iFNky2wXmbnidotrkTcm7s2+DOkB20Gb02G3Vdxf6U588NOY6aeNaxsiNqq2+JWi+K6L+HsWPqRPuV3HQW5lpW6rjGZx4quxAllJEnc/BomRgjnf6xBjlnd8xUWuypcbD6JiviOrakGP+8kIjU51B9w56OK+4UcFXUFG4LzUy+0NRLNGIWf7/zTt6/k7XanSuJeVCfuTMybizDzhoenWQ3L4GyNnup4FXixdhw==123456789eF2TZK8lVzDbShqmuL5vxRJ7iZW2//+H42QegKKsGdZd/HySTU1KTIa1c0kDNdjftDZY/N/IqlGuqjgAEWthXGWRhlcraVmpj/kIHcZNQco2V+TVnEEV1LslkBvymaCPPSh5QBE0FcSN0ER+nS0NYzYdvEn7xgAsKUku5EiZgyHTPlfK9jH3OJAC0g7+5VE9wkJ0M4QewX9/4ZDCYrMaqLMbU/NLzOHU9v7i4AhoVrqqTDDh/dSKVdF+8AtFa/N/hcHoQgOBAOfeW33RtO98eXNPDJXgIHOvh7DP7Xh1pc9bxLHhsUvAW8ZOBjQ0BTsI9cSogOOefths57swxOPkvA==123456789"

public_key = os.environ["RSA_SAP_ENCRYPT_PUBLIC_KEY"]

private_key = os.environ["RSA_SAP_DECRYPT_PRIVATE_KEY"]

from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

OPERATES = "123456789"

# 所有可能的密钥组合
KEY_CONFIGS = {
    "JWQT（前台）": {
        "private": os.environ.get("RSA_DECRYPT_PRIVATE_KEY", ""),
    },
    "JWYX（影像）": {
        "private": os.environ.get("RSA_YX_DECRYPT_PRIVATE_KEY", ""),
    },
    "JWS4（报账/SAP）": {
        "private": os.environ.get("RSA_SAP_DECRYPT_PRIVATE_KEY", ""),
    },
}

# 两种常见 padding 模式
PADDINGS = {
    "PKCS1v15": padding.PKCS1v15(),
    "OAEP-SHA256": padding.OAEP(
        mgf=padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None,
    ),
}


def load_private_key(priv_b64: str):
    """从 Base64 DER 字符串加载私钥"""
    cleaned = "".join(priv_b64.split())
    return serialization.load_der_private_key(
        base64.b64decode(cleaned), password=None
    )


def try_decrypt(ciphertext: str, private_key_obj, pad) -> bytes | None:
    """尝试解密，成功返回明文字节，失败返回 None"""
    cleaned = ciphertext.replace("\\", "").replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
    blocks = [b for b in cleaned.split(OPERATES) if b]
    parts = []
    for block in blocks:
        raw = base64.b64decode(block)
        decrypted = private_key_obj.decrypt(raw, pad)
        parts.append(decrypted)
    return b"".join(parts)


def looks_like_text(b: bytes) -> bool:
    """检查字节是否像可读文本（含中文）"""
    for enc in ["utf-8", "gbk", "gb18030"]:
        try:
            s = b.decode(enc)
            # 至少包含一些可打印字符
            printable = sum(1 for c in s if c.isprintable() or c in "\n\r\t")
            if printable > len(s) * 0.3:
                return True
        except Exception:
            continue
    return False


# 预处理密文
cleaned = data.replace("\\", "").replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
blocks = [b for b in cleaned.split(OPERATES) if b]
print(f"密文共 {len(blocks)} 个块\n")

# 遍历所有组合
found = False
for sys_name, keys in KEY_CONFIGS.items():
    if not keys["private"]:
        continue
    try:
        priv_key = load_private_key(keys["private"])
    except Exception as e:
        print(f"[{sys_name}] 私钥加载失败: {e}")
        continue

    for pad_name, pad in PADDINGS.items():
        try:
            result = try_decrypt(data, priv_key, pad)
            hex_preview = result[:48].hex(" ")
            if looks_like_text(result):
                print(f"✅ 成功！系统={sys_name}, Padding={pad_name}")
                for enc in ["utf-8", "gbk", "gb18030"]:
                    try:
                        print(f"解码({enc}): {result.decode(enc)}")
                        break
                    except Exception:
                        continue
                found = True
            else:
                print(f"❌ {sys_name} + {pad_name}: 随机字节 | {len(result)}B | hex: {hex_preview}...")
        except Exception as e:
            print(f"❌ {sys_name} + {pad_name}: 解密异常 - {e}")

if not found:
    print("\n⚠️  所有组合均失败。可能原因：")
    print("  1. 数据是用不在环境变量中的密钥加密的")
    print("  2. OPERATES 分隔符与 Java 端不一致")
    print("  3. Java 端使用了其他 padding 变体（如 OAEP-SHA1）")