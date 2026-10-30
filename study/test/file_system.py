from babeldoc.file_system.opentext import file_upload, file_download

test_file_path = "./"
test_arc_id = "Z1"
test_doc_id = "aaaio21h4j2wubt3j6oyhvvmduauq"
async def main():
    res = await file_download(test_arc_id, test_doc_id, test_file_path)
    print(res)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
