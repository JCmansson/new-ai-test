# utils/path_helpers.py
"""
Enhanced path management with type safety and validation.

Provides centralized path management with:
- Type-safe category constants and literals
- Memory-efficient frozen dataclass with __slots__
- Path validation and existence checking
- Cleanup utilities
- Size calculation helpers
- No fuzzy matching - fail fast on errors
"""

import os
import shutil
from pathlib import Path
from functools import lru_cache
from dataclasses import dataclass
from typing import Optional, Set, List, Tuple, Union, Dict, Literal
from datetime import datetime, timedelta

# Type-safe category literal for IDE support
CategoryType = Literal[
    'config', 'data', 'files', 'generated_payloads',
    'logs', 'output', 'payloads', 'schemas', 'tmp', 'wsdl'
]


class Dir:
    """
    Directory category constants to prevent typos.

    Use these constants instead of strings for type safety:
        Dir.CONFIG instead of 'config'
        Dir.OUTPUT instead of 'output'
    """
    CONFIG: CategoryType = 'config'
    DATA: CategoryType = 'data'
    FILES: CategoryType = 'files'
    GENERATED_PAYLOADS: CategoryType = 'generated_payloads'
    LOGS: CategoryType = 'logs'
    OUTPUT: CategoryType = 'output'
    PAYLOADS: CategoryType = 'payloads'
    SCHEMAS: CategoryType = 'schemas'
    TMP: CategoryType = 'tmp'
    WSDL: CategoryType = 'wsdl'

    @classmethod
    def all(cls) -> Set[CategoryType]:
        """Get all valid categories."""
        return {
            cls.CONFIG, cls.DATA, cls.FILES, cls.GENERATED_PAYLOADS,
            cls.LOGS, cls.OUTPUT, cls.PAYLOADS, cls.SCHEMAS,
            cls.TMP, cls.WSDL
        }

    @classmethod
    def validate(cls, category: str) -> bool:
        """Check if a category is valid."""
        return category in cls.all()


@dataclass(frozen=True)
class ProjectPaths:
    """
    Container for all project paths. Frozen to prevent accidental modification.

    This class provides standardized access to project directory paths.
    The root path can be set in three ways (in order of precedence):
    1. Explicitly passed to init()
    2. Through the PROJECT_ROOT environment variable
    3. Derived automatically from the location of this file
    """
    __slots__ = [
        'root', 'config', 'data', 'files', 'generated_payloads',
        'logs', 'output', 'payloads', 'schemas', 'tmp', 'wsdl'
    ]

    root: Path
    config: Path
    data: Path
    files: Path
    generated_payloads: Path
    logs: Path
    output: Path
    payloads: Path
    schemas: Path
    tmp: Path
    wsdl: Path

    @classmethod
    @lru_cache(maxsize=1)
    def init(cls, root_path: Optional[Path] = None) -> 'ProjectPaths':
        """
        Get singleton instance with cached paths.

        Args:
            root_path: Explicit root directory path. If None, defaults to the parent
                      of the directory containing this file, or uses PROJECT_ROOT env var

        Returns:
            ProjectPaths instance with all project directory paths configured

        Raises:
            ValueError: If the root_path (explicit or derived) is not a valid directory
        """
        # Use provided root_path, or fallback to env var, or compute from __file__
        if root_path is None:
            env_root = os.getenv("PROJECT_ROOT")
            if env_root:
                root_path = Path(env_root)
            else:
                root_path = Path(__file__).resolve().parent.parent

        # Validate root_path
        if not root_path.is_dir():
            raise ValueError(f"Invalid root path: {root_path} is not a directory")

        return cls(
            root=root_path,
            config=root_path / "config",
            data=root_path / "data",
            files=root_path / "files",
            generated_payloads=root_path / "generated_payloads",
            logs=root_path / "logs",
            output=root_path / "output",
            payloads=root_path / "payloads",
            schemas=root_path / "schemas",
            tmp=root_path / "tmp",
            wsdl=root_path / "wsdl"
        )

    def ensure_dirs(self, skip_dirs: Optional[Set[str]] = None) -> List[str]:
        """
        Create all project directories if they don't exist.

        Args:
            skip_dirs: Set of directory names to skip creating

        Returns:
            List of directory names that were created

        Raises:
            OSError: If directory creation fails due to permissions
        """
        skip_dirs = skip_dirs or set()
        created_dirs = []

        for attr_name in self.__slots__:
            if attr_name == 'root' or attr_name in skip_dirs:
                continue

            path = getattr(self, attr_name)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    created_dirs.append(attr_name)
                except OSError as e:
                    raise OSError(f"Failed to create directory {path}: {e}")

        return created_dirs

    def validate_structure(self) -> Tuple[List[str], List[str]]:
        """
        Validate that all expected directories exist.

        Returns:
            Tuple of (existing_dirs, missing_dirs)
        """
        existing = []
        missing = []

        for attr_name in self.__slots__:
            if attr_name == 'root':
                continue

            path = getattr(self, attr_name)
            if path.exists():
                existing.append(attr_name)
            else:
                missing.append(attr_name)

        return existing, missing

    def get_dir_sizes(self) -> Dict[str, int]:
        """
        Get the size of each directory in bytes.

        Returns:
            Dictionary mapping directory names to sizes in bytes
        """
        sizes = {}

        for attr_name in self.__slots__:
            path = getattr(self, attr_name)
            if path.exists() and path.is_dir():
                size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
                sizes[attr_name] = size

        return sizes


