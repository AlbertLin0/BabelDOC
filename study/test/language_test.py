import httpx 
from babeldoc.utils.rsa import rsa_decrypt, _rsa_encrpyt_test_private_key
from babeldoc.schemas.api.po import ZDataInput



async def test_language_endpoint(lang: str):
    async with httpx.AsyncClient() as client:
        text = """
        1. **英语**: Forward to General Affairs Department Test Account 10 for entertainment expense reimbursement.
        2. **法语**: Transférer au compte test 10 du service des affaires générales pour le remboursement des frais de réception professionnelle.
        3. **德语**: An Testkonto 10 der Allgemeinen Abteilung zur Erstattung von Bewirtungskosten weiterleiten.
        4. **西班牙语**: Remitir a la cuenta de prueba 10 del Departamento de Asuntos Generales para el reembolso de gastos de recepción empresarial.
        5. **俄语**: Передать на тестовый счет 10 отдела общих дел для возмещения расходов на деловые приемы.
        6. **泰语**: ส่งต่อไปยังบัญชีทดสอบหมายเลข 10 ของแผนกงานทั่วไป เพื่อขอเบิกค่าใช้จ่ายรับรองธุรกิจ
        7. **土耳其语**: İş ağırlama giderlerinin geri ödemesi için Genel İşler Departmanı Test Hesabı 10'a iletin.
        8. **波兰语**: Przekazać na konto testowe 10 działu spraw ogólnych w celu zwrotu kosztów przyjęć służbowych.
        9. **中文**: 转综合部测试账号 10 报业务招待费
        """

        ZDATA = ZDataInput( # type: ignore
            JOBID="FI1297",
            TARGET_LANG=lang,
            TEXT=text
        )
        body = {
            "IS_INPUT":
            {
                "SYSID":"JWQT",
                "IFYWID":"FI1299",
                "BSKEY":"5254008E97F81FE1B8CB69BB46AC825B",
                "SAPKEY":"5254008E97F81FE1B8CB69BB46AC825B",
                "ZFILED1":"QTQ",
                "ZFILED2":"1",
                "ZFILED5":"JWQT",
                "ZDATA":ZDATA.model_dump_json()
                }
            }

        
        response = await client.post(
            json=body,
            url="http://10.16.6.191:38001/po/translate",
            timeout=30.0
            )
        print(rsa_decrypt(response.json()["ES_OUTPUT"]["ZDATA"], _rsa_encrpyt_test_private_key))

async def main():
    lang = [ 
        "ru"
    ]
    for lang in lang:
        await test_language_endpoint(lang)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

"""
"
1. **İngilizce**: Forward to General Affairs Department Test Account 10 for entertainment expense reimbursement.\n
2. **Fransızca**: Transférer au compte test 10 du service des affaires générales pour le remboursement des frais de réception professionnelle.\n
3. **Almanca**: An Testkonto 10 der Allgemeinen Abteilung zur Erstattung von Bewirtungskosten weiterleiten.\n
4. **İspanyolca**: Remitir a la cuenta de prueba 10 del Departamento de Asuntos Generales para el reembolso de gastos de recepción empresarial.\n
5. **Rusça**: Передать на тестовый счет 10 отдела общих дел для возмещения расходов на деловые приемы.\n
6. **Tayca**: ส่งต่อไปยังบัญชีทดสอบหมายเลข 10 ของแผนกงานทั่วไป เพื่อขอเบิกค่าใช้จ่ายรับรองธุรกิจ\n
7. **Türkçe**: İş ağırlama giderlerinin geri ödemesi için Genel İşler Departmanı Test Hesabı 10'a iletin.\n
8. **Lehçe**: Przekazać na konto testowe 10 działu spraw ogólnych w celu zwrotu kosztów przyjęć służbowych.\n
9. **Çince**: 转综合部测试账号 10 报业务招待费"
"""