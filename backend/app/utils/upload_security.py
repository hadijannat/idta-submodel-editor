"""
Upload security utilities with magic bytes validation.

Provides secure file upload validation that checks:
- File size (with streaming size check before full read)
- File type by magic bytes, not just extension/MIME
- Randomized filename generation for storage
"""

import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from app.errors import APIError, ErrorCode


class FileType(str, Enum):
    """Supported file types for upload validation."""

    PDF = "pdf"
    AASX = "aasx"  # ZIP-based
    XLSX = "xlsx"  # ZIP-based
    CSV = "csv"
    ZIP = "zip"


# Magic bytes signatures for file type detection
# References:
# - https://en.wikipedia.org/wiki/List_of_file_signatures
# - https://www.garykessler.net/library/file_sigs.html
MAGIC_BYTES: dict[FileType, tuple[bytes, ...]] = {
    FileType.PDF: (b"%PDF",),  # PDF starts with %PDF
    FileType.AASX: (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),  # ZIP signatures
    FileType.XLSX: (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),  # ZIP-based
    FileType.ZIP: (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),  # Standard ZIP
    FileType.CSV: (),  # No magic bytes for CSV, validated differently
}

# File extension mapping
EXTENSION_TO_TYPE: dict[str, FileType] = {
    ".pdf": FileType.PDF,
    ".aasx": FileType.AASX,
    ".xlsx": FileType.XLSX,
    ".xls": FileType.XLSX,
    ".csv": FileType.CSV,
    ".zip": FileType.ZIP,
}


@dataclass
class ValidationResult:
    """Result of upload validation."""

    valid: bool
    file_type: FileType | None = None
    error_code: ErrorCode | None = None
    error_message: str | None = None
    size_bytes: int = 0


def get_file_type_from_extension(filename: str | None) -> FileType | None:
    """Extract file type from filename extension."""
    if not filename:
        return None
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else None
    return EXTENSION_TO_TYPE.get(ext) if ext else None


def check_magic_bytes(content: bytes, file_type: FileType) -> bool:
    """
    Check if file content matches expected magic bytes for the file type.

    Args:
        content: File content (at least first 8 bytes)
        file_type: Expected file type

    Returns:
        True if magic bytes match, False otherwise
    """
    signatures = MAGIC_BYTES.get(file_type)
    if not signatures:
        # No magic bytes to check (e.g., CSV)
        return True

    for signature in signatures:
        if content.startswith(signature):
            return True
    return False


def validate_csv_content(content: bytes) -> bool:
    """
    Basic validation for CSV files.

    Checks that the content is valid UTF-8 text and doesn't start
    with known binary signatures.
    """
    # Check for binary signatures that would indicate wrong file type
    binary_signatures = [
        b"PK",  # ZIP
        b"%PDF",  # PDF
        b"\x89PNG",  # PNG
        b"\xff\xd8\xff",  # JPEG
        b"GIF8",  # GIF
        b"\x00\x00\x00",  # Various binary formats
    ]
    for sig in binary_signatures:
        if content.startswith(sig):
            return False

    # Try to decode as UTF-8 (at least the first portion)
    try:
        content[:4096].decode("utf-8")
        return True
    except UnicodeDecodeError:
        # Try with common CSV encodings
        for encoding in ["latin-1", "cp1252"]:
            try:
                content[:4096].decode(encoding)
                return True
            except UnicodeDecodeError:
                continue
        return False


def generate_secure_filename(original_filename: str, preserve_extension: bool = True) -> str:
    """
    Generate a secure randomized filename.

    Args:
        original_filename: Original filename
        preserve_extension: Whether to keep the file extension

    Returns:
        Randomized filename with optional original extension
    """
    random_part = secrets.token_hex(16)

    if preserve_extension and original_filename and "." in original_filename:
        ext = original_filename.rsplit(".", 1)[-1].lower()
        return f"{random_part}.{ext}"

    return random_part


