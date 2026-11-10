from babeldoc.file_system.opentext import file_upload, file_download

test_arc_id = "Z1"
test_doc_id = "aaaio21h4j2wubt3j6oyhvvmduauq"
test_file_path = "./test.pdf"
async def main():
    res = await file_download(test_arc_id, test_doc_id, test_file_path)
    print(res)

async def test_file_upload():
    res = await file_upload(test_file_path, test_arc_id)
    print(res)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_file_upload())
