# rag-gis-api

## Setup

ต้องมี [uv](https://docs.astral.sh/uv/getting-started/installation/) และ Python >= 3.14

```bash
git clone <repo-url>
cd rag-gis-api

# สร้าง .venv และติดตั้ง dependencies ทั้งหมดจาก uv.lock
uv sync

# ติดตั้ง git hook
uv run pre-commit install
```

สร้างไฟล์ `.env` ที่ root (ไม่ commit ขึ้น repo) ใส่ API key ของ Gemini ไม่งั้นโปรแกรมจะ error ตั้งแต่ import:

```
GOOGLE_API_KEY=<your-key>
ENV=local
```

รัน API:

```bash
uv run rag-gis-api
```

เปิดที่ http://127.0.0.1:8000/api/health

## API

| Endpoint | ทำอะไร |
| --- | --- |
| `GET /api/health` | เช็คว่า server ขึ้นแล้ว |
| `GET /api/chat?question=<คำถาม>` | ค้น chunk ที่เกี่ยวข้องจาก vector store แล้วให้ LLM ตอบ รอจนจบแล้วคืน JSON ก้อนเดียว |
| `GET /api/chat/stream?question=<คำถาม>` | คำตอบเดียวกัน แต่ทยอยส่งกลับด้วย SSE ระหว่างที่ทำงาน |

ทั้งสอง endpoint ใช้ pipeline เดียวกัน คือค้น `RETRIEVE_LIMIT` chunk แรกที่ใกล้เคียงคำถามที่สุด
(ตั้งค่าที่ `services/chat_service.py`) แล้วส่งเข้า LLM เป็น context — ถ้า context ไม่มีคำตอบ
system prompt สั่งให้ตอบว่าไม่พบข้อมูล ไม่ให้เดา

### SSE: `GET /api/chat/stream`

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

ทดสอบจาก terminal ด้วย `rag-gis-chat` — เปิด server ค้างไว้อีก terminal นึงก่อน:

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

ฝั่ง frontend ใช้ `EventSource` ได้เลย:

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

ข้อจำกัดที่ต้องรู้: state อยู่ในหน่วยความจำของ request นั้นอย่างเดียว ถ้า user กด refresh
ระหว่าง stream คำตอบที่ขึ้นไปแล้วจะหายและต้องถามใหม่ ถ้าอยากให้ refresh แล้วต่อได้
ต้องเก็บ job + partial answer ไว้ฝั่ง server แล้วเปลี่ยนเป็น `POST /chat/jobs` +
`GET /chat/jobs/{id}/stream` ซึ่งยังไม่ได้ทำในรอบนี้

## Git hook (format ก่อน commit)

ตั้งค่าไว้ที่ `.pre-commit-config.yaml` ใช้ `ruff-format` ทุกครั้งที่ `git commit`

ต้องรันคำสั่งนี้ก่อน hook ถึงจะทำงาน:

```bash
uv run pre-commit install
```

คำสั่งนี้จะไปสร้างไฟล์ `.git/hooks/pre-commit` ซึ่ง**ไม่ได้ commit ขึ้น repo** ดังนั้นทุกคนที่ clone ใหม่ต้องรันเองครั้งนึง ไม่งั้น `git commit` จะผ่านไปเฉย ๆ โดยไม่เช็ค format

- ถ้าไฟล์ format ไม่ถูก hook จะ fail และ commit ไม่ผ่าน
- แก้โดยรัน `uv run ruff format .` แล้ว `git add` ไฟล์ที่เปลี่ยน และ commit อีกครั้ง

รันด้วยมือทั้งโปรเจกต์:

```bash
uv run pre-commit run --all-files
```

## คำสั่ง uv run

| คำสั่ง | ทำอะไร |
| --- | --- |
| `uv run rag-gis-api` | start FastAPI ด้วย uvicorn ที่ `127.0.0.1:8000` (reload เมื่อ `ENV=local`) |
| `uv run rag-gis-chat "<คำถาม>"` | ถาม API ที่รันอยู่ผ่าน SSE แล้ว print แต่ละ event พร้อมเวลาที่ได้รับ ใช้ตรวจว่า stream ทำงานจริง (ต้องเปิด `rag-gis-api` ค้างไว้ก่อน) |
| `uv run rag-gis-chat "<คำถาม>" --url <url>` | ชี้ไป endpoint อื่น เช่นตอนรัน server คนละ port |
| `uv run rag-gis-ingest` | ingest PDF ทุกไฟล์ใน `documents/` เข้า vector store (ข้ามไฟล์ที่ไม่เปลี่ยน) |
| `uv run rag-gis-ingest <path>` | ingest เฉพาะไฟล์เดียว โดย path อ้างจาก `documents/` |
| `uv run rag-gis-ingest <folder>` | ingest ทุกไฟล์ในโฟลเดอร์นั้น รวม subfolder เช่น `law/min_notif` |
| `uv run rag-gis-ingest --reset` | ลบ chunk ทั้งหมดทิ้งก่อน แล้ว ingest ใหม่ทั้งหมด |
| `uv run rag-gis-ingest --clear` | ลบ chunk ทั้งหมดอย่างเดียว ไม่ ingest ต่อ |
| `uv run rag-gis-load-pdf` | อ่าน PDF ใน `documents/` แล้ว print เนื้อหาแต่ละหน้า ใช้ตรวจว่า PyPDF อ่านไฟล์ออกไหม |
| `uv run rag-gis-load-pdf <path>` | ระบุไฟล์เอง โดย path อ้างจาก `documents/` |
| `uv run rag-gis-load-pdf <path> --page N` | print เฉพาะหน้า N (เริ่มที่ 0) |
| `uv run rag-gis-load-doc <path>` | print chunk ของไฟล์ที่ ingest ไว้แล้วใน vector store แยกตามหน้า (path จำเป็น อ้างจาก `documents/`) |
| `uv run rag-gis-load-doc <path> --page N` | print เฉพาะ chunk ของหน้า N (เริ่มที่ 0) |
| `uv run rag-gis-prompt` | ส่ง prompt ตัวอย่างไปหา LLM แล้ว print คำตอบ ใช้ตรวจว่าต่อ Gemini ได้ไหม |
| `uv run rag-gis-prompt "<คำถาม>"` | ถามคำถามเอง (system prompt กำกับให้ตอบสั้น ๆ ไม่เกิน 2 ประโยค) |
| `uv run ruff format .` | format โค้ดทั้งโปรเจกต์ |
| `uv run ruff check .` | ตรวจ lint |
| `uv run pre-commit run --all-files` | รัน hook กับไฟล์ทั้งหมดโดยไม่ต้อง commit |

## เพิ่ม dependencies

```bash
# dependency ที่ใช้ตอน run
uv add <package>

# dependency ที่ใช้แค่ตอน dev เช่น ruff, pre-commit
uv add --dev <package>

# ลบออก
uv remove <package>
```

`uv add` จะแก้ `pyproject.toml` อัปเดต `uv.lock` และติดตั้งลง `.venv` ให้เลย — commit ทั้ง `pyproject.toml` และ `uv.lock` ด้วย
