from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.database import get_session
from app.models import User
from app.modules.tutoring.attachments import (
    DEFAULT_UPLOAD_ROOT, MAX_ATTACHMENT_BYTES, MEDIA_TYPES, attachment_path, authorize_download, store_attachment,
)
from app.modules.tutoring.message import check_message_permission, send_file_message
from app.schemas.responses import MessageResponse

router = APIRouter(prefix='/bookings', tags=['tutoring files'])
DB = Annotated[Session, Depends(get_session)]
Current = Annotated[User, Depends(get_current_user)]


def upload_root(request: Request) -> Path:
    return Path(getattr(request.app.state, 'tutoring_upload_root', DEFAULT_UPLOAD_ROOT))


@router.post('/{booking_id}/attachments', response_model=MessageResponse, status_code=201)
async def upload(
    booking_id: UUID, request: Request, session: DB, user: Current,
    name: str = Query(min_length=1, max_length=120), dispute_id: UUID | None = None,
):
    await run_in_threadpool(check_message_permission, session, user.id, booking_id, dispute_id, lock=False)
    media_type = request.headers.get('content-type', '').split(';')[0].strip().lower()
    if media_type not in MEDIA_TYPES.values():
        raise HTTPException(status_code=415, detail='Chỉ nhận PDF, PNG, JPEG hoặc văn bản UTF-8')
    declared = request.headers.get('content-length')
    if declared and (not declared.isdigit() or int(declared) > MAX_ATTACHMENT_BYTES):
        raise HTTPException(status_code=413, detail='Tệp vượt giới hạn 5 MB')
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_ATTACHMENT_BYTES:
            raise HTTPException(status_code=413, detail='Tệp vượt giới hạn 5 MB')
        content.extend(chunk)
    # Never hold a booking row lock while waiting for a network upload.
    def commit_file():
        stored = store_attachment(upload_root(request), bytes(content), media_type)
        try:
            row = send_file_message(session, user.id, booking_id, stored.url(booking_id), name, dispute_id)
            result = MessageResponse.model_validate(row)
            session.commit()
            return result
        except BaseException:
            session.rollback()
            stored.path.unlink(missing_ok=True)
            raise
    return await run_in_threadpool(commit_file)


@router.get('/{booking_id}/attachments/{identity}.{extension}')
def download(
    booking_id: UUID, identity: UUID, extension: Literal['pdf', 'png', 'jpg', 'txt'],
    request: Request, session: DB, user: Current,
):
    authorize_download(session, user.id, booking_id, identity, extension)
    path = attachment_path(upload_root(request), identity, extension)
    if not path.is_file():
        raise HTTPException(status_code=404, detail='Tệp không còn trên máy chủ')
    return FileResponse(path, filename=f'attachment-{identity}.{extension}', media_type=MEDIA_TYPES[extension],
                        content_disposition_type='attachment', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
