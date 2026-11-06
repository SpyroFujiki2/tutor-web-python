"""Private local attachment storage; files are served only after booking checks."""

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import ROOT_DIR
from app.models import Message
from app.modules.common import require
from app.modules.tutoring.access import accessible_booking
from app.modules.tutoring.dispute import dispute_access

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
DEFAULT_UPLOAD_ROOT = ROOT_DIR / 'uploads' / 'tutoring'
FORMATS = {'application/pdf': 'pdf', 'image/png': 'png', 'image/jpeg': 'jpg', 'text/plain': 'txt'}
MEDIA_TYPES = {extension: media_type for media_type, extension in FORMATS.items()}


@dataclass(frozen=True)
class StoredAttachment:
    path: Path
    identity: UUID
    extension: str

    def url(self, booking_id: UUID) -> str:
        return f'/api/bookings/{booking_id}/attachments/{self.identity}.{self.extension}'


def attachment_path(root: Path, identity: UUID, extension: str) -> Path:
    require(extension in MEDIA_TYPES, 'Loại tệp không được hỗ trợ')
    root = root.resolve()
    path = (root / f'{identity}.{extension}').resolve()
    require(path.parent == root, 'Đường dẫn tệp không hợp lệ', PermissionError)
    return path


def store_attachment(root: Path, content: bytes, media_type: str) -> StoredAttachment:
    require(0 < len(content) <= MAX_ATTACHMENT_BYTES, 'Tệp phải có dung lượng từ 1 byte đến 5 MB')
    extension = FORMATS.get(media_type)
    require(extension is not None, 'Chỉ nhận PDF, PNG, JPEG hoặc văn bản UTF-8')
    if extension == 'pdf':
        require(content.startswith(b'%PDF-'), 'Nội dung không phải PDF')
    elif extension == 'png':
        require(content.startswith(b'\x89PNG\r\n\x1a\n'), 'Nội dung không phải PNG')
    elif extension == 'jpg':
        require(content.startswith(b'\xff\xd8\xff'), 'Nội dung không phải JPEG')
    else:
        try:
            content.decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError('Văn bản phải là UTF-8') from None
        require(b'\x00' not in content, 'Văn bản không được chứa byte null')
    root.mkdir(parents=True, exist_ok=True)
    identity = uuid4()
    path = attachment_path(root, identity, extension)
    created = False
    try:
        with path.open('xb') as target:
            created = True
            target.write(content)
    except BaseException:
        if created:
            path.unlink(missing_ok=True)
        raise
    return StoredAttachment(path, identity, extension)


def authorize_download(
    session: Session, user_id: UUID, booking_id: UUID, identity: UUID, extension: str,
) -> Message:
    url = f'/api/bookings/{booking_id}/attachments/{identity}.{extension}'
    message = session.scalar(select(Message).where(Message.booking_id == booking_id, Message.file_url == url))
    require(message is not None, 'Không tìm thấy tệp', LookupError)
    if message.dispute_id is not None:
        dispute = dispute_access(session, user_id, message.dispute_id)
        require(dispute.booking_id == booking_id, 'Không tìm thấy tệp', LookupError)
    else:
        accessible_booking(session, user_id, booking_id)
    return message
