# utils/load_n_save.py
"""
Enhanced data handler with specialized methods and type safety.

Provides efficient file I/O with:
- Thread-safe lazy loading of heavy dependencies
- Type-safe category usage with validation
- Specialized methods for each file type
- Smart dispatcher for automatic routing
- Format detection and validation
- Comprehensive error handling
"""

import json
import gzip
import threading
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Union, Dict, Any, Optional, List, Literal

from utils.logger import setup_logger
from utils.path_helpers import CategoryType, get_path, format_size
from utils.exceptions import FileOperationError, ValidationError

# Hard-fail imports - TXO requires properly configured environment
import pandas as pd
import yaml
import openpyxl  # Used by pandas for Excel operations (engine='openpyxl')

logger = setup_logger()

# File format detection types
FileFormat = Literal['json', 'text', 'csv', 'excel', 'yaml', 'binary', 'gzip', 'unknown']


class DecimalEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles Decimal objects.

    Converts Decimal to float for JSON serialization.
    """

    def default(self, obj):
        """Convert Decimal to float, pass others to the default encoder."""
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class TxoDataHandler:
    """
    Data I/O handler with specialized methods and type safety.

    Features:
    - Thread-safe lazy loading of heavy dependencies
    - Type-safe category usage
    - Specialized save/load methods for each format
    - Smart routing with format detection
    - Comprehensive error handling with fail-fast approach
    """

    # Thread safety for file operations
    _file_lock = threading.Lock()

    # Configuration constants
    DEFAULT_ENCODING = 'utf-8'
    DEFAULT_JSON_INDENT = 2
    DEFAULT_COMPRESSION_LEVEL = 9
    DEFAULT_CSV_DELIMITER = ','
    DEFAULT_SHEET_NAME = 'Sheet1'

    @staticmethod
    def get_utc_timestamp() -> str:
        """
        Get current UTC timestamp in TXO standard format.

        Returns:
            Timestamp string in format: 2025-01-25T143045Z

        Example:
            > TxoDataHandler.get_utc_timestamp()
            '2025-01-25T143045Z'
        """
        utc_now = datetime.now(timezone.utc)
        return utc_now.strftime("%Y-%m-%dT%H%M%SZ")

    @staticmethod
    def save_with_timestamp(data: Any, directory: CategoryType, filename: str,
                           add_timestamp: bool = False, **kwargs) -> Path:
        """
        Save file with optional UTC timestamp suffix.

        Args:
            data: Data to save
            directory: Target directory category
            filename: Base filename
            add_timestamp: Whether to add UTC timestamp (default: False)
            **kwargs: Additional arguments passed to save method

        Returns:
            Path to saved file

        Example:
            > # Without timestamp
            > path = data_handler.save_with_timestamp(data, Dir.OUTPUT, "report.json")
            > # Saves as: report.json

            > # With timestamp
            > path = data_handler.save_with_timestamp(data, Dir.OUTPUT, "report.json", add_timestamp=True)
            > # Saves as: report_2025-01-25T143045Z.json
        """
        if add_timestamp:
            timestamp = TxoDataHandler.get_utc_timestamp()

            # Insert timestamp before file extension
            if '.' in filename:
                name_parts = filename.rsplit('.', 1)
                timestamped_filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
            else:
                timestamped_filename = f"{filename}_{timestamp}"

            logger.debug(f"Adding UTC timestamp to filename: {filename} -> {timestamped_filename}")
            filename = timestamped_filename

        return TxoDataHandler.save(data, directory, filename, **kwargs)

    # Format detection mappings
    FORMAT_EXTENSIONS = {
        '.json': 'json',
        '.txt': 'text', '.log': 'text', '.md': 'text',
        '.html': 'text', '.xml': 'text', '.py': 'text',
        '.csv': 'csv', '.tsv': 'csv',
        '.xlsx': 'excel', '.xls': 'excel', '.xlsm': 'excel',
        '.yaml': 'yaml', '.yml': 'yaml',
        '.gz': 'gzip', '.rapidstart': 'gzip',
        '.bin': 'binary', '.dat': 'binary', '.pkl': 'binary'
    }

    # ==================== Format Detection ====================

    @staticmethod
    def detect_format(filename: str) -> FileFormat:
        """
        Detect file format from extension.

        Args:
            filename: Filename with extension

        Returns:
            Detected FileFormat
        """
        ext = Path(filename).suffix.lower()
        return TxoDataHandler.FORMAT_EXTENSIONS.get(ext, 'unknown')

    @staticmethod
    def validate_format(data: Any, filename: str, strict: bool = True) -> bool:
        """
        Validate that data type matches file extension.

        Args:
            data: Data to validate
            filename: Target filename
            strict: If True, raise exception on mismatch

        Returns:
            True if valid, False if not (when strict=False)

        Raises:
            ValidationError: If validation fails and strict=True
        """
        detected = TxoDataHandler.detect_format(filename)
        data_type = type(data).__name__

        valid = True
        error_msg = None

        if isinstance(data, str):
            if detected not in ('text', 'json', 'yaml'):
                valid = False
                error_msg = f"{data_type} data cannot be saved to {detected} format"
        elif isinstance(data, bytes):
            if detected not in ('binary', 'gzip'):
                valid = False
                error_msg = f"{data_type} data cannot be saved to {detected} format"
        elif isinstance(data, (dict, list)):
            if detected not in ('json', 'yaml'):
                valid = False
                error_msg = f"{data_type} data should be saved as json/yaml, not {detected}"
        elif hasattr(data, 'to_csv') and hasattr(data, 'to_excel'):
            if detected not in ('csv', 'excel'):
                valid = False
                error_msg = f"{data_type} should be saved as csv/excel, not {detected}"
        elif detected == 'unknown':
            valid = False
            error_msg = f"Unknown file format for extension: {Path(filename).suffix} (data type: {data_type})"

        if not valid:
            if strict:
                raise ValidationError(
                    f"Format validation failed: {error_msg}",
                    field='filename',
                    value=filename
                )
            else:
                logger.warning(f"Format validation: {error_msg}")

        return valid

    @staticmethod
    def suggest_extension(data: Any) -> str:
        """
        Suggest appropriate file extension based on data type.

        Args:
            data: Data to analyze

        Returns:
            Suggested extension with dot (e.g., '.json')
        """
        if isinstance(data, str):
            return '.txt'
        elif isinstance(data, bytes):
            return '.bin'
        elif isinstance(data, (dict, list)):
            return '.json'
        elif hasattr(data, 'to_csv'):
            return '.csv'
        elif hasattr(data, 'save'):
            return '.xlsx'
        return '.dat'

    # ==================== Main Load Dispatcher ====================

    @staticmethod
    def load(directory: CategoryType, filename: str, **kwargs) -> Any:
        """
        Smart load method that auto-detects format and routes to specialized loader.

        Args:
            directory: Target directory (use Categories.*)
            filename: Filename to load
            **kwargs: Format-specific options passed to specialized loader

        Returns:
            Loaded data in appropriate format

        Raises:
            FileNotFoundError: If file doesn't exist
            ValidationError: If file format is unknown
            Various format-specific exceptions
        """
        # Validate file exists
        file_path = get_path(directory, filename, ensure_parent=False)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filename} in {directory}")

        # Detect format and route
        file_format = TxoDataHandler.detect_format(filename)

        if file_format == 'json':
            return TxoDataHandler.load_json(directory, filename)
        elif file_format == 'text':
            return TxoDataHandler.load_text(directory, filename, **kwargs)
        elif file_format == 'csv':
            return TxoDataHandler.load_csv(directory, filename, **kwargs)
        elif file_format == 'excel':
            return TxoDataHandler.load_excel(directory, filename, **kwargs)
        elif file_format == 'yaml':
            return TxoDataHandler.load_yaml(directory, filename)
        elif file_format == 'gzip':
            return TxoDataHandler.load_gzip(directory, filename)
        elif file_format == 'binary':
            return TxoDataHandler.load_binary(directory, filename)
        else:
            raise ValidationError(
                f"Unknown file format for {filename}. "
                f"Extension '{Path(filename).suffix}' not recognized",
                field='filename'
            )

    # ==================== Main Save Dispatcher ====================

    @staticmethod
    def save(data: Any, directory: CategoryType, filename: str, **kwargs) -> Path:
        """
        Smart save method that auto-routes to specialized saver based on data type.

        Args:
            data: Data to save (auto-detects type)
            directory: Target directory (use Categories.*)
            filename: Target filename with extension
            **kwargs: Format-specific options passed to specialized saver

        Returns:
            Path to saved file

        Raises:
            TypeError: Unsupported data type
            ValidationError: Data type doesn't match extension
        """
        # Validate format matches data
        TxoDataHandler.validate_format(data, filename, strict=True)

        # Route to specialized method based on data type
        if isinstance(data, str):
            return TxoDataHandler.save_text(data, directory, filename, **kwargs)
        elif isinstance(data, bytes):
            format_type = TxoDataHandler.detect_format(filename)
            if format_type == 'gzip':
                return TxoDataHandler.save_gzip(data, directory, filename, **kwargs)
            else:
                return TxoDataHandler.save_binary(data, directory, filename)
        elif isinstance(data, (dict, list)):
            format_type = TxoDataHandler.detect_format(filename)
            if format_type == 'yaml':
                return TxoDataHandler.save_yaml(data, directory, filename, **kwargs)
            else:
                return TxoDataHandler.save_json(data, directory, filename, **kwargs)
        elif hasattr(data, 'to_csv') and hasattr(data, 'to_excel'):
            return TxoDataHandler._save_dataframe(data, directory, filename, **kwargs)
        elif hasattr(data, 'save') and callable(data.save):
            return TxoDataHandler._save_workbook(data, directory, filename)
        else:
            raise TypeError(
                f"Unsupported data type: {type(data).__name__}. "
                f"Supported types: str, bytes, dict, list, DataFrame, Workbook. "
                f"Suggested extension: {TxoDataHandler.suggest_extension(data)}"
            )

    # ==================== Specialized Load Methods ====================

    @staticmethod
    def load_json(directory: CategoryType, filename: str) -> Union[Dict[str, Any], list]:
        """
        Load JSON file with proper error handling.

        Args:
            directory: Source directory (use Categories.*)
            filename: JSON filename

        Returns:
            Parsed JSON data (dict or list)

        Raises:
            FileOperationError: If file cannot be read
            ValidationError: If JSON is invalid
        """
        file_path = get_path(directory, filename, ensure_parent=False)
        logger.debug(f"Loading JSON from {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Loaded JSON from {file_path} ({file_path.stat().st_size:,} bytes)")
                return data
        except FileNotFoundError:
            raise FileOperationError(
                f"JSON file not found: {filename}",
                file_path=str(file_path),
                operation='load'
            )
        except json.JSONDecodeError as e:
            raise ValidationError(
                f"Invalid JSON in {filename}: {e}",
                field='json_content'
            )
        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to read JSON file: {e}",
                file_path=str(file_path),
                operation='load'
            )

    @staticmethod
    def load_text(directory: CategoryType, filename: str,
                  encoding: Optional[str] = None) -> str:
        """
        Load text file with specified encoding.

        Args:
            directory: Source directory (use Categories.*)
            filename: Text filename
            encoding: Text encoding (default: UTF-8)

        Returns:
            File content as string

        Raises:
            FileOperationError: If file cannot be read
            UnicodeDecodeError: If encoding is incorrect
        """
        encoding = encoding or TxoDataHandler.DEFAULT_ENCODING
        file_path = get_path(directory, filename, ensure_parent=False)
        logger.debug(f"Loading text file from {file_path} with {encoding} encoding")

        try:
            content = file_path.read_text(encoding=encoding)
            logger.info(f"Loaded text from {file_path} ({len(content):,} chars)")
            return content
        except FileNotFoundError:
            raise FileOperationError(
                f"Text file not found: {filename}",
                file_path=str(file_path),
                operation='load'
            )
        except UnicodeDecodeError as e:
            raise UnicodeDecodeError(
                e.encoding, e.object, e.start, e.end,
                f"Cannot decode {filename} with {encoding} encoding. Try different encoding."
            )
        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to read text file: {e}",
                file_path=str(file_path),
                operation='load'
            )

    @staticmethod
    def load_yaml(directory: CategoryType, filename: str) -> Union[Dict[str, Any], list, Any]:
        """
        Load YAML file with lazy import.

        Args:
            directory: Source directory (use Categories.*)
            filename: YAML filename

        Returns:
            Parsed YAML data

        Raises:
            FileOperationError: If file cannot be read
            ValidationError: If YAML is invalid
        """
        # Direct import - hard-fail if not available
        file_path = get_path(directory, filename, ensure_parent=False)
        logger.debug(f"Loading YAML from {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                logger.info(f"Loaded YAML from {file_path}")
                return data
        except FileNotFoundError:
            raise FileOperationError(
                f"YAML file not found: {filename}",
                file_path=str(file_path),
                operation='load'
            )
        except yaml.YAMLError as e:
            raise ValidationError(
                f"Invalid YAML in {filename}: {e}",
                field='yaml_content'
            )
        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to read YAML file: {e}",
                file_path=str(file_path),
                operation='load'
            )

    @staticmethod
    def load_csv(directory: CategoryType, filename: str,
                 delimiter: Optional[str] = None,
                 encoding: Optional[str] = None,
                 usecols: Optional[List[str]] = None,
                 nrows: Optional[int] = None,
                 chunksize: Optional[int] = None) -> Union['pd.DataFrame', Any]:
        """
        Load CSV file with memory-efficient options.

        Args:
            directory: Source directory (use Categories.*)
            filename: CSV filename
            delimiter: Column delimiter (default: comma)
            encoding: File encoding (default: UTF-8)
            usecols: Columns to load (for memory efficiency)
            nrows: Number of rows to read
            chunksize: Return iterator for processing large files in chunks

        Returns:
            DataFrame or iterator if chunksize is specified

        Raises:
            FileOperationError: If file cannot be read
        """
        # Direct import - hard-fail if not available

        delimiter = delimiter or TxoDataHandler.DEFAULT_CSV_DELIMITER
        encoding = encoding or TxoDataHandler.DEFAULT_ENCODING

        file_path = get_path(directory, filename, ensure_parent=False)
        logger.debug(f"Loading CSV from {file_path}")

        try:
            df = pd.read_csv(
                file_path,
                encoding=encoding,
                delimiter=delimiter,
                usecols=usecols,
                nrows=nrows,
                chunksize=chunksize
            )

            if chunksize:
                logger.info(f"Loading CSV {file_path} in chunks of {chunksize}")
                logger.info(f"Returned TextFileReader for chunked processing")
            else:
                logger.info(f"Loaded CSV from {file_path}")

            return df

        except FileNotFoundError:
            raise FileOperationError(
                f"CSV file not found: {filename}",
                file_path=str(file_path),
                operation='load'
            )
        except (OSError, IOError, pd.errors.ParserError) as e:
            raise FileOperationError(
                f"Failed to load CSV file: {e}",
                file_path=str(file_path),
                operation='load'
            )

    @staticmethod
    def load_excel(directory: CategoryType, filename: str,
                   sheet_name: Union[str, int] = 0,
                   skiprows: int = 0,
                   usecols: Optional[List[str]] = None,
                   nrows: Optional[int] = None) -> 'pd.DataFrame':
        """
        Load Excel file with memory-efficient options.

        Args:
            directory: Source directory (use Categories.*)
            filename: Excel filename
            sheet_name: Sheet to load (name or index, default: 0)
            skiprows: Rows to skip from beginning
            usecols: Columns to load (for memory efficiency)
            nrows: Number of rows to read

        Returns:
            DataFrame with Excel data

        Raises:
            FileOperationError: If file cannot be read
            ValidationError: If sheet doesn't exist
        """
        # Direct import - hard-fail if not available
        # openpyxl available via direct import

        file_path = get_path(directory, filename, ensure_parent=False)
        logger.debug(f"Loading Excel from {file_path} (sheet: {sheet_name})")

        try:
            df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                skiprows=skiprows,
                usecols=usecols,
                nrows=nrows,
                engine='openpyxl'
            )
            logger.info(f"Loaded Excel from {file_path} ({len(df):,} rows)")
            return df

        except FileNotFoundError:
            raise FileOperationError(
                f"Excel file not found: {filename}",
                file_path=str(file_path),
                operation='load'
            )
        except ValueError as e:
            if 'Worksheet' in str(e):
                raise ValidationError(
                    f"Sheet '{sheet_name}' not found in {filename}",
                    field='sheet_name',
                    value=sheet_name
                )
            raise FileOperationError(
                f"Failed to load Excel file: {e}",
                file_path=str(file_path),
                operation='load'
            )
        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to load Excel file: {e}",
                file_path=str(file_path),
                operation='load'
            )

    @staticmethod
    def load_binary(directory: CategoryType, filename: str) -> bytes:
        """
        Load binary file.

        Args:
            directory: Source directory (use Categories.*)
            filename: Binary filename

        Returns:
            File content as bytes

        Raises:
            FileOperationError: If file cannot be read
        """
        file_path = get_path(directory, filename, ensure_parent=False)
        logger.debug(f"Loading binary file from {file_path}")

        try:
            content = file_path.read_bytes()
            logger.info(f"Loaded binary from {file_path} ({len(content):,} bytes)")
            return content
        except FileNotFoundError:
            raise FileOperationError(
                f"Binary file not found: {filename}",
                file_path=str(file_path),
                operation='load'
            )
        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to read binary file: {e}",
                file_path=str(file_path),
                operation='load'
            )

    @staticmethod
    def load_gzip(directory: CategoryType, filename: str) -> bytes:
        """
        Load and decompress GZip file.

        Args:
            directory: Source directory (use Categories.*)
            filename: GZip filename

        Returns:
            Decompressed content as bytes

        Raises:
            FileOperationError: If file cannot be read or decompressed
        """
        file_path = get_path(directory, filename, ensure_parent=False)
        logger.debug(f"Loading GZip file from {file_path}")

        try:
            with gzip.open(file_path, 'rb') as gz_file:
                content = gz_file.read()
                logger.info(f"Loaded and decompressed {file_path} ({len(content):,} bytes)")
                return content
        except FileNotFoundError:
            raise FileOperationError(
                f"GZip file not found: {filename}",
                file_path=str(file_path),
                operation='load'
            )
        except gzip.BadGzipFile:
            raise FileOperationError(
                f"Invalid GZip file: {filename}",
                file_path=str(file_path),
                operation='load'
            )
        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to load GZip file: {e}",
                file_path=str(file_path),
                operation='load'
            )

    # ==================== Specialized Save Methods ====================

    @staticmethod
    def save_json(data: Union[Dict, list],
                  directory: CategoryType,
                  filename: str,
                  compact: bool = False,
                  sort_keys: bool = False,
                  ensure_ascii: bool = False) -> Path:
        """
        Save data as JSON with formatting options.

        Args:
            data: JSON-serializable data (dict or list)
            directory: Target directory (use Categories.*)
            filename: Target filename
            compact: Minimize file size (no indentation)
            sort_keys: Sort dictionary keys alphabetically
            ensure_ascii: Force ASCII encoding

        Returns:
            Path to saved file

        Raises:
            TypeError: If data is not dict or list
            ValidationError: If data cannot be serialized
            FileOperationError: If file cannot be written
        """
        if not isinstance(data, (dict, list)):
            raise TypeError(
                f"JSON data must be dict or list, got {type(data).__name__}"
            )

        file_path = get_path(directory, filename)

        try:
            if compact:
                content = json.dumps(
                    data,
                    cls=DecimalEncoder,
                    separators=(',', ':'),
                    ensure_ascii=ensure_ascii,
                    sort_keys=sort_keys
                )
            else:
                content = json.dumps(
                    data,
                    indent=TxoDataHandler.DEFAULT_JSON_INDENT,
                    cls=DecimalEncoder,
                    ensure_ascii=ensure_ascii,
                    sort_keys=sort_keys
                )

            file_path.write_text(content, encoding='utf-8')
            size_str = format_size(len(content.encode('utf-8')))
            logger.info(f"Saved JSON to {file_path} ({size_str})")
            return file_path

        except (TypeError, ValueError) as e:
            raise ValidationError(
                f"JSON serialization failed: {e}",
                field='data'
            )
        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to save JSON file: {e}",
                file_path=str(file_path),
                operation='save'
            )

    @staticmethod
    def save_text(content: str,
                  directory: CategoryType,
                  filename: str,
                  encoding: Optional[str] = None,
                  ensure_newline: bool = False,
                  line_ending: Optional[Literal['unix', 'windows']] = None) -> Path:
        """
        Save text content with encoding options.

        Args:
            content: Text content to save
            directory: Target directory (use Categories.*)
            filename: Target filename
            encoding: Text encoding (default: UTF-8)
            ensure_newline: Ensure file ends with newline
            line_ending: Force specific line endings

        Returns:
            Path to saved file

        Raises:
            TypeError: If content is not string
            FileOperationError: If file cannot be written
        """
        if not isinstance(content, str):
            raise TypeError(
                f"Content must be str, got {type(content).__name__}"
            )

        encoding = encoding or TxoDataHandler.DEFAULT_ENCODING

        # Handle line endings
        if line_ending == 'unix':
            content = content.replace('\r\n', '\n').replace('\r', '\n')
        elif line_ending == 'windows':
            content = content.replace('\r\n', '\n').replace('\r', '\n')
            content = content.replace('\n', '\r\n')

        # Ensure newline at end if requested
        if ensure_newline and content and not content.endswith('\n'):
            content += '\n'

        file_path = get_path(directory, filename)

        try:
            file_path.write_text(content, encoding=encoding)
            logger.info(f"Saved text to {file_path} ({len(content):,} chars, {encoding})")
            return file_path
        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to save text file: {e}",
                file_path=str(file_path),
                operation='save'
            )

    @staticmethod
    def save_yaml(data: Union[Dict, list, Any],
                  directory: CategoryType,
                  filename: str,
                  default_flow_style: bool = False,
                  sort_keys: bool = False) -> Path:
        """
        Save data as YAML file.

        Args:
            data: Data to save (usually dict or list)
            directory: Target directory (use Categories.*)
            filename: Target filename
            default_flow_style: Use flow style {a: 1} vs block style
            sort_keys: Sort dictionary keys

        Returns:
            Path to saved file

        Raises:
            ValidationError: If data cannot be serialized
            FileOperationError: If file cannot be written
        """
        # Direct import - hard-fail if not available
        file_path = get_path(directory, filename)

        try:
            yaml_content = yaml.dump(
                data,
                default_flow_style=default_flow_style,
                sort_keys=sort_keys,
                allow_unicode=True,
                encoding=None  # Return string, not bytes
            )

            file_path.write_text(yaml_content, encoding='utf-8')
            logger.info(f"Saved YAML to {file_path}")
            return file_path

        except yaml.YAMLError as e:
            raise ValidationError(
                f"YAML serialization failed: {e}",
                field='data'
            )
        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to save YAML file: {e}",
                file_path=str(file_path),
                operation='save'
            )

    @staticmethod
    def save_binary(data: bytes,
                    directory: CategoryType,
                    filename: str) -> Path:
        """
        Save binary data to file.

        Args:
            data: Binary data to save
            directory: Target directory (use Categories.*)
            filename: Target filename

        Returns:
            Path to saved file

        Raises:
            TypeError: If data is not bytes
            FileOperationError: If file cannot be written
        """
        if not isinstance(data, bytes):
            raise TypeError(
                f"Data must be bytes for binary save, got {type(data).__name__}"
            )

        file_path = get_path(directory, filename)

        try:
            file_path.write_bytes(data)
            size_str = format_size(len(data))
            logger.info(f"Saved binary to {file_path} ({size_str})")
            return file_path
        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to save binary file: {e}",
                file_path=str(file_path),
                operation='save'
            )

    @staticmethod
    def save_gzip(data: Union[str, bytes],
                  directory: CategoryType,
                  filename: str,
                  compression_level: Optional[int] = None) -> Path:
        """
        Save data as GZip compressed file.

        Args:
            data: String or bytes to compress
            directory: Target directory (use Categories.*)
            filename: Target filename (should end with .gz)
            compression_level: Compression level 0-9 (9=max)

        Returns:
            Path to saved file

        Raises:
            FileOperationError: If file cannot be written
        """
        compression_level = compression_level or TxoDataHandler.DEFAULT_COMPRESSION_LEVEL

        if not 0 <= compression_level <= 9:
            raise ValueError(f"Compression level must be 0-9, got {compression_level}")

        file_path = get_path(directory, filename)

        try:
            # Convert string to bytes if needed
            content = data.encode('utf-8') if isinstance(data, str) else data
            original_size = len(content)

            with gzip.open(file_path, 'wb', compresslevel=compression_level) as gz_file:
                gz_file.write(content)

            # Log compression stats
            compressed_size = file_path.stat().st_size
            ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
            logger.info(
                f"Saved GZip to {file_path}: "
                f"{format_size(original_size)} → {format_size(compressed_size)} "
                f"({ratio:.1f}% compression, level={compression_level})"
            )

            return file_path

        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to save GZip file: {e}",
                file_path=str(file_path),
                operation='save'
            )

    # ==================== Private Helper Methods ====================

    @staticmethod
    def _save_dataframe(df: 'pd.DataFrame',
                        directory: CategoryType,
                        filename: str,
                        index: bool = False,
                        sheet_name: Optional[str] = None,
                        **kwargs) -> Path:
        """
        Internal method to save DataFrames.

        Args:
            df: DataFrame to save
            directory: Target directory
            filename: Target filename
            index: Include index in output
            sheet_name: Excel sheet name
            **kwargs: Additional format-specific options

        Returns:
            Path to saved file

        Raises:
            ValueError: If file extension is not supported
            FileOperationError: If save fails
        """
        file_path = get_path(directory, filename)
        file_ext = file_path.suffix.lower()

        try:
            if file_ext == '.csv':
                df.to_csv(file_path, index=index, **kwargs)
            elif file_ext in ('.xlsx', '.xls'):
                sheet_name = sheet_name or TxoDataHandler.DEFAULT_SHEET_NAME
                df.to_excel(
                    file_path,
                    index=index,
                    sheet_name=sheet_name,
                    engine='openpyxl',
                    **kwargs
                )
            else:
                raise ValueError(
                    f"Unsupported extension for DataFrame: {file_ext}. "
                    f"Use .csv or .xlsx"
                )

            logger.info(f"Saved DataFrame to {file_path} ({len(df):,} rows)")
            return file_path

        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to save DataFrame: {e}",
                file_path=str(file_path),
                operation='save'
            )

    @staticmethod
    def _save_workbook(workbook: Any,
                       directory: CategoryType,
                       filename: str) -> Path:
        """
        Internal method to save openpyxl Workbooks.

        Args:
            workbook: Workbook object with save() method
            directory: Target directory
            filename: Target filename

        Returns:
            Path to saved file

        Raises:
            FileOperationError: If save fails
        """
        file_path = get_path(directory, filename)

        try:
            workbook.save(file_path)
            logger.info(f"Saved Workbook to {file_path}")
            return file_path
        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to save Workbook: {e}",
                file_path=str(file_path),
                operation='save'
            )

    # ==================== Utility Methods ====================

    @staticmethod
    def exists(directory: CategoryType, filename: str,
               check_empty: bool = False) -> bool:
        """
        Check if a file exists and optionally if it's not empty.

        Args:
            directory: Directory to check (use Categories.*)
            filename: Filename to check
            check_empty: Also verify file is not empty

        Returns:
            True if file exists (and is not empty if check_empty=True)
        """
        file_path = get_path(directory, filename, ensure_parent=False)

        if not file_path.exists():
            return False

        if check_empty and file_path.stat().st_size == 0:
            logger.warning(f"File exists but is empty: {file_path}")
            return False

        return True

    @staticmethod
    def delete(directory: CategoryType, filename: str,
               safe: bool = True) -> bool:
        """
        Delete a file from the specified directory.

        Args:
            directory: Directory containing file (use Categories.*)
            filename: File to delete
            safe: If True, don't error if file doesn't exist

        Returns:
            True if file was deleted, False if it didn't exist

        Raises:
            FileNotFoundError: If file doesn't exist and safe=False
            FileOperationError: If deletion fails
        """
        file_path = get_path(directory, filename, ensure_parent=False)

        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted file: {file_path}")
                return True
            elif not safe:
                raise FileNotFoundError(f"File not found: {file_path}")
            else:
                logger.debug(f"File already absent: {file_path}")
                return False
        except (OSError, IOError) as e:
            raise FileOperationError(
                f"Failed to delete file: {e}",
                file_path=str(file_path),
                operation='delete'
            )

    @staticmethod
    def get_size(directory: CategoryType, filename: str) -> int:
        """
        Get the size of a file in bytes.

        Args:
            directory: Directory containing file (use Categories.*)
            filename: Filename to check

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        file_path = get_path(directory, filename, ensure_parent=False)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        size = file_path.stat().st_size
        logger.debug(f"File {filename} size: {format_size(size)}")
        return size