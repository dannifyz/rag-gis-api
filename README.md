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

รัน API:

```bash
uv run rag-gis-api
```

เปิดที่ http://127.0.0.1:8000/api/health

## Git hook (format ก่อน commit)

ตั้งค่าไว้ที่ `.pre-commit-config.yaml` ใช้ `ruff-format` ทุกครั้งที่ `git commit`

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
| `uv run rag-gis-load-pdf` | อ่าน PDF ใน `documents/` แล้ว print เนื้อหาแต่ละหน้า ใช้ตรวจว่า PyPDF อ่านไฟล์ออกไหม |
| `uv run rag-gis-load-pdf <path>` | ระบุไฟล์เอง โดย path อ้างจาก `documents/` |
| `uv run rag-gis-load-pdf <path> --page N` | print เฉพาะหน้า N (เริ่มที่ 0) |
| `uv run ruff format .` | format โค้ดทั้งโปรเจกต์ |
| `uv run ruff check .` | ตรวจ lint |
| `uv run pre-commit install` | ติดตั้ง git hook |
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
