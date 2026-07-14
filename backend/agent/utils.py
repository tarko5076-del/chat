import re
from datetime import date, timedelta


STOP_WORDS = frozenset({
    "i", "want", "order", "add", "the", "a", "an", "please", "my",
    "last", "same", "thing", "time", "for", "to", "do", "you", "have",
    "what", "show", "me", "can", "get", "with", "and", "or",
})

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\b(?:\+?\d[\d .-]{6,}\d)\b")
DATE_ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
TIME_RE = re.compile(r"\bat\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b")
TIME_COLON_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))\s*(am|pm)?\b")
TIME_AMPM_RE = re.compile(r"\b(\d{1,2})\s*(am|pm)\b", re.I)
TIME_HOURS_RE = re.compile(r"\b(\d{1,2})\s*hours?\s*(am|pm)?\b", re.I)
PARTY_SIZE_RE = re.compile(r"(?:for|to)\s*(\d+)|(\d+)\s*(?:people|guests|person)")
NAME_PATTERNS = [
    re.compile(r"(?:my name is|name is|it's|it is|i am|i'm)\s+([A-Za-z]+(?: [A-Za-z]+)?)", re.I),
    re.compile(r"\bfor\s+([A-Za-z]+(?: [A-Za-z]+)?)\b", re.I),
]

RESERVATION_WORDS = frozenset({
    "reserve", "reservation", "book", "booking", "table", "seat", "seating",
})


def words(text):
    return {
        word
        for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in STOP_WORDS and len(word) > 1
    }


def parse_date(text):
    lower = text.lower()
    if "tomorrow" in lower:
        return (date.today() + timedelta(days=1)).isoformat()
    if "today" in lower:
        return date.today().isoformat()
    match = DATE_ISO_RE.search(text)
    return match.group(0) if match else None


def parse_time(text):
    match = TIME_RE.search(text)
    if not match:
        match = TIME_COLON_RE.search(text)
    if not match:
        match = TIME_AMPM_RE.search(text)
    if not match:
        match = TIME_HOURS_RE.search(text)
    if not match:
        return None

    groups = match.groups()
    hour = int(match.group(1))
    minute = int(groups[1]) if len(groups) > 1 and groups[1] and str(groups[1]).isdigit() else 0
    meridiem = groups[2] if len(groups) > 2 else groups[1]

    if isinstance(meridiem, str) and meridiem.lower() == "pm" and hour < 12:
        hour += 12
    if isinstance(meridiem, str) and meridiem.lower() == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def parse_party_size(text):
    match = PARTY_SIZE_RE.search(text)
    return int(match.group(1) or match.group(2)) if match else None


def cuisine_hint_words(text):
    lowered = text.lower()
    hints = set()
    if any(word in lowered for word in ["sushi", "seafood", "fish"]):
        hints.update({"fish", "salmon", "seafood", "calamari", "shrimp", "squid"})
    if "pizza" in lowered:
        hints.update({"pizza", "tomato", "mozzarella", "cheese"})
    if "pasta" in lowered or "lasagna" in lowered:
        hints.update({"pasta", "spaghetti", "penne", "carbonara", "tomato", "parmesan"})
    if "burger" in lowered:
        hints.update({"chicken", "bread", "cheese"})
    return hints


def extract_email(text):
    match = EMAIL_RE.search(text)
    return match.group(0) if match else None


def extract_phone(text):
    match = PHONE_RE.search(text)
    if match:
        value = match.group(0)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value.strip()
    return None


def extract_name(text):
    for pattern in NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            name = match.group(1).strip()
            if pattern == NAME_PATTERNS[1]:
                lower = name.lower()
                skip = {"dinner", "lunch", "breakfast", "tonight", "tomorrow", "today"}
                if lower in skip:
                    continue
            return name.title()

    stripped = text.strip()
    if re.fullmatch(r"[A-Za-z]+(?:['-][A-Za-z]+)?", stripped, re.I):
        common = {"yes", "no", "ok", "okay", "please", "thanks", "hello", "hi", "hey", "help"}
        if stripped.lower() not in common:
            return stripped.title()
    return None


def looks_like_phone(text):
    digits = re.sub(r"[^\d]", "", text)
    return 7 <= len(digits) <= 15
