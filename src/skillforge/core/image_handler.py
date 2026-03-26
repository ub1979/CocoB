# =============================================================================
'''
    File Name : image_handler.py

    Description : Central image validation, storage, cleanup, and base64
                  encoding. All channels and the router use this module
                  instead of implementing their own image logic.

    Created on 2026-03-19

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team

    Project : SkillForge - AI Assistant with Persistent Memory

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone
'''
# =============================================================================

# =============================================================================
# Import Section
# =============================================================================
import base64
import hashlib
import io
import logging
import os
import re
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

# =============================================================================
# Setup logging
# =============================================================================
logger = logging.getLogger("image_handler")

# =============================================================================
# Constants
# =============================================================================

ALLOWED_MIME_TYPES = {
    "image/png":  [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/gif":  [b"GIF87a", b"GIF89a"],
    "image/webp": [b"RIFF"],          # first 4 bytes; bytes 8-12 == b"WEBP"
    "image/bmp":  [b"BM"],
}

EXTENSION_TO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

MAX_IMAGE_SIZE = 20 * 1024 * 1024          # 20 MB (FR-1.4)
LLM_MAX_SIZE = 4 * 1024 * 1024            # 4 MB — resize above this (NFR-1)
DEFAULT_STORAGE_LIMIT = 1 * 1024**3        # 1 GB (FR-4.2)
SAFE_FILENAME_RE = re.compile(r'[^a-zA-Z0-9_.\-]')


# =============================================================================
'''
    Attachment : Represents a validated, stored image attachment.
'''
# =============================================================================

@dataclass
class Attachment:
    """Represents a validated, stored image attachment."""
    file_path: str
    original_filename: str
    mime_type: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None

    # =========================================================================
    # Function to_dict -> None to dict
    # =========================================================================
    def to_dict(self) -> dict:
        """Serialize for JSONL storage (no base64 -- just references)."""
        return {
            "file_path": self.file_path,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
        }

    # =========================================================================
    # Classmethod from_dict -> dict to Attachment
    # =========================================================================
    @classmethod
    def from_dict(cls, d: dict) -> "Attachment":
        """Deserialize from a dictionary."""
        return cls(
            file_path=d["file_path"],
            original_filename=d["original_filename"],
            mime_type=d["mime_type"],
            size_bytes=d["size_bytes"],
            width=d.get("width"),
            height=d.get("height"),
        )


# =============================================================================
'''
    ImageHandler : Central image validation, storage, cleanup, and
                   base64 encoding.
'''
# =============================================================================

class ImageHandler:
    """Image validation, storage, and encoding."""

    # =========================================================================
    # Function __init__ -> str, int to None
    # =========================================================================
    def __init__(
        self,
        data_dir: Optional[str] = None,
        max_storage_bytes: int = DEFAULT_STORAGE_LIMIT,
    ):
        """
        Initialize the image handler.

        Args:
            data_dir: Root directory for image storage.
                      Defaults to PROJECT_ROOT / "data" / "images".
            max_storage_bytes: Maximum total bytes for stored images (default 1 GB).
        """
        if data_dir is None:
            from skillforge import PROJECT_ROOT
            self.data_dir = PROJECT_ROOT / "data" / "images"
        else:
            self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_storage_bytes = max_storage_bytes
        self._store_counter = 0
        self._store_lock = threading.Lock()

    # =========================================================================
    # Validation
    # =========================================================================

    # =========================================================================
    # Function validate_file -> str to Tuple[bool, str]
    # =========================================================================
    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate an image file.

        Args:
            file_path: Path to the file to validate.

        Returns:
            Tuple of (ok, error_message). error_message is empty on success.
        """
        path = Path(file_path)
        if not path.exists():
            return False, "File does not exist"
        if not path.is_file():
            return False, "Path is not a file"

        size = path.stat().st_size
        if size == 0:
            return False, "File is empty"
        if size > MAX_IMAGE_SIZE:
            return False, f"File too large ({size / 1024 / 1024:.1f} MB, max 20 MB)"

        # Extension check
        ext = path.suffix.lower()
        if ext not in EXTENSION_TO_MIME:
            return False, f"Unsupported format: {ext}"

        # Magic byte check
        expected_mime = EXTENSION_TO_MIME[ext]
        ok, detected_mime = self._check_magic_bytes(path)
        if not ok:
            return False, f"File content does not match {ext} format (magic bytes mismatch)"

        # Extra WEBP check: bytes 8-12 must be b"WEBP"
        if expected_mime == "image/webp":
            try:
                with open(path, "rb") as f:
                    header = f.read(12)
                if len(header) < 12 or header[8:12] != b"WEBP":
                    return False, "Invalid WEBP file (missing WEBP signature)"
            except OSError:
                return False, "Cannot read file for WEBP validation"

        return True, ""

    # =========================================================================
    # Function _check_magic_bytes -> Path to Tuple[bool, Optional[str]]
    # =========================================================================
    def _check_magic_bytes(self, path: Path) -> Tuple[bool, Optional[str]]:
        """
        Check file magic bytes against known signatures.

        Args:
            path: Path to the file.

        Returns:
            Tuple of (matched, detected_mime_type). detected_mime_type is None
            if no match.
        """
        try:
            with open(path, "rb") as f:
                header = f.read(12)
        except OSError:
            return False, None

        for mime, signatures in ALLOWED_MIME_TYPES.items():
            for sig in signatures:
                if header[:len(sig)] == sig:
                    return True, mime
        return False, None

    # =========================================================================
    # Function detect_mime_type -> str to Optional[str]
    # =========================================================================
    def detect_mime_type(self, file_path: str) -> Optional[str]:
        """
        Detect MIME type from magic bytes.

        Args:
            file_path: Path to the file.

        Returns:
            Detected MIME type string, or None if unrecognized.
        """
        _, mime = self._check_magic_bytes(Path(file_path))
        return mime

    # =========================================================================
    # Filename sanitization
    # =========================================================================

    # =========================================================================
    # Function sanitize_filename -> str to str
    # =========================================================================
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename: remove path components, dangerous chars.

        Steps:
            1. Strip directory components (path traversal prevention)
            2. Remove null bytes
            3. Replace unsafe chars with underscore
            4. Prepend 'image' if name starts with '.' or is empty
            5. Truncate to 200 chars preserving extension

        Args:
            filename: Raw filename from user.

        Returns:
            Sanitized filename safe for filesystem use.
        """
        # Strip directory components (path traversal prevention)
        name = Path(filename).name
        # Remove null bytes
        name = name.replace("\x00", "")
        # Replace unsafe chars
        name = SAFE_FILENAME_RE.sub("_", name)
        # Ensure non-empty
        if not name or name.startswith("."):
            name = "image" + name
        # Truncate to 200 chars preserving extension
        if len(name) > 200:
            stem, ext = os.path.splitext(name)
            name = stem[:200 - len(ext)] + ext
        return name

    # =========================================================================
    # Storage
    # =========================================================================

    # =========================================================================
    # Function store_image -> str, str, Optional[str] to Attachment
    # =========================================================================
    def store_image(
        self,
        source_path: str,
        session_key: str,
        original_filename: Optional[str] = None,
    ) -> Attachment:
        """
        Validate and store an image.

        Args:
            source_path: Path to the source image file.
            session_key: Session key for directory organization.
            original_filename: Original filename (for display).
                              Uses source basename if None.

        Returns:
            Attachment dataclass with stored file info.

        Raises:
            ValueError: If validation fails.
        """
        ok, error = self.validate_file(source_path)
        if not ok:
            raise ValueError(f"Image validation failed: {error}")

        src = Path(source_path)
        orig_name = original_filename or src.name
        safe_name = self.sanitize_filename(orig_name)

        # Detect MIME type from actual content
        mime = self.detect_mime_type(source_path) or EXTENSION_TO_MIME.get(
            src.suffix.lower(), "image/png"
        )

        # Sanitize session_key for directory name
        safe_session = SAFE_FILENAME_RE.sub("_", session_key)
        # Truncate long session keys to avoid filesystem path limits;
        # use a hash suffix for uniqueness when truncated.
        if len(safe_session) > 100:
            session_hash = hashlib.md5(session_key.encode()).hexdigest()[:8]
            safe_session = safe_session[:91] + "_" + session_hash

        # Build destination: data/images/{safe_session}/{timestamp}_{safe_name}
        dest_dir = self.data_dir / safe_session
        dest_dir.mkdir(parents=True, exist_ok=True)
        # Use millisecond timestamp + counter to guarantee uniqueness
        with self._store_lock:
            ts = int(time.time() * 1000)
            self._store_counter += 1
            counter = self._store_counter
        dest_file = dest_dir / f"{ts}_{counter}_{safe_name}"

        # Copy file to storage
        shutil.copy2(str(src), str(dest_file))

        size = dest_file.stat().st_size

        return Attachment(
            file_path=str(dest_file),
            original_filename=orig_name,
            mime_type=mime,
            size_bytes=size,
        )

    # =========================================================================
    # Function get_images_for_session -> str to List[Attachment]
    # =========================================================================
    def get_images_for_session(self, session_key: str) -> List[Attachment]:
        """
        List stored images for a session.

        Args:
            session_key: Session key used during storage.

        Returns:
            List of Attachment objects for images in the session directory,
            sorted by filename (timestamp-prefixed, so oldest first).
        """
        safe_session = SAFE_FILENAME_RE.sub("_", session_key)
        session_dir = self.data_dir / safe_session

        if not session_dir.exists():
            return []

        attachments = []
        for f in sorted(session_dir.iterdir()):
            if f.is_file():
                mime = self.detect_mime_type(str(f))
                if mime:
                    attachments.append(Attachment(
                        file_path=str(f),
                        original_filename=f.name,
                        mime_type=mime,
                        size_bytes=f.stat().st_size,
                    ))
        return attachments

    # =========================================================================
    # Base64 encoding (lazy -- only when sending to LLM)
    # =========================================================================

    # =========================================================================
    # Function encode_base64 -> str, int to str
    # =========================================================================
    def encode_base64(self, file_path: str, max_size: int = LLM_MAX_SIZE) -> str:
        """
        Read image and return base64 string. Resize if larger than max_size.

        Args:
            file_path: Path to image file.
            max_size: Max bytes before resizing. Default 4 MB.

        Returns:
            Base64-encoded ASCII string.
        """
        path = Path(file_path)
        data = path.read_bytes()

        if len(data) > max_size:
            data = self._resize_image_bytes(data, max_size)

        return base64.b64encode(data).decode("ascii")

    # =========================================================================
    # Function _resize_image_bytes -> bytes, int to bytes
    # =========================================================================
    def _resize_image_bytes(self, data: bytes, max_size: int) -> bytes:
        """
        Resize image bytes to fit within max_size. Requires Pillow.

        If Pillow is not installed, returns the original data with a warning.

        Args:
            data: Raw image bytes.
            max_size: Target maximum size in bytes.

        Returns:
            Resized image bytes, or original if Pillow is unavailable.
        """
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(data))
            # Iteratively reduce quality/size
            for quality in [85, 70, 50, 30]:
                buf = io.BytesIO()
                fmt = img.format or "JPEG"
                if fmt.upper() == "PNG":
                    # Convert PNG to JPEG for size reduction
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    fmt = "JPEG"
                img.save(buf, format=fmt, quality=quality, optimize=True)
                if buf.tell() <= max_size:
                    return buf.getvalue()

            # If still too large, reduce dimensions
            factor = 0.75
            while factor > 0.1:
                new_size = (int(img.width * factor), int(img.height * factor))
                resized = img.resize(new_size, Image.LANCZOS)
                buf = io.BytesIO()
                resized.save(buf, format="JPEG", quality=70, optimize=True)
                if buf.tell() <= max_size:
                    return buf.getvalue()
                factor -= 0.15

            # Last resort: return as-is
            return data

        except ImportError:
            logger.warning(
                "Pillow not installed -- cannot resize image. Sending full size."
            )
            return data

    # =========================================================================
    # Cleanup (oldest-first eviction)
    # =========================================================================

    # =========================================================================
    # Function get_storage_usage -> None to int
    # =========================================================================
    def get_storage_usage(self) -> int:
        """
        Get total bytes used by stored images.

        Returns:
            Total bytes of all files under the data directory.
        """
        total = 0
        for f in self.data_dir.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
        return total

    # =========================================================================
    # Function cleanup_if_needed -> None to None
    # =========================================================================
    def cleanup_if_needed(self) -> None:
        """
        Evict oldest images if storage exceeds limit.

        Collects all image files sorted by modification time (oldest first),
        then deletes files until total usage drops below max_storage_bytes.
        """
        usage = self.get_storage_usage()
        if usage <= self.max_storage_bytes:
            return

        # Collect all image files sorted oldest-first
        files = []
        for f in self.data_dir.rglob("*"):
            if f.is_file():
                files.append((f.stat().st_mtime, f))
        files.sort(key=lambda x: x[0])  # oldest first

        # Delete until under limit
        for mtime, f in files:
            if usage <= self.max_storage_bytes:
                break
            size = f.stat().st_size
            try:
                f.unlink()
                usage -= size
                logger.info(f"Evicted old image: {f.name} ({size} bytes)")
            except OSError:
                pass


# =============================================================================
# Convenience function
# =============================================================================

def create_image_handler(
    data_dir: Optional[str] = None,
    max_storage_bytes: int = DEFAULT_STORAGE_LIMIT,
) -> ImageHandler:
    """Create an image handler with the given configuration."""
    return ImageHandler(data_dir=data_dir, max_storage_bytes=max_storage_bytes)


# =============================================================================
'''
    End of File : image_handler.py

    Project : SkillForge - AI Assistant with Persistent Memory

    License : Open Source - Safe Open Community Project

    Mission : Making AI Useful for Everyone

    Done by : Syed Usama Bukhari & Idrak AI Ltd Team
'''
# =============================================================================
