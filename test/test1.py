import httpx

async def translate_pdf(pdf_path: str):
    async with httpx.AsyncClient(timeout=3600) as client:
        with open(pdf_path, "rb") as f:
            files = {"file": ("doc.pdf", f, "application/pdf")}
            response = await client.post(
                "http://localhost:8086/translate",
                files=files,
            )

        if response.status_code == 200:
            with open("translated_result.zip", "wb") as f:
                f.write(response.content)
            return response.headers
        else:
            raise Exception(f"翻译失败: {response.status_code}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(translate_pdf("../examples/ci/test4.pdf"))