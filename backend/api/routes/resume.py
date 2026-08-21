"""简历上传/解析路由。"""
from fastapi import APIRouter, File, UploadFile, HTTPException

from api import schemas
from services import resume_parser

router = APIRouter()


@router.post("/upload", response_model=schemas.ResumeTextOut)
async def upload_resume(file: UploadFile = File(...)):
    """上传 PDF 简历，返回解析后的原始文本。"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="V1 仅支持 PDF")
    content = await file.read()
    text = resume_parser.parse_pdf(content)
    if not text:
        raise HTTPException(status_code=422, detail="未能从 PDF 中提取到文本")
    return {"text": text}
