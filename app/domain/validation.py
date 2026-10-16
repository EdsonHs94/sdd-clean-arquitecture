"""Pure user and file rules shared by all entry points."""

from unicodedata import category

from email_validator import EmailNotValidError, validate_email

from app.domain.errors import FileTooLarge, InvalidFileData, InvalidNoteData, InvalidUserData


def _validate_note_text(text: str) -> None:
    if "\x00" in text or any(category(char) == "Cs" for char in text):
        raise InvalidNoteData("Note text contains unsupported Unicode characters")


def validate_note_title(title: str) -> str:
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
        raise InvalidNoteData("Title must contain 1–200 characters")
    _validate_note_text(title)
    return title.strip()


def validate_note_body(body: str) -> str:
    if not isinstance(body, str) or len(body) > 10_000:
        raise InvalidNoteData("Body must contain at most 10000 characters")
    _validate_note_text(body)
    return body


def validate_name(name: str) -> str:
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise InvalidUserData("Name must contain 1–100 characters")
    return name.strip()


def normalize_email(email: str) -> str:
    if not isinstance(email, str):
        raise InvalidUserData("Invalid email")
    normalized = email.strip().lower()
    if len(normalized) > 254:
        raise InvalidUserData("Invalid email")
    try:
        validate_email(normalized, check_deliverability=False, strict=True)
    except EmailNotValidError:
        raise InvalidUserData("Invalid email") from None
    return normalized


def validate_password(password: str) -> str:
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise InvalidUserData("Password must contain 8–128 characters")
    return password


MAX_FILE_SIZE = 10_485_760


def validate_filename(filename: str) -> str:
    if not isinstance(filename, str) or not 1 <= len(filename) <= 255:
        raise InvalidFileData("Filename must contain 1–255 characters")
    if any(char in "/\\" or category(char) == "Cc" for char in filename):
        raise InvalidFileData("Filename must not contain separators or control characters")
    return filename


def validate_file_size(size: int) -> int:
    if type(size) is not int or size < 0:
        raise InvalidFileData("Size must be a nonnegative integer")
    if size > MAX_FILE_SIZE:
        raise FileTooLarge()
    return size


def normalize_content_type(content_type: str | None) -> str:
    if content_type is None or content_type == "":
        return "application/octet-stream"
    if not isinstance(content_type, str):
        raise InvalidFileData("Content type must be a string")
    return content_type
