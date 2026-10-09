"""Domain validation errors."""


class InvalidUserData(ValueError):
    """User input violates a domain rule."""


class InvalidFileData(ValueError):
    """File input violates a domain rule."""


class FileTooLarge(InvalidFileData):
    def __init__(self) -> None:
        super().__init__("File too large")