def get_path(category: CategoryType, filename: str, ensure_parent: bool = True) -> Path:
    """
    Get the full path for a file in a specified category directory.

    Args:
        category: Directory category - must be exact match from Categories constants
                  (e.g., Categories.CONFIG, Categories.OUTPUT)
        filename: Target filename (e.g., "config.json")
        ensure_parent: If True, create the parent directory if it doesn't exist

    Returns:
        The full path to the file

    Raises:
        ValueError: If the category is not a valid CategoryType
        OSError: If directory creation fails when ensure_parent is True

    Example:
        > from utils.path_helpers import get_path, Categories
        > config_path = get_path(Categories.CONFIG, 'app-config.json')
        > log_path = get_path(Categories.LOGS, 'app.log')
    """
    paths = ProjectPaths.init()

    # Hard fail on invalid category - no fuzzy matching
    if not Dir.validate(category):
        raise ValueError(
            f"Invalid category '{category}'. "
            f"Must be exactly one of: {', '.join(sorted(Dir.all()))}\n"
            f"Use Categories.* constants for type safety (e.g., Categories.CONFIG)"
        )

    # Convert hyphenated categories to underscored attributes
    attr_name = category.replace('-', '_')
    path = getattr(paths, attr_name) / filename

    if ensure_parent:
        try:
            path.parent.mkdir(exist_ok=True, parents=True)
        except OSError as e:
            raise OSError(f"Cannot create parent directory for {path}: {e}")

    return path


def set_project_root(path: Union[str, Path]) -> None:
    """
    Set the project root path for the application.

    Args:
        path: The path to set as the project root

    Raises:
        ValueError: If the path doesn't exist or isn't a directory

    Example:
        > set_project_root('/path/to/project')
        > config_file = get_path(Categories.CONFIG, 'settings.json')
    """
    root_path = Path(path) if isinstance(path, str) else path

    if not root_path.exists():
        raise ValueError(f"Project root does not exist: {root_path}")

    if not root_path.is_dir():
        raise ValueError(f"Project root must be a directory, not a file: {root_path}")

    # Clear the lru_cache to force reinitialization with the new path
    ProjectPaths.init.cache_clear()

    # Initialize with the new path
    ProjectPaths.init(root_path)


def get_project_root() -> Path:
    """
    Get the current project root path.

    Returns:
        The project root Path
    """
    return ProjectPaths.init().root


def setup_import_path() -> None:
    """
    Setup Python import path for scripts running from subdirectories.

    Automatically adds project root to sys.path if not already present.
    Safe to call multiple times.

    Usage:
        > # At top of script in src/ or other subdirectory
        > from utils.path_helpers import setup_import_path
        > setup_import_path()
    """
    import sys

    project_root = get_project_root()
    project_root_str = str(project_root)

    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


def cleanup_old_files(category: CategoryType, days: int = 30,
                      pattern: str = "*", dry_run: bool = False) -> List[Path]:
    """
    Clean up old files from a category directory.

    Args:
        category: Directory category to clean (use Categories.*)
        days: Delete files older than this many days
        pattern: File pattern to match (default: "*")
        dry_run: If True, only report what would be deleted

    Returns:
        List of deleted (or would-be deleted) file paths

    Raises:
        ValueError: If category is invalid

    Example:
        > # Delete logs older than 7 days
        > deleted = cleanup_old_files(Categories.LOGS, days=7, pattern="*.log")
    """
    if not Dir.validate(category):
        raise ValueError(f"Invalid category: {category}. Use Categories.* constants")

    paths = ProjectPaths.init()
    attr_name = category.replace('-', '_')
    directory = getattr(paths, attr_name)

    if not directory.exists():
        return []

    cutoff_time = datetime.now() - timedelta(days=days)
    deleted_files = []

    for file_path in directory.glob(pattern):
        if file_path.is_file():
            file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_mtime < cutoff_time:
                deleted_files.append(file_path)
                if not dry_run:
                    try:
                        file_path.unlink()
                    except OSError as e:
                        # Continue processing other files
                        pass

    return deleted_files


