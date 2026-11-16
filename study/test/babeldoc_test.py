from babeldoc.services.translation_service import manager 
from pathlib import Path
async def test_babeldoc():
    task_id = "test_task_id"
    path = Path("./test.pdf")
    if not path.exists():
        print(f"file not exists: {path}")
    res = await manager._run_translation(path, task_id)

    print(res)

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_babeldoc())