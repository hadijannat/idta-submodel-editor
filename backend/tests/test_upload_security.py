"""Tests for upload security utilities."""

import pytest

from app.errors import APIError, ErrorCode
from app.utils.upload_security import (
    FileType,
    UploadValidator,
    ValidationResult,
    check_magic_bytes,
    read_upload_file,
    generate_secure_filename,
    get_file_type_from_extension,
    validate_csv_content,
    create_pdf_validator,
    create_aasx_validator,
    create_spreadsheet_validator,
)


class TestFileTypeDetection:
    """Tests for file type detection from extensions."""

    def test_pdf_extension(self):
        """Test PDF extension detection."""
        assert get_file_type_from_extension("document.pdf") == FileType.PDF
        assert get_file_type_from_extension("Document.PDF") == FileType.PDF

    def test_aasx_extension(self):
        """Test AASX extension detection."""
        assert get_file_type_from_extension("template.aasx") == FileType.AASX
        assert get_file_type_from_extension("TEMPLATE.AASX") == FileType.AASX

    def test_xlsx_extension(self):
        """Test XLSX extension detection."""
        assert get_file_type_from_extension("data.xlsx") == FileType.XLSX
        assert get_file_type_from_extension("data.xls") == FileType.XLSX

    def test_csv_extension(self):
        """Test CSV extension detection."""
        assert get_file_type_from_extension("data.csv") == FileType.CSV

    def test_unknown_extension(self):
        """Test unknown extension returns None."""
        assert get_file_type_from_extension("file.unknown") is None
        assert get_file_type_from_extension("noextension") is None

    def test_none_filename(self):
        """Test None filename returns None."""
        assert get_file_type_from_extension(None) is None

    def test_empty_filename(self):
        """Test empty filename returns None."""
        assert get_file_type_from_extension("") is None


class TestMagicBytesValidation:
    """Tests for magic bytes validation."""

    def test_pdf_magic_bytes(self):
        """Test PDF magic bytes validation."""
        valid_pdf = b"%PDF-1.4 some content"
        invalid_pdf = b"not a pdf file"

        assert check_magic_bytes(valid_pdf, FileType.PDF) is True
        assert check_magic_bytes(invalid_pdf, FileType.PDF) is False

    def test_zip_magic_bytes(self):
        """Test ZIP/AASX/XLSX magic bytes validation."""
        # Standard ZIP signature
        valid_zip = b"PK\x03\x04 rest of file"

        assert check_magic_bytes(valid_zip, FileType.ZIP) is True
        assert check_magic_bytes(valid_zip, FileType.AASX) is True
        assert check_magic_bytes(valid_zip, FileType.XLSX) is True

    def test_invalid_magic_bytes(self):
        """Test rejection of wrong magic bytes."""
        pdf_content = b"%PDF-1.4 content"
        zip_content = b"PK\x03\x04 content"

        # PDF content shouldn't validate as ZIP
        assert check_magic_bytes(pdf_content, FileType.ZIP) is False

        # ZIP content shouldn't validate as PDF
        assert check_magic_bytes(zip_content, FileType.PDF) is False

    def test_csv_has_no_magic_bytes(self):
        """Test that CSV always passes magic bytes check."""
        any_content = b"any content at all"
        assert check_magic_bytes(any_content, FileType.CSV) is True


class TestCsvValidation:
    """Tests for CSV content validation."""

    def test_valid_utf8_csv(self):
        """Test valid UTF-8 CSV content."""
        content = b"name,value\ntest,123\n"
        assert validate_csv_content(content) is True

    def test_valid_csv_with_bom(self):
        """Test CSV with UTF-8 BOM."""
        content = b"\xef\xbb\xbfname,value\ntest,123\n"
        assert validate_csv_content(content) is True

    def test_latin1_csv(self):
        """Test CSV with Latin-1 encoding."""
        content = b"name,value\ncaf\xe9,123\n"  # 'café' in Latin-1
        assert validate_csv_content(content) is True

    def test_binary_content_rejected(self):
        """Test that binary content is rejected."""
        # PDF content
        assert validate_csv_content(b"%PDF-1.4") is False

        # ZIP content
        assert validate_csv_content(b"PK\x03\x04") is False

        # PNG content
        assert validate_csv_content(b"\x89PNG\r\n\x1a\n") is False


