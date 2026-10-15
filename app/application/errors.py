"""Application failures independent of transport and vendor exceptions."""


class NoteNotFound(Exception):
    def __init__(self) -> None:
        super().__init__("Note not found")


class EmailAlreadyRegistered(Exception):
    def __init__(self) -> None:
        super().__init__("Email already registered")


class DependencyUnavailable(Exception):
    def __init__(self) -> None:
        super().__init__("Service unavailable")


class NotAuthenticated(Exception):
    def __init__(self) -> None:
        super().__init__("Not authenticated")


class InvalidCredentials(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid credentials")


class FileNotFound(Exception):
    def __init__(self) -> None:
        super().__init__("File not found")
