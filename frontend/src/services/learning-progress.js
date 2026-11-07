function percent(value) {
  const result = Math.round(value * 100) / 100
  return value < 100 ? Math.min(99.99, result) : 100
}

export function learningProgress(lessons, progressRows, attendanceRows, localWatch, isLive) {
  const confirmed = new Map(progressRows.map((row) => [row.lesson_id, row]))
  const attendance = new Map(attendanceRows.map((row) => [row.lesson_id, row]))
  const rows = lessons.map((lesson) => {
    const saved = confirmed.get(lesson.id)
    const record = attendance.get(lesson.id)
    const local = localWatch[lesson.id]
    const duration = local?.duration_seconds || saved?.duration_seconds || lesson.duration_seconds || (lesson.duration_minutes ? lesson.duration_minutes * 60 : null)
    const watched = Math.max(0, Number(local?.duration_watched ?? 0), Number(saved?.duration_watched ?? 0), Number(record?.duration_watched ?? 0))
    const hasAssignment = !!lesson.assignment_url?.trim()
    const assignmentCompleted = saved ? !!saved.assignment_completed : !!record?.assignment_completed
    let raw = 0
    if (hasAssignment) raw = assignmentCompleted ? 100 : 0
    else if (isLive) raw = saved ? Number(saved.progress_percent) : record && !record.is_absent ? 100 : 0
    else if (duration > 0) raw = Math.min(100, watched / duration * 100)
    return { lesson_id: lesson.id, duration_seconds: duration, duration_watched: watched,
      has_assignment: hasAssignment, assignment_completed: assignmentCompleted,
      progress_percent: percent(raw), is_completed: raw >= 100, fraction: raw / 100 }
  })
  const raw = rows.length ? rows.reduce((sum, row) => sum + row.fraction * 100, 0) / rows.length : 0
  return { rows, progress_percent: percent(raw) }
}