class UploadValidator:
    """
    Validates file uploads using magic bytes and size limits.

    Usage:
        validator = UploadValidator(
            allowed_types=[FileType.PDF, FileType.AASX],
            max_size_bytes=50 * 1024 * 1024,  # 50MB
        )
        result = validator.validate(content, filename)
        if not result.valid:
            raise APIError(code=result.error_code, message=result.error_message)
    """

    def __init__(
        self,
        allowed_types: list[FileType],
        max_size_bytes: int,
        require_magic_bytes: bool = True,
    ):
        """
        Initialize the validator.

        Args:
            allowed_types: List of allowed file types
            max_size_bytes: Maximum file size in bytes
            require_magic_bytes: Whether to require magic bytes validation
        """
        self.allowed_types = allowed_types
        self.max_size_bytes = max_size_bytes
        self.require_magic_bytes = require_magic_bytes

    def validate(
        self,
        content: bytes,
        filename: str | None = None,
    ) -> ValidationResult:
        """
        Validate file upload.

        Args:
            content: File content
            filename: Original filename (for extension detection)

        Returns:
            ValidationResult with validation status
        """
        size_bytes = len(content)

        # Check size
        if size_bytes > self.max_size_bytes:
            return ValidationResult(
                valid=False,
                error_code=ErrorCode.FILE_TOO_LARGE,
                error_message=f"File too large. Maximum size is {self.max_size_bytes // (1024*1024)}MB",
                size_bytes=size_bytes,
            )

        # Determine file type from extension
        file_type = get_file_type_from_extension(filename)

        # Check if file type is allowed
        if file_type is None:
            return ValidationResult(
                valid=False,
                error_code=ErrorCode.INVALID_FILE_TYPE,
                error_message="Could not determine file type from filename",
                size_bytes=size_bytes,
            )

        if file_type not in self.allowed_types:
            allowed_exts = [ext for ext, ft in EXTENSION_TO_TYPE.items() if ft in self.allowed_types]
            return ValidationResult(
                valid=False,
                file_type=file_type,
                error_code=ErrorCode.INVALID_FILE_TYPE,
                error_message=f"File type not allowed. Allowed types: {', '.join(allowed_exts)}",
                size_bytes=size_bytes,
            )

        # Validate magic bytes
        if self.require_magic_bytes:
            if file_type == FileType.CSV:
                # Special handling for CSV (text-based)
                if not validate_csv_content(content):
                    return ValidationResult(
                        valid=False,
                        file_type=file_type,
                        error_code=ErrorCode.INVALID_MAGIC_BYTES,
                        error_message="File content does not match expected CSV format",
                        size_bytes=size_bytes,
                    )
            else:
                # Binary file validation via magic bytes
                if not check_magic_bytes(content, file_type):
                    return ValidationResult(
                        valid=False,
                        file_type=file_type,
                        error_code=ErrorCode.INVALID_MAGIC_BYTES,
                        error_message=f"File content does not match expected {file_type.value} format",
                        size_bytes=size_bytes,
                    )

        return ValidationResult(
            valid=True,
            file_type=file_type,
            size_bytes=size_bytes,
        )

    def validate_and_raise(
        self,
        content: bytes,
        filename: str | None = None,
    ) -> FileType:
        """
        Validate file upload and raise APIError if invalid.

        Args:
            content: File content
            filename: Original filename

        Returns:
            Detected file type if valid

        Raises:
            APIError: If validation fails
        """
        result = self.validate(content, filename)
        if not result.valid:
            raise APIError(
                code=result.error_code,
                message=result.error_message,
                detail={
                    "filename": filename,
                    "size_bytes": result.size_bytes,
                },
            )
        return result.file_type


class AsyncReadable(Protocol):
    """Protocol for async file-like objects."""

    async def read(self, size: int = -1) -> bytes: ...


async def read_upload_file(
    file_obj: AsyncReadable,
    max_size_bytes: int,
    chunk_size: int = 1024 * 1024,
) -> bytes:
    """
    Read an uploaded file with a hard size limit to prevent memory exhaustion.

    Args:
        file_obj: Async file-like object (e.g., FastAPI UploadFile)
        max_size_bytes: Maximum allowed size in bytes
        chunk_size: Read chunk size in bytes

    Returns:
        Full file contents as bytes

    Raises:
        APIError: If the file exceeds the maximum size
    """
    if max_size_bytes <= 0:
        return await file_obj.read()

    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = await file_obj.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size_bytes:
            raise APIError(
                code=ErrorCode.FILE_TOO_LARGE,
                message=f"File too large. Maximum size is {max_size_bytes // (1024*1024)}MB",
                detail={"size_bytes": total},
            )
        chunks.append(chunk)

    return b"".join(chunks)


# Pre-configured validators for common use cases
def create_pdf_validator(max_size_mb: int = 50) -> UploadValidator:
    """Create a validator for PDF uploads."""
    return UploadValidator(
        allowed_types=[FileType.PDF],
        max_size_bytes=max_size_mb * 1024 * 1024,
    )


def create_aasx_validator(max_size_mb: int = 100) -> UploadValidator:
    """Create a validator for AASX uploads."""
    return UploadValidator(
        allowed_types=[FileType.AASX],
        max_size_bytes=max_size_mb * 1024 * 1024,
    )


def create_spreadsheet_validator(max_size_mb: int = 50) -> UploadValidator:
    """Create a validator for CSV/XLSX uploads."""
    return UploadValidator(
        allowed_types=[FileType.CSV, FileType.XLSX],
        max_size_bytes=max_size_mb * 1024 * 1024,
    )
