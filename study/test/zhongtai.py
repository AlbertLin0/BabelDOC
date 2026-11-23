import httpx 

async def main():
    body = {"IS_INPUT":{"SYSID":"FYMX","IFYWID":"FI1297","BSKEY":"5254008E97F81FE1B8CB69BB46AC825B","SAPKEY":"5254008E97F81FE1B8CB69BB46AC825B","ZFILED1":"700","ZFILED5":"FYQ","ZDATA":"hkUZm3n1PBq3voxJBGKvxLJzZLv1GPodfc0hqI0z1iGSJRjBLOvJtvzs4WI8f8L68nLMgIyxkvKK7v8EDxYfQJ5SQlK7mWoPvOs4nSkUf+wqe3bdiAd\/m3yI8Uc3tf8uuDSzFX5Ey+X53+\/g0yrc15s1S8imQ4gB2XeDCRDPhUioD+OPw8EH\/0EQ4m4U\/9h3rF7c8tO51eI95A\/11C9wjZATkuKQL5DOPiC\/j4v8rCtpkJJ6o3+MnuKuL\/Hn0a2zU0lIC5sIqNBS66\/ik+b9djUtB8PBcGx108EEDQy7gCecHE5mUNa9ufiEJrC8QhsceL6PQA7kzcKkTEkS7lgY\/w==123456789dwIO8cbPD3bRVGLJ7DuWKnFnkLJ9mi3aHOXLWrClayBb4vI43hRK\/UK0bu7GTSTv5o3goUt96+MAPoudHuJLG\/mmLTvGuJ\/Q+EgsN+4IA72iWCjvL80XMZLAh24Ts8rxp99FksfIU37JqZJLavpXTQwz4LtQk9QZ4MBa59p3p3v9N\/MZlf+Dv4mpI9W9HNyTqlHFDwsIyiDysz6p+nffXfUmHPGzEfixQWaUvCHoVuXzjQqY0rNQUPcPAyN5A\/q9urJpIyptHWoCJmrEdIkqVPb9UNkY6jODM6Pj+NmWAcvLyFeXeuBvJG1GzTbBU4cvmQlvG73qI2gPfDdnwd8oiw==123456789s0zIQ7zapLJffHS08M20NtzfAX0mUjUWoY4Rb6Ozqxdgz2icuWOsChmHky6\/KlFl+LKCYdlwZvIugHqqxrxCjJNRJ8tifiENXwJ0Zuy7gQzIHYLluRfx\/yX0Qis+UMZ3tQzNHv+8P7mPGlkALX4evQ8oBiTAdVUxL2hV7Be3Pp814f41d+h2Fmo39MgoCCY2TvsX33lQY2gRbG\/6voGriKzX4ubifHQvqqTFyD4NIlSp2ONYDUx66hOJgCtd\/1mTHyUZVNh0Qg+\/OtD8U2i9IA2d4Nmk21zB4bnl8NMxWTFC\/HRGH\/6ATYyg3VMh24uDy8BnGXHYFSVQR\/W+IWGSJA==1234567890vae7G1FxUus0XdutOlIOZJ3uXrtaozDY0NaX6i8fBmBjMl5T85Zj\/rgKiImjdw+TTX+AcecUv3jnOEsxLsAxwr04Wu0GGjDq5lcw\/OSSsQuah9l3ClUJVvocp\/rzo0oqMP31s+XX\/XGnJ7Ct\/mQ8Tzk7hyhUETkFgJJrZMVG2WfEhjve+B+2ItdVEOWPdNA7sI0LSCG3B3LXgsUuRa5Pi4+G6+JqWiGMPry3ziZHAAIYgFkdiy6JkkDBJuMViz15PkERNNs7YZYxoQRxGW\/aCPh2JFW2AHkd2EthPZS3mNp0s+mNwFnh8BLPKaecSbDgbgAyiC9uLAIq6f2YpJLkA=="}}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            url="http://10.16.6.191:38001/po/translate",
            json=body
        )
        response.raise_for_status()
        print(response.status_code)
        try:
            print(response.json())
        except ValueError:
            print(response.text)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())