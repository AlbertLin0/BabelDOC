from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from babeldoc.schedule.schedule import Schedule
from datetime import datetime

app = APIRouter()

sche = Schedule.get_instance()

@app.post("/schedule/move_up")
def move_up(task_id: str):
    try:
        sche.move_up(task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")
    return JSONResponse(content={"message": "OK"}, status_code=200)


@app.post("/schedule/move_down")
def move_down(task_id: str):
    try:
        sche.move_down(task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")
    return JSONResponse(content={"message": "OK"}, status_code=200)

@app.post("/schedule/remove")
def remove(task_id: str):
    try:
        sche.remove(task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")
    return JSONResponse(content={"message": "OK"}, status_code=200)

@app.post("/schedule/move_to_position")
def move_to_position(task_id: str, position: int):
    try:
        sche.move_to_position(task_id, position)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")
    return JSONResponse(content={"message": "OK"}, status_code=200)

@app.post("/schedule/cancel")
def cancel(task_id: str):
    try:
        sche.cancel(task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")
    return JSONResponse(content={"message": "OK"}, status_code=200)

@app.post("/schedule/get_pending")
def get_pending():  
    tasks = sche.get_pending()

    res = []
    try:
        for index, task in enumerate(tasks):
            item = {
                "position": index, 
                "task_id": task.task_id,
                "task_name": "附件翻译" if task.zdata.FILE_ARCID else "截图翻译",
                "created_at": datetime.fromtimestamp(task.created_at).strftime("%Y-%m-%d %H:%M:%S"), # 转格式为字符串YYYY-MM-DD HH:MM:SS
                "file_name": task.file_name if task.file_name else "截图",
                "predicted_time": 20,
                "status": task.status.value,
            }
            res.append(item)
        return JSONResponse(content={"message": "OK", "data": res}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")

@app.post("/schedule/get_processing")
def get_processing():
    tasks = sche.get_processing()
    res = []
    try:
        for task in tasks:
            item = {
                "task_id": task.task_id,
                "task_name": "附件翻译" if task.zdata.FILE_ARCID else "截图翻译",
                "created_at": datetime.fromtimestamp(task.created_at).strftime("%Y-%m-%d %H:%M:%S"), # 转格式为字符串YYYY-MM-DD HH:MM:SS
                "file_name": task.file_name if task.file_name else "截图",
                "predicted_time": 20,
                "status": task.status.value,
            }
            res.append(item)
        return JSONResponse(content={"message": "OK", "data": res}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")

@app.post("/schedule/get_completed")
def get_completed():
    tasks = sche.get_completed()
    res = []
    try:
        for task in tasks:
            item = {
                "task_id": task.task_id,
                "task_name": "附件翻译" if task.zdata.FILE_ARCID else "截图翻译",
                "created_at": datetime.fromtimestamp(task.created_at).strftime("%Y-%m-%d %H:%M:%S"), # 转格式为字符串YYYY-MM-DD HH:MM:SS
                "file_name": task.file_name if task.file_name else "截图",
                "predicted_time": 20,
                "status": task.status.value,
            }
            res.append(item)
        return JSONResponse(content={"message": "OK", "data": res}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail="排队接口异常")