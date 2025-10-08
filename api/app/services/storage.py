"""
Storage abstraction layer for optimized data files
Supports local filesystem and R2/S3
"""
from pathlib import Path
from typing import Optional
from ..config import settings


class StorageError(Exception):
    """Error accessing storage"""
    pass


def _local_read(key: str) -> bytes:
    """
    Read file from local filesystem

    Args:
        key: Path relative to LOCAL_DATA_ROOT (e.g., "tenants/uuid/accounts/act_123/meta_v1.json")

    Returns:
        File contents as bytes

    Raises:
        StorageError: If file not found or not readable
    """
    base = Path(settings.LOCAL_DATA_ROOT)
    file_path = base / key

    # Security: prevent directory traversal
    try:
        file_path = file_path.resolve()
        base = base.resolve()
        if not str(file_path).startswith(str(base)):
            raise StorageError("Invalid file path (directory traversal attempt)")
    except Exception as e:
        raise StorageError(f"Invalid file path: {e}")

    if not file_path.exists():
        raise StorageError(f"File not found: {key}")

    if not file_path.is_file():
        raise StorageError(f"Not a file: {key}")

    try:
        return file_path.read_bytes()
    except Exception as e:
        raise StorageError(f"Failed to read file: {e}")


def _local_write(key: str, data: bytes) -> None:
    """
    Write file to local filesystem

    Args:
        key: Path relative to LOCAL_DATA_ROOT
        data: File contents as bytes
    """
    base = Path(settings.LOCAL_DATA_ROOT)
    file_path = base / key

    # Security: prevent directory traversal
    try:
        file_path = file_path.resolve()
        base = base.resolve()
        if not str(file_path).startswith(str(base)):
            raise StorageError("Invalid file path (directory traversal attempt)")
    except Exception as e:
        raise StorageError(f"Invalid file path: {e}")

    # Create parent directories
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        file_path.write_bytes(data)
    except Exception as e:
        raise StorageError(f"Failed to write file: {e}")


def get_object(key: str) -> bytes:
    """
    Get object from storage

    Args:
        key: Storage key (e.g., "tenants/uuid/accounts/act_123/meta_v1.json")

    Returns:
        Object contents as bytes

    Raises:
        StorageError: If object not found or error occurred
    """
    if settings.STORAGE_MODE == "local":
        return _local_read(key)
    elif settings.STORAGE_MODE == "r2":
        # TODO: Implement R2/S3 client
        raise NotImplementedError("R2/S3 storage not yet implemented")
    else:
        raise StorageError(f"Unknown storage mode: {settings.STORAGE_MODE}")


def put_object(key: str, data: bytes) -> None:
    """
    Put object to storage

    Args:
        key: Storage key
        data: Object contents as bytes

    Raises:
        StorageError: If write failed
    """
    if settings.STORAGE_MODE == "local":
        _local_write(key, data)
    elif settings.STORAGE_MODE == "r2":
        # TODO: Implement R2/S3 client
        raise NotImplementedError("R2/S3 storage not yet implemented")
    else:
        raise StorageError(f"Unknown storage mode: {settings.STORAGE_MODE}")


def object_exists(key: str) -> bool:
    """
    Check if object exists in storage

    Args:
        key: Storage key

    Returns:
        True if exists, False otherwise
    """
    if settings.STORAGE_MODE == "local":
        base = Path(settings.LOCAL_DATA_ROOT)
        file_path = base / key
        try:
            file_path = file_path.resolve()
            base = base.resolve()
            if not str(file_path).startswith(str(base)):
                return False
        except:
            return False
        return file_path.exists() and file_path.is_file()
    elif settings.STORAGE_MODE == "r2":
        # TODO: Implement R2/S3 client
        raise NotImplementedError("R2/S3 storage not yet implemented")
    else:
        return False
