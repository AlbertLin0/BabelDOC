
---

## 调度队列接口文档

**Base Path**: `/schedule`  
**Content-Type**: `application/json`

所有的接口(除了"get_pending"接口)都需要传递 `task_id` 参数。`position` 参数在移动到指定位置接口中必填。
---

### 1. 上移任务

将等待队列中的任务向前移动一位，已在队首则位置不变。

- **URL**: `POST /schedule/move_up`
- **Query 参数**:

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| task_id | string | ✅ | 任务 ID |

- **响应**: `"OK"`

---

### 2. 下移任务

将等待队列中的任务向后移动一位，已在队尾则位置不变。

- **URL**: `POST /schedule/move_down`
- **Query 参数**:

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| task_id | string | ✅ | 任务 ID |

- **响应**: `"OK"`

---

### 3. 移除任务

从等待队列中彻底删除任务（不会进入执行流程）。

- **URL**: `POST /schedule/remove`
- **Query 参数**:

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| task_id | string | ✅ | 任务 ID |

- **响应**: `"OK"`

---

### 4. 移动到指定位置

将任务移动到等待队列的指定位置（0 = 队首）。

- **URL**: `POST /schedule/move_to_position`
- **Query 参数**:

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| task_id | string | ✅ | 任务 ID |
| position | int | ✅ | 目标位置（0 为队首，超出范围自动 clamp） |

- **响应**: `"OK"`

---

### 5. 取消任务 <<< 正在开发中，现只支持取消等待中的任务，不支持取消执行中的任务。

取消指定任务。等待中的任务直接移除并标记为 FAILED；执行中的任务设置 cancelled 标志并尝试中断 asyncio 任务。

- **URL**: `POST /schedule/cancel`
- **Query 参数**:

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| task_id | string | ✅ | 任务 ID |

- **响应**: `"OK"`

---

### 6. 获取等待队列

返回当前所有排队中的任务列表（按排队顺序）。

- **URL**: `POST /schedule/get_pending`
- **Query 参数**: 无

- **响应示例**:
```json
"message": "OK",
"data":
[
  {
    "position": 0,
    "task_id": "3f5a8b2c-...",
    "task_name": "附件翻译",
    "created_at": "2023-11-01 12:0:00",
    "file_name": "example.pdf",
    "predicted_time": 20,
    "status": "PENDING"
  },
  {
    "position": 1,
    "task_id": "7d9e1a4f-...",
    "task_name": "截图翻译",
    "created_at": "2023-11-01 12:00:00",
    "file_name": "截图",
    "predicted_time": 20,
    "status": "PENDING"
  }
]
```

- **响应字段说明**:

| 字段 | 类型 | 说明 |
|---|---|---|
| position | int | 排队位置（0 = 队首） |
| task_id | string | 任务唯一 ID |
| task_name | string | `"附件翻译"` 或 `"截图翻译"` |
| created_at | float | 任务创建时间戳（秒） |
| file_name | string | 文件名，截图任务固定显示 `"截图"` |
| predicted_time | int | 预计处理时长（秒），当前固定返回 20 |
| status | string | 固定为 `"PENDING"`（等待中） |

---
### 7. 获取正在翻译队列
- **URL**: `POST /schedule/get_processing`
- **Query 参数**: 无

- **响应字段说明**:
| status | string | 固定为 `"PROCESSING"`（处理中） |
---
### 8. 获取已完成队列
- **URL**: `POST /schedule/get_completed`
- **Query 参数**: 无

- **响应字段说明**:
| status | string | 固定为 `"COMPLETED"`（已完成）｜`"FAILED"`（失败）｜`"CANCELLED"`（已取消） |
---

### 位置取值规则

| 接口 | 有效范围 | 边界行为 |
|---|---|---|
| `move_to_position` | 0 ≤ position ≤ len-1 | 超范围自动 clamp |
| `move_up` | — | position ≤ 0 时不变 |
| `move_down` | — | position ≥ len-1 时不变 |

---

