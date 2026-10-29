import httpx

async def translate_text():
    async with httpx.AsyncClient(timeout=3600) as client:
        payload = {
            "IS_INPUT": {
                "SYSID": "123456",
                "IFYWID": "FI1301",
                "BSKEY": "123456",
                "SAPKEY": "123456",
                "ZORG": "123456",
                "ZFILED5": "123456",
                "ZDATA": {
                    "JOBID": "123456",
                    "TEXT": "翻译后的文本",
                },
            }
        }
        response = await client.post(
            "http://10.16.6.191:38001/po/translate",
            json=payload,
        )

        if response.status_code == 200:
            print(response.json())
        else:
            print(f"状态码: {response.status_code}")
            print(f"响应头 Content-Type: {response.headers.get('content-type')}")
            print(f"响应体: {response.text}")
            raise Exception(f"翻译失败: {response.status_code}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(translate_text())