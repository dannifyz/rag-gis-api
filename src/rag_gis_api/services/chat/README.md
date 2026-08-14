# chat

Pipeline ตอบคำถาม: ค้น chunk ที่เกี่ยวข้องจาก vector store แล้วส่งเข้า LLM เป็น context

| ไฟล์ | ทำอะไร |
| --- | --- |
| `build_messages.py` | system prompt + ประกอบ chunk เป็น context block ที่ติดชื่อไฟล์กับเลขหน้าไว้ทุกก้อน |
| `list_sources.py` | ยุบ chunk ที่มาจากไฟล์เดียวกันให้เหลือ entry เดียวพร้อมเลขหน้า ไว้ส่งกลับให้ client |
| `../chat_service.py` | `ask()` กับ `ask_stream()` — เดิน pipeline และปล่อย event ระหว่างทาง |
| `../../controllers/chat_controller.py` | endpoint ทั้งสองตัว |

## Endpoint

| Endpoint | ทำอะไร |
| --- | --- |
| `GET /api/chat?question=<คำถาม>` | รอจนจบแล้วคืน JSON ก้อนเดียว |
| `GET /api/chat/stream?question=<คำถาม>` | คำตอบเดียวกัน แต่ทยอยส่งกลับด้วย SSE ระหว่างที่ทำงาน |

ทั้งสองใช้ pipeline เดียวกัน คือค้น `RETRIEVE_LIMIT` chunk แรกที่ใกล้เคียงคำถามที่สุด
(ตั้งค่าที่ `chat_service.py`) แล้วส่งเข้า LLM เป็น context — ถ้า context ไม่มีคำตอบ system prompt
สั่งให้ตอบว่าไม่พบข้อมูล ไม่ให้เดา ผลข้างเคียงคือคำถามคุยเล่นทั่วไปจะโดนตอบว่าไม่พบข้อมูลด้วย

## SSE: `GET /api/chat/stream`

`data` เป็น JSON ทุก event เพราะ SSE แบ่ง event ด้วยบรรทัด ถ้าส่ง token ดิบที่มี `\n` อยู่ข้างใน
stream จะขาดกลางคัน — JSON escape ให้เอง

| event | data | ส่งตอนไหน |
| --- | --- | --- |
| `status` | `{"stage": "retrieving", "message": "..."}` | เริ่มค้นเอกสาร |
| `status` | `{"stage": "retrieved", "message": "...", "count": 5}` | ค้นเสร็จ รู้แล้วว่าเจอกี่ chunk |
| `status` | `{"stage": "generating", "message": "..."}` | ส่ง context เข้า LLM แล้ว กำลังรอ token แรก |
| `token` | `{"text": "..."}` | ทุก chunk ที่ LLM ส่งกลับมา |
| `done` | `{"answer": "...", "sources": [...]}` | จบแล้ว `answer` คือ token ทั้งหมดต่อกัน |
| `error` | `{"message": "..."}` | pipeline พัง — stream จบตรงนี้ |

ตัวอย่างที่ได้กลับมา:

```
event: status
data: {"stage": "retrieving", "message": "กำลังค้นหาเอกสาร..."}

event: status
data: {"stage": "retrieved", "message": "พบเอกสารที่เกี่ยวข้อง 5 รายการ", "count": 5}

event: status
data: {"stage": "generating", "message": "กำลังสร้างคำตอบ..."}

event: token
data: {"text": "ไม่พบข้อมูลเกี่ยวกับขั้นตอนการขออนุญาตก่อสร้าง..."}

event: done
data: {"answer": "ไม่พบข้อมูล...", "sources": [{"source": "ประกาศกระทรวง_Min_Notif/PDF ต้นฉบับ/Min_Notif_031.pdf", "pages": [9]}]}
```

`error` มีไว้เพราะถ้าปล่อยให้ stream ขาดดื้อ ๆ `EventSource` ฝั่ง browser จะ reconnect เองแล้วถามใหม่
ทั้งรอบ เสียทั้ง embedding call และ LLM call ฟรี ๆ

## ทดสอบ

เปิด server ค้างไว้อีก terminal นึงก่อน แล้ว:

```bash
uv run rag-gis-chat "การขออนุญาตก่อสร้างมีขั้นตอนอย่างไร"
```

```
Q: การขออนุญาตก่อสร้างมีขั้นตอนอย่างไร

[  0.1s] กำลังค้นหาเอกสาร...
[  0.7s] พบเอกสารที่เกี่ยวข้อง 5 รายการ
[  0.7s] กำลังสร้างคำตอบ...
ไม่พบข้อมูลเกี่ยวกับขั้นตอนการขออนุญาตก่อสร้างในเอกสารที่ให้มา เอกสารระบุเพียงว่า...

[  5.2s] done
  - ประกาศกระทรวง_Min_Notif/PDF ต้นฉบับ/Min_Notif_031.pdf หน้า 9
  - ประกาศกระทรวง_Min_Notif/PDF ต้นฉบับ/Min_Notif_045.pdf หน้า 8, 9
```

เวลาหน้าบรรทัดคือจุดสำคัญ: มันบอกว่า status ขึ้นตั้งแต่วินาทีแรก ไม่ได้รอจนคำตอบเสร็จค่อยโผล่มาพร้อมกัน

`--url` ไว้ชี้ไป endpoint อื่น เช่นตอนรัน server คนละ port:

```bash
uv run rag-gis-chat "<คำถาม>" --url http://127.0.0.1:8001/api/chat/stream
```

ถ้าจะดู event ดิบ ๆ ใช้ curl ก็ได้ แต่ต้องครบสามอย่างนี้:

```bash
curl.exe -N -G "http://127.0.0.1:8000/api/chat/stream" --data-urlencode "question=การขออนุญาตก่อสร้างมีขั้นตอนอย่างไร"
```

- `curl.exe` ไม่ใช่ `curl` — ใน PowerShell `curl` เป็น alias ของ `Invoke-WebRequest` ซึ่งรอโหลดจนจบก่อนค่อย print
- `-N` ปิด buffer ของ curl เอง ไม่งั้นก็ไม่เห็นว่ามันทยอยมา
- `-G --data-urlencode` ไม่ใช่การต่อ `?question=` ตรง ๆ — curl ไม่ percent-encode ให้ ถ้าใส่ภาษาไทยดิบ ๆ
  ลงใน URL มันจะส่ง byte พวกนั้นในบรรทัดแรกของ HTTP request ซึ่งผิดสเปค uvicorn จะตอบ
  `Invalid HTTP request received.` กลับมาโดยที่ FastAPI ไม่เห็น request เลย (เบราว์เซอร์ไม่เจอปัญหานี้
  เพราะ encode ให้เอง)

## ฝั่ง frontend

```js
const source = new EventSource(
  `http://127.0.0.1:8000/api/chat/stream?question=${encodeURIComponent(question)}`,
);

source.addEventListener("status", (e) => showStatus(JSON.parse(e.data).message));
source.addEventListener("token", (e) => appendAnswer(JSON.parse(e.data).text));

source.addEventListener("done", (e) => {
  showSources(JSON.parse(e.data).sources);
  source.close(); // ต้องปิดเอง ไม่งั้น EventSource จะ reconnect แล้วถามใหม่ทั้งรอบ
});

source.addEventListener("error", (e) => {
  console.error(JSON.parse(e.data).message);
  source.close();
});
```

## ยังไม่ได้ทำ

state อยู่ในหน่วยความจำของ request นั้นอย่างเดียว ถ้า user กด refresh ระหว่าง stream คำตอบที่ขึ้นไป
แล้วจะหายและต้องถามใหม่ ถ้าอยากให้ refresh แล้วต่อได้ ต้องเก็บ job + partial answer ไว้ฝั่ง server
แล้วเปลี่ยนเป็น `POST /chat/jobs` + `GET /chat/jobs/{id}/stream`

event `error` ตอนนี้ส่ง exception message ดิบกลับไป สะดวกตอน dev แต่ก่อน deploy จริงควรเปลี่ยนเป็น
log ฝั่ง server แล้วส่งข้อความกลาง ๆ กลับไปแทน
