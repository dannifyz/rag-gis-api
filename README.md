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
