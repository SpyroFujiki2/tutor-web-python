"""Repeatable one-course seed from ten real Google Drive file links."""

import re
from urllib.parse import parse_qs, urlsplit
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.models import Course, Lesson
from app.models.enums import CourseStatus
from app.modules.common import add, now, require

SOURCE_FOLDER = 'https://drive.google.com/drive/folders/1WM8foEk5gsIMs0OikFlnIiKwp7MvYplF'
COURSE_ID = uuid5(NAMESPACE_URL, SOURCE_FOLDER)


def drive_file_id(url: str) -> str:
    parsed = urlsplit(url)
    require(parsed.scheme == 'https' and parsed.hostname == 'drive.google.com'
            and not parsed.username and not parsed.password, 'Cần link video HTTPS của Google Drive')
    match = re.match(r'^/file/d/([A-Za-z0-9_-]{10,200})(?:/|$)', parsed.path)
    identity = match.group(1) if match else (
        parse_qs(parsed.query).get('id', [''])[0] if parsed.path in {'/open', '/uc'} else '')
    require(bool(re.fullmatch(r'[A-Za-z0-9_-]{10,200}', identity)), 'Link cần trỏ tới file video, không phải thư mục')
    return identity


class SeedVideo(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    url: str
    title: str = Field(default='', max_length=200)
    duration_minutes: int | None = Field(default=None, gt=0, le=10000)


class DriveCourseSeed(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    source_folder: str = SOURCE_FOLDER
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=20000)
    price: int = Field(default=0, strict=True, ge=0, le=2147483647)
    videos: list[SeedVideo] = Field(min_length=10, max_length=10)

    @model_validator(mode='after')
    def real_distinct_links(self):
        require(self.source_folder == SOURCE_FOLDER, 'Seed này dành cho thư mục Drive đã cung cấp')
        identities = [drive_file_id(video.url) for video in self.videos]
        require(len(set(identities)) == 10, 'Cần đúng 10 video khác nhau')
        return self


def seed_drive_course(session, manifest: DriveCourseSeed) -> tuple[Course, bool]:
    course = session.get(Course, COURSE_ID, with_for_update=True)
    expected = [(uuid5(COURSE_ID, drive_file_id(video.url)), index,
                 f'https://drive.google.com/file/d/{drive_file_id(video.url)}/view', video.duration_minutes)
                for index, video in enumerate(manifest.videos, 1)]
    if course is not None:
        actual = [(row.id, row.order_idx, row.media_url, row.duration_minutes) for row in session.scalars(
            select(Lesson).where(Lesson.course_id == course.id).order_by(Lesson.order_idx))]
        require(actual == expected, 'Khóa seed đã tồn tại với nội dung khác; không ghi đè lịch sử học')
        return course, False
    course = add(session, Course, id=COURSE_ID, title=manifest.title, description=manifest.description,
                 price=manifest.price, is_live=False, status=CourseStatus.VISIBLE, created_at=now(), updated_at=now())
    for identity, order, url, duration in expected:
        add(session, Lesson, id=identity, course_id=course.id, order_idx=order,
            media_url=url, duration_minutes=duration)
    return course, True
