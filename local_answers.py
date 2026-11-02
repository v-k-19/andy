"""Fast, deterministic answers from the computer's local clock."""
from datetime import datetime
import re


def local_reply(text, now=None):
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
