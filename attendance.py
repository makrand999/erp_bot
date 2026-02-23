"""
attendance.py
Handles formatting and comparison of attendance data.

Attendance shape (from browser.py):
  { subject_name: { "present": int, "total": int } }
"""

import math


# ─── Short name helper ────────────────────────────────────────────────────────

def to_short_name(subject: str) -> str:
    return ''.join(
        word[0].upper() for word in subject.split() if word
    )


# ─── Emoji based on % ────────────────────────────────────────────────────────

def get_emoji(present: int, total: int) -> str:
    if total == 0:
        return '⚪'
    pct = (present / total) * 100
    if pct >= 75:
        return '🟢'
    if pct >= 60:
        return '🟡'
    return '🔴'


def get_pct(present: int, total: int) -> str:
    if total == 0:
        return 'N/A'
    return f"{round((present / total) * 100)}%"


# ─── Format: short (abbreviated subject names) ────────────────────────────────

def format_attendance_short(attendance: dict) -> str:
    if not attendance:
        return 'No attendance data found.'

    lines = ["📊 *Attendance Summary*\n", "```"]
    lines.append(f"{'Sub':<10} {'P/T':<8} {'Pct':>5}")
    lines.append("─" * 26)

    for subject, data in attendance.items():
        present, total = data['present'], data['total']
        short = to_short_name(subject)
        emoji = get_emoji(present, total)
        pct = get_pct(present, total)
        lines.append(f"{emoji}{short:<9} {present}/{total:<6} {pct:>5}")

    lines.append("```")
    lines.append("_🟢≥75%  🟡60–74%  🔴<60%_")

    return '\n'.join(lines)


# ─── Total percentage ─────────────────────────────────────────────────────────

def total_percentage(attendance: dict) -> str:
    total_present = 0
    total_classes = 0

    for data in attendance.values():
        total_present += data['present']
        total_classes += data['total']

    return get_pct(total_present, total_classes)


# ─── Format: full (complete subject names) ────────────────────────────────────

def format_attendance_full(attendance: dict) -> str:
    lines = []
    for subject, data in attendance.items():
        present, total = data['present'], data['total']
        emoji = get_emoji(present, total)
        pct = get_pct(present, total)
        lines.append(f"{emoji} {subject}: {present}/{total} ({pct})")

    if not lines:
        return 'No attendance data found.'

    return f"📋 *Full Attendance*\n\n" + '\n'.join(lines) + '\n\n_🟢≥75%  🟡60–74%  🔴<60%_'


# ─── Format: only low attendance subjects (<75%) ──────────────────────────────

def format_low_attendance(attendance: dict, threshold: int = 75) -> str | None:
    low = [
        (subject, data)
        for subject, data in attendance.items()
        if data['total'] > 0 and (data['present'] / data['total']) * 100 < threshold
    ]

    if not low:
        return None

    lines = []
    for subject, data in low:
        present, total = data['present'], data['total']
        short = to_short_name(subject)
        pct = get_pct(present, total)
        needed = lectures_needed_for_75(present, total)
        lines.append(f"🔴 *{short}*: {present}/{total} ({pct}) — need {needed} more")

    return f"⚠️ *Low Attendance (< {threshold}%)*\n\n" + '\n'.join(lines)


# ─── How many more lectures needed to reach 75% ──────────────────────────────

def lectures_needed_for_75(present: int, total: int) -> int:
    # Solve: (present + x) / (total + x) >= 0.75
    needed = math.ceil((0.75 * total - present) / 0.25)
    return max(needed, 0)


# ─── Compare old vs new attendance ───────────────────────────────────────────

def compare_attendance(old_att: dict, new_att: dict) -> list:
    """
    Returns list of changed subjects:
    [{ 'subject': str, 'old': {present, total}, 'current': {present, total} }]
    """
    changes = []

    for subject, current in new_att.items():
        old = old_att.get(subject, {'present': 0, 'total': 0})
        if old['present'] == current['present'] and old['total'] != current['total']:
            changes.append({'subject': subject, 'old': old, 'current': current})

    return changes