class TestUploadValidator:
    """Tests for UploadValidator class."""

    def test_valid_pdf(self):
        """Test validation of valid PDF."""
        validator = UploadValidator(
            allowed_types=[FileType.PDF],
            max_size_bytes=1024 * 1024,  # 1MB
        )
        content = b"%PDF-1.4 some pdf content"
        result = validator.validate(content, "document.pdf")

        assert result.valid is True
        assert result.file_type == FileType.PDF
        assert result.size_bytes == len(content)

    def test_valid_aasx(self):
        """Test validation of valid AASX."""
        validator = UploadValidator(
            allowed_types=[FileType.AASX],
            max_size_bytes=1024 * 1024,
        )
        content = b"PK\x03\x04 aasx content"
        result = validator.validate(content, "template.aasx")

        assert result.valid is True
        assert result.file_type == FileType.AASX

    def test_file_too_large(self):
        """Test rejection of oversized files."""
        validator = UploadValidator(
            allowed_types=[FileType.PDF],
            max_size_bytes=100,  # 100 bytes
        )
        content = b"%PDF-1.4 " + b"x" * 200  # ~200 bytes
        result = validator.validate(content, "document.pdf")

        assert result.valid is False
        assert result.error_code == ErrorCode.FILE_TOO_LARGE

    def test_invalid_file_type(self):
        """Test rejection of disallowed file types."""
        validator = UploadValidator(
            allowed_types=[FileType.PDF],
            max_size_bytes=1024 * 1024,
        )
        content = b"PK\x03\x04 aasx content"
        result = validator.validate(content, "template.aasx")

        assert result.valid is False
        assert result.error_code == ErrorCode.INVALID_FILE_TYPE

    def test_invalid_magic_bytes(self):
        """Test rejection of spoofed extension (wrong magic bytes)."""
        validator = UploadValidator(
            allowed_types=[FileType.PDF],
            max_size_bytes=1024 * 1024,
        )
        # File claims to be PDF but has ZIP magic bytes
        content = b"PK\x03\x04 not actually a pdf"
        result = validator.validate(content, "fake.pdf")

        assert result.valid is False
        assert result.error_code == ErrorCode.INVALID_MAGIC_BYTES

    def test_unknown_extension(self):
        """Test rejection of unknown file extension."""
        validator = UploadValidator(
            allowed_types=[FileType.PDF],
            max_size_bytes=1024 * 1024,
        )
        content = b"%PDF-1.4 content"
        result = validator.validate(content, "file.unknown")

        assert result.valid is False
        assert result.error_code == ErrorCode.INVALID_FILE_TYPE

    def test_no_filename(self):
        """Test rejection when no filename provided."""
        validator = UploadValidator(
            allowed_types=[FileType.PDF],
            max_size_bytes=1024 * 1024,
        )
        content = b"%PDF-1.4 content"
        result = validator.validate(content, None)

        assert result.valid is False
        assert result.error_code == ErrorCode.INVALID_FILE_TYPE

    def test_validate_and_raise_success(self):
        """Test validate_and_raise returns file type on success."""
        validator = UploadValidator(
            allowed_types=[FileType.PDF],
            max_size_bytes=1024 * 1024,
        )
        content = b"%PDF-1.4 content"
        file_type = validator.validate_and_raise(content, "doc.pdf")

        assert file_type == FileType.PDF

    def test_validate_and_raise_failure(self):
        """Test validate_and_raise raises APIError on failure."""
        validator = UploadValidator(
            allowed_types=[FileType.PDF],
            max_size_bytes=100,
        )
        content = b"%PDF-1.4 " + b"x" * 200

        with pytest.raises(APIError) as exc_info:
            validator.validate_and_raise(content, "doc.pdf")

        assert exc_info.value.code == ErrorCode.FILE_TOO_LARGE