def cleanup_tmp(max_age_hours: int = 24) -> int:
    """
    Clean up temporary files older than specified hours.

    Args:
        max_age_hours: Maximum age of tmp files in hours

    Returns:
        Number of files deleted
    """
    paths = ProjectPaths.init()
    tmp_dir = paths.tmp

    if not tmp_dir.exists():
        return 0

    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    deleted_count = 0

    for item in tmp_dir.iterdir():
        try:
            item_mtime = datetime.fromtimestamp(item.stat().st_mtime)
            if item_mtime < cutoff_time:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
                deleted_count += 1
        except OSError as e:
            # Continue with other items
            pass

    return deleted_count


def format_size(size_bytes: int) -> str:
    """
    Format bytes as human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def get_dir_size(category: CategoryType, human_readable: bool = True) -> Union[str, int]:
    """
    Get the total size of a category directory.

    Args:
        category: Directory category (use Categories.*)
        human_readable: If True, return formatted string, else bytes

    Returns:
        Directory size as formatted string or integer bytes

    Raises:
        ValueError: If category is invalid

    Example:
        > size = get_dir_size(Categories.OUTPUT, human_readable=True)
        > print(f"Output directory size: {size}")
    """
    if not Dir.validate(category):
        raise ValueError(f"Invalid category: {category}. Use Categories.* constants")

    paths = ProjectPaths.init()
    attr_name = category.replace('-', '_')
    directory = getattr(paths, attr_name)

    if not directory.exists():
        return "0 B" if human_readable else 0

    total_size = sum(f.stat().st_size for f in directory.rglob('*') if f.is_file())

    if not human_readable:
        return total_size

    return format_size(total_size)


def list_files(category: CategoryType, pattern: str = "*",
               recursive: bool = False) -> List[Path]:
    """
    List files in a category directory.

    Args:
        category: Directory category (use Categories.*)
        pattern: File pattern to match
        recursive: If True, search recursively

    Returns:
        List of file paths matching the pattern

    Raises:
        ValueError: If category is invalid

    Example:
        > json_files = list_files(Categories.CONFIG, pattern="*.json")
    """
    if not Dir.validate(category):
        raise ValueError(f"Invalid category: {category}. Use Categories.* constants")

    paths = ProjectPaths.init()
    attr_name = category.replace('-', '_')
    directory = getattr(paths, attr_name)

    if not directory.exists():
        return []

    if recursive:
        files = [f for f in directory.rglob(pattern) if f.is_file()]
    else:
        files = [f for f in directory.glob(pattern) if f.is_file()]

    return sorted(files)


def ensure_file_backup(category: CategoryType, filename: str,
                       max_backups: int = 5) -> Optional[Path]:
    """
    Create a backup of a file before overwriting it.

    Args:
        category: Directory category (use Categories.*)
        filename: File to backup
        max_backups: Maximum number of backups to keep

    Returns:
        Path to backup file if created, None if file doesn't exist

    Raises:
        ValueError: If category is invalid
        OSError: If backup creation fails

    Example:
        > backup_path = ensure_file_backup(Categories.CONFIG, 'settings.json')
    """
    if not Dir.validate(category):
        raise ValueError(f"Invalid category: {category}. Use Categories.* constants")

    original_path = get_path(category, filename, ensure_parent=False)

    if not original_path.exists():
        return None

    # Create backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{original_path.stem}_backup_{timestamp}{original_path.suffix}"
    backup_path = original_path.parent / backup_name

    # Copy file to backup
    try:
        shutil.copy2(original_path, backup_path)

        # Clean up old backups
        backup_pattern = f"{original_path.stem}_backup_*{original_path.suffix}"
        backups = sorted(original_path.parent.glob(backup_pattern))

        if len(backups) > max_backups:
            for old_backup in backups[:-max_backups]:
                old_backup.unlink()

        return backup_path

    except OSError as e:
        raise OSError(f"Failed to create backup of {original_path}: {e}")