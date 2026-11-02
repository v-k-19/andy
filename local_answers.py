"""Fast, deterministic answers from the computer's local clock."""
from datetime import datetime
import re
import unicodedata


def local_reply(text, now=None):
    spoken = ''.join(char for char in text.lower() if char.isspace() or unicodedata.category(char)[0] in 'LMN').strip()
    spoken = re.sub(r'\s+', ' ', spoken)
    telugu_time = {'సమయం ఎంత', 'ఇప్పుడు సమయం ఎంత', 'టైం ఎంత', 'టైమ్ ఎంత',
                   'ఇప్పుడు టైం ఎంత', 'ఇప్పుడు టైమ్ ఎంత', 'సమయం చెప్పు',
                   'time entha', 'time enta', 'ippudu time entha', 'ippudu time enta'}
    telugu_date = {'ఈరోజు తేదీ ఎంత', 'ఈరోజు తేదీ ఏమిటి', 'ఈ రోజు తేదీ ఏమిటి', 'తేదీ చెప్పు'}
    telugu_day = {'ఈరోజు ఏ రోజు', 'ఈ రోజు ఏ రోజు', 'ఈరోజు ఏ వారం'}
    if spoken in telugu_time | telugu_date | telugu_day:
        now = now or datetime.now().astimezone()
        if spoken in telugu_time:
            period = 'ఉదయం' if 5 <= now.hour < 12 else 'మధ్యాహ్నం' if 12 <= now.hour < 17 else 'సాయంత్రం' if 17 <= now.hour < 21 else 'రాత్రి'
            return f"ఇప్పుడు {period} {now.hour % 12 or 12}:{now.minute:02d}."
        if spoken in telugu_day:
            days = ['సోమవారం', 'మంగళవారం', 'బుధవారం', 'గురువారం', 'శుక్రవారం', 'శనివారం', 'ఆదివారం']
            return f'ఈరోజు {days[now.weekday()]}.'
        return f'ఈరోజు తేదీ {now.day}-{now.month}-{now.year}.'
    normalized = re.sub(r"[^a-z0-9\s]", '', text.lower().replace('’', "'"))
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    normalized = re.sub(r'^(?:hey )?andy\s+', '', normalized)
    normalized = re.sub(r'^(?:please |can you |could you )+', '', normalized)
    normalized = re.sub(r'\s+(?:please|right now|now)$', '', normalized)
    clock = {'time', 'time now', 'the time', 'current time', 'whats the time',
             'what is the time', 'what time is it', 'tell me the time',
             'tell me what time it is', 'do you know what time it is'}
    dates = {'date', 'todays date', 'whats todays date', 'what is todays date',
             'what is the date', 'whats the date', 'what date is it',
             'tell me the date', 'what is todays date today'}
    days = {'day', 'what day is it', 'what day is today', 'what day is it today',
            'whats the day today', 'tell me the day'}
    if normalized not in clock | dates | days:
        return None
    now = now or datetime.now().astimezone()
    if normalized in clock:
        return f"It's {now.hour % 12 or 12}:{now.minute:02d} {'a.m.' if now.hour < 12 else 'p.m.'}"
    if normalized in days:
        return f"Today is {now.strftime('%A')}."
    return f"Today is {now.strftime('%A, %B')} {now.day}, {now.year}."
