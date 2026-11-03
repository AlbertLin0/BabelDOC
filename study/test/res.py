"""生成 3 对 RSA 2048 测试密钥，输出为可直接放入 .env 的格式"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEY_SIZE = 2048  # 必须 2048，匹配 _MAX_ENCRYPT_CHUNK = 245

for name in ("RSA", "RSA_SAP", "RSA_YX"):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=KEY_SIZE)

    private_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    print(f'{name}_DECRYPT_PRIVATE_KEY={base64.b64encode(private_der).decode()}')
    print(f'{name}_ENCRYPT_PUBLIC_KEY={base64.b64encode(public_der).decode()}')
    print()

