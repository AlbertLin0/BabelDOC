import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# 必须是 2048 位，才能匹配 _MAX_ENCRYPT_CHUNK = 245
private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

private_der = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.TraditionalOpenSSL,   # PKCS#1
    encryption_algorithm=serialization.NoEncryption(),
)
public_der = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,  # X.509
)

print("RSA_DECRYPT_PRIVATE_KEY=" + base64.b64encode(private_der).decode())
print("RSA_ENCRYPT_PUBLIC_KEY=" + base64.b64encode(public_der).decode())