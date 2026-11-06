"""Catalog authoring, purchases and server-controlled learning results."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select

from app.models import Attendance, Course, CourseProgress, Lesson, UserSubscription
from app.models.enums import CourseResult, CourseStatus, ServiceType, SubscriptionStatus, TransactionType
from app.modules.common import actor, add, audit, get, now, require
from app.modules.finance.payments import owned_wallet, platform_wallet, transfer
from app.modules.learning.lesson import list_my_course_lessons


def save_course(session, admin_id, values, course_id=None):
    admin = actor(session, admin_id, admin=True)
    if course_id is None:
        row = add(session, Course, **values, created_at=now(), updated_at=now())
    else:
        row = get(session, Course, course_id, lock=True)
        # Live/VOD affects completion rules; don't reinterpret existing purchases.
        if row.is_live != values["is_live"]:
            require(not session.scalar(select(CourseProgress.subscription_id).where(CourseProgress.course_id == row.id).limit(1)),
                    "Không đổi loại khóa đã có học viên")
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = now()
    audit(session, admin, row, "course.save", after={"title": row.title, "price": row.price, "status": row.status})
    return row


def save_lesson(session, admin_id, course_id, values, lesson_id=None):
    admin = actor(session, admin_id, admin=True)
    course = get(session, Course, course_id, lock=True)
    require(not session.scalar(select(CourseProgress.subscription_id).where(CourseProgress.course_id == course_id).limit(1)),
            "Cấu trúc bài học đã có học viên được cố định; tạo khóa mới để đổi nội dung")
    require(course.is_live or values.get("duration_minutes"), "Bài VOD cần thời lượng")
    if lesson_id is None:
        row = add(session, Lesson, course_id=course_id, **values)
    else:
        row = get(session, Lesson, lesson_id, lock=True)
        require(row.course_id == course_id, "Bài học không thuộc khóa", LookupError)
        for key, value in values.items():
            setattr(row, key, value)
    audit(session, admin, row, "lesson.save", after={"order_idx": row.order_idx})
    return row


def reorder_lessons(session, admin_id, course_id, ids):
    admin = actor(session, admin_id, admin=True)
    course = get(session, Course, course_id, lock=True)
    rows = list(session.scalars(select(Lesson).where(Lesson.course_id == course_id)))
    require(len(ids) == len(set(ids)) and set(ids) == {row.id for row in rows}, "Cần đủ bài học, không trùng lặp")
    # Temporary values avoid the non-deferrable unique constraint.
    by_id = {row.id: row for row in rows}
    temporary_start = max([row.order_idx for row in rows] + [0]) + 1
    for index, row in enumerate(rows):
        row.order_idx = temporary_start + index
    session.flush()
    for index, identity in enumerate(ids, 1):
        by_id[identity].order_idx = index
    audit(session, admin, course, "lesson.reorder", after={"lesson_ids": [str(i) for i in ids]})
    return [by_id[i] for i in ids]


def remove_lesson(session, admin_id, course_id, lesson_id):
    admin = actor(session, admin_id, admin=True)
    get(session, Course, course_id, lock=True)
    row = get(session, Lesson, lesson_id, lock=True)
    require(row.course_id == course_id, "Bài học không thuộc khóa", LookupError)
    require(not session.scalar(select(CourseProgress.subscription_id).where(CourseProgress.course_id == course_id).limit(1)),
            "Không xóa bài học của khóa đã có học viên")
    audit(session, admin, row, "lesson.remove")
    session.delete(row)


def purchase_course(session, user_id, course_id, request_id):
    actor(session, user_id, lock=True)
    existing = session.get(UserSubscription, request_id)
    if existing:
        progress = session.get(CourseProgress, request_id)
        require(existing.user_id == user_id and existing.type == ServiceType.COURSE and progress
                and progress.course_id == course_id, "Mã yêu cầu đã được dùng")
        return existing
    course = get(session, Course, course_id, lock=True)
    require(course.status == CourseStatus.VISIBLE and course.price is not None, "Khóa học chưa mở bán")
    require(session.scalar(select(Lesson.id).where(Lesson.course_id == course_id).limit(1)), "Khóa học chưa có bài")
    subscription = add(session, UserSubscription, id=request_id, user_id=user_id, type=ServiceType.COURSE,
                       title_at_purchase=course.title, price_at_purchase=course.price,
                       status=SubscriptionStatus.ACTIVE, activated_at=now())
    transfer(session, owned_wallet(session, user_id).id, platform_wallet(session), course.price,
             TransactionType.PAYMENT, subscription_id=subscription.id)
    add(session, CourseProgress, subscription_id=subscription.id, course_id=course_id,
        progress_percent=Decimal(0), updated_at=now())
    return subscription


def recalculate(session, progress):
    course = get(session, Course, progress.course_id)
    lessons = list(session.scalars(select(Lesson).where(Lesson.course_id == course.id)))
    rows = {row.lesson_id: row for row in session.scalars(select(Attendance).where(
        Attendance.subscription_id == progress.subscription_id))}
    complete = 0
    for lesson in lessons:
        attendance = rows.get(lesson.id)
        if attendance and (not attendance.is_absent if course.is_live or lesson.duration_minutes is None else
                           attendance.duration_watched >= lesson.duration_minutes * 60):
            complete += 1
    ratio = Decimal(complete) / len(lessons) if lessons else Decimal(0)
    progress.attendance_ratio = ratio.quantize(Decimal("0.0001"))
    grades = [progress.midterm_score, progress.endterm_score, progress.practice_score]
    # 100% requires a server-side assessment, as required by the schema check.
    percent = min(Decimal("99.99"), (ratio * 100).quantize(Decimal("0.01")))
    if lessons and complete == len(lessons) and all(value is not None for value in grades):
        score = int((sum(Decimal(value) for value in grades) / 3).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        progress.progress_percent = Decimal("100.00")
        progress.final_score = score
        progress.result = CourseResult.EXCELLENT if score >= 85 else CourseResult.GOOD if score >= 50 else CourseResult.FAILED
        progress.completed_at = progress.completed_at or now()
    else:
        progress.progress_percent = percent
        progress.final_score = progress.result = progress.completed_at = None
    progress.updated_at = now()
    session.flush()
    return progress


def record_attendance(session, user_id, subscription_id, lesson_id, duration_watched, completed=False):
    actor(session, user_id)
    progress = get(session, CourseProgress, subscription_id, lock=True)
    lessons = list_my_course_lessons(session, subscription_id, user_id)
    lesson = next((row for row in lessons if row.id == lesson_id), None)
    require(lesson is not None, "Bài học không thuộc khóa", LookupError)
    require(not get(session, Course, progress.course_id).is_live, "Điểm danh trực tiếp do quản trị ghi nhận")
    row = session.get(Attendance, (subscription_id, lesson_id))
    duration = min(duration_watched, lesson.duration_minutes * 60) if lesson.duration_minutes else duration_watched
    confirmed = completed or (lesson.duration_minutes is not None and duration >= lesson.duration_minutes * 60)
    if row is None:
        row = add(session, Attendance, subscription_id=subscription_id, lesson_id=lesson_id,
                  course_id=lesson.course_id, duration_watched=duration, is_absent=not confirmed)
    else:
        row.duration_watched = max(row.duration_watched, duration)
        row.is_absent = row.is_absent and not confirmed
    # Watch time is self-reported, never used as a trusted final exam score.
    session.flush()
    return recalculate(session, progress)


def grade_course(session, admin_id, subscription_id, values):
    admin = actor(session, admin_id, admin=True)
    progress = get(session, CourseProgress, subscription_id, lock=True)
    for key, value in values.items():
        setattr(progress, key, value)
    recalculate(session, progress)
    audit(session, admin, progress, "course.grade", after=values)
    return progress


def live_attendance(session, admin_id, subscription_id, lesson_id, is_absent):
    admin = actor(session, admin_id, admin=True)
    progress = get(session, CourseProgress, subscription_id, lock=True)
    subscription = get(session, UserSubscription, subscription_id)
    require(subscription.status == SubscriptionStatus.ACTIVE and subscription.activated_at <= now()
            and (subscription.expired_at is None or subscription.expired_at > now()), "Quyền học đã hết hạn")
    require(get(session, Course, progress.course_id).is_live, "Chỉ áp dụng cho khóa trực tiếp")
    lesson = get(session, Lesson, lesson_id)
    require(lesson.course_id == progress.course_id, "Bài học không thuộc khóa")
    row = session.get(Attendance, (subscription_id, lesson_id))
    if row is None:
        row = add(session, Attendance, subscription_id=subscription_id, lesson_id=lesson_id,
                  course_id=lesson.course_id, is_absent=is_absent, duration_watched=0)
    else:
        row.is_absent = is_absent
    session.flush()
    recalculate(session, progress)
    audit(session, admin, progress, "course.attendance", after={"lesson_id": str(lesson_id), "is_absent": is_absent})
    return progress


def refund_course(session, admin_id, subscription_id, reason):
    """Administrative full refund; retain lessons, attendance and grades as history."""
    admin = actor(session, admin_id, admin=True)
    subscription = get(session, UserSubscription, subscription_id, lock=True)
    require(subscription.type == ServiceType.COURSE, "Chỉ áp dụng cho quyền khóa học")
    if subscription.status == SubscriptionStatus.CANCELLED:
        return subscription
    require(subscription.price_at_purchase is not None, "Không có giá mua để hoàn")
    transfer(session, platform_wallet(session), owned_wallet(session, subscription.user_id, require_active=False).id,
             subscription.price_at_purchase, TransactionType.REFUND,
             subscription_id=subscription.id, admin_id=admin.id, allow_inactive_destination=True)
    subscription.status = SubscriptionStatus.CANCELLED
    audit(session, admin, subscription, "course.refund", after={"amount": subscription.price_at_purchase}, reason=reason)
    return subscription