class DummyAsyncFile:
    """Simple async file stub for testing chunked reads."""

    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks
        self._index = 0

    async def read(self, size: int = -1) -> bytes:
        if self._index >= len(self._chunks):
            return b""
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


class TestReadUploadFile:
    """Tests for read_upload_file size enforcement."""

    @pytest.mark.asyncio
    async def test_read_within_limit(self):
        file_obj = DummyAsyncFile([b"abc", b"de"])
        data = await read_upload_file(file_obj, max_size_bytes=10, chunk_size=3)
        assert data == b"abcde"

    @pytest.mark.asyncio
    async def test_read_exceeds_limit(self):
        file_obj = DummyAsyncFile([b"a" * 6, b"b" * 6])
        with pytest.raises(APIError) as exc_info:
            await read_upload_file(file_obj, max_size_bytes=10, chunk_size=6)
        assert exc_info.value.code == ErrorCode.FILE_TOO_LARGE


class TestSecureFilename:
    """Tests for secure filename generation."""

    def test_generates_random_filename(self):
        """Test that random filenames are generated."""
        filename1 = generate_secure_filename("original.pdf")
        filename2 = generate_secure_filename("original.pdf")

        # Should be different each time
        assert filename1 != filename2

        # Should end with .pdf
        assert filename1.endswith(".pdf")
        assert filename2.endswith(".pdf")

    def test_preserves_extension(self):
        """Test that extension is preserved."""
        assert generate_secure_filename("file.pdf").endswith(".pdf")
        assert generate_secure_filename("file.aasx").endswith(".aasx")
        assert generate_secure_filename("file.CSV").endswith(".csv")

    def test_no_extension_preservation(self):
        """Test option to not preserve extension."""
        filename = generate_secure_filename("file.pdf", preserve_extension=False)
        assert "." not in filename

    def test_no_original_extension(self):
        """Test handling of filename without extension."""
        filename = generate_secure_filename("noextension")
        assert "." not in filename

    def test_filename_length(self):
        """Test that generated filename has reasonable length."""
        filename = generate_secure_filename("original.pdf")
        # 32 hex chars + 1 dot + 3 extension = 36
        assert len(filename) == 36


class TestFactoryFunctions:
    """Tests for pre-configured validator factory functions."""

    def test_create_pdf_validator(self):
        """Test PDF validator factory."""
        validator = create_pdf_validator(max_size_mb=10)

        # Should accept PDF
        result = validator.validate(b"%PDF-1.4 content", "doc.pdf")
        assert result.valid is True

        # Should reject AASX
        result = validator.validate(b"PK\x03\x04 content", "template.aasx")
        assert result.valid is False

    def test_create_aasx_validator(self):
        """Test AASX validator factory."""
        validator = create_aasx_validator(max_size_mb=10)

        # Should accept AASX
        result = validator.validate(b"PK\x03\x04 content", "template.aasx")
        assert result.valid is True

        # Should reject PDF
        result = validator.validate(b"%PDF-1.4 content", "doc.pdf")
        assert result.valid is False

    def test_create_spreadsheet_validator(self):
        """Test spreadsheet validator factory."""
        validator = create_spreadsheet_validator(max_size_mb=10)

        # Should accept CSV
        result = validator.validate(b"name,value\n", "data.csv")
        assert result.valid is True

        # Should accept XLSX
        result = validator.validate(b"PK\x03\x04 xlsx content", "data.xlsx")
        assert result.valid is True

        # Should reject PDF
        result = validator.validate(b"%PDF-1.4 content", "doc.pdf")
        assert result.valid is False
