import hashlib
import json
import uuid
from datetime import date


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def digest(value):
    data = value if isinstance(value, bytes) else json_text(value).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def parse_date(value):
    return date.fromisoformat(value) if value else None


def serializable(value):
    return json.loads(json_text(value))
