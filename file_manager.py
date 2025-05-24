"""
File operations manager for VCBot.
Provides centralized file handling with proper context management and cleanup.
"""

from pathlib import Path
from contextlib import contextmanager
import tempfile
from typing import Union, Optional
import shutil
import logging

logger = logging.getLogger(__name__)


class FileManager:
    """Manages file operations with proper context management and cleanup."""
    
    def __init__(self, base_dir: Path):
        """Initialize FileManager with base directory.
        
        Args:
            base_dir: Base directory for relative operations
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"FileManager initialized with base directory: {self.base_dir}")
    
    @contextmanager
    def temporary_file(self, suffix: str = ".txt", prefix: str = "vcbot_"):
        """Context manager for temporary files with automatic cleanup.
        
        Args:
            suffix: File extension (default: .txt)
            prefix: Filename prefix (default: vcbot_)
            
        Yields:
            Path: Path to temporary file
            
        Example:
            with file_manager.temporary_file(".pdf") as temp_path:
                temp_path.write_bytes(pdf_content)
                # File automatically cleaned up on exit
        """
        temp_file = None
        temp_path = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                suffix=suffix,
                prefix=prefix,
                dir=self.base_dir,
                delete=False
            )
            temp_path = Path(temp_file.name)
            temp_file.close()  # Close so file can be used by other processes
            logger.debug(f"Created temporary file: {temp_path}")
            yield temp_path
        finally:
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug(f"Cleaned up temporary file: {temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_path}: {e}")
    
    def ensure_directory(self, directory: Union[str, Path]) -> Path:
        """Ensure directory exists, creating it if necessary.
        
        Args:
            directory: Directory path (relative to base_dir or absolute)
            
        Returns:
            Path: Absolute path to directory
        """
        dir_path = self._resolve_path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {dir_path}")
        return dir_path
    
    def save_text(self, content: str, filename: str, directory: Union[str, Path] = None, 
                  encoding: str = 'utf-8') -> Path:
        """Save text content to file.
        
        Args:
            content: Text content to save
            filename: Name of file to create
            directory: Directory to save in (default: base_dir)
            encoding: Text encoding (default: utf-8)
            
        Returns:
            Path: Path to saved file
        """
        target_dir = self.ensure_directory(directory or self.base_dir)
        filepath = target_dir / filename
        
        try:
            filepath.write_text(content, encoding=encoding)
            logger.info(f"Saved text file: {filepath} ({len(content)} chars)")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save text file {filepath}: {e}")
            raise
    
    def save_bytes(self, content: bytes, filename: str, directory: Union[str, Path] = None) -> Path:
        """Save binary content to file.
        
        Args:
            content: Binary content to save
            filename: Name of file to create
            directory: Directory to save in (default: base_dir)
            
        Returns:
            Path: Path to saved file
        """
        target_dir = self.ensure_directory(directory or self.base_dir)
        filepath = target_dir / filename
        
        try:
            filepath.write_bytes(content)
            logger.info(f"Saved binary file: {filepath} ({len(content)} bytes)")
            return filepath
        except Exception as e:
            logger.error(f"Failed to save binary file {filepath}: {e}")
            raise
    
    def read_text(self, filepath: Union[str, Path], encoding: str = 'utf-8') -> str:
        """Read text content from file.
        
        Args:
            filepath: Path to file (relative to base_dir or absolute)
            encoding: Text encoding (default: utf-8)
            
        Returns:
            str: File content
        """
        file_path = self._resolve_path(filepath)
        
        try:
            content = file_path.read_text(encoding=encoding)
            logger.debug(f"Read text file: {file_path} ({len(content)} chars)")
            return content
        except Exception as e:
            logger.error(f"Failed to read text file {file_path}: {e}")
            raise
    
    def read_bytes(self, filepath: Union[str, Path]) -> bytes:
        """Read binary content from file.
        
        Args:
            filepath: Path to file (relative to base_dir or absolute)
            
        Returns:
            bytes: File content
        """
        file_path = self._resolve_path(filepath)
        
        try:
            content = file_path.read_bytes()
            logger.debug(f"Read binary file: {file_path} ({len(content)} bytes)")
            return content
        except Exception as e:
            logger.error(f"Failed to read binary file {file_path}: {e}")
            raise
    
    def append_text(self, content: str, filepath: Union[str, Path], 
                    encoding: str = 'utf-8') -> None:
        """Append text content to file.
        
        Args:
            content: Text content to append
            filepath: Path to file (relative to base_dir or absolute)
            encoding: Text encoding (default: utf-8)
        """
        file_path = self._resolve_path(filepath)
        
        try:
            with open(file_path, 'a', encoding=encoding) as f:
                f.write(content)
            logger.debug(f"Appended to text file: {file_path} ({len(content)} chars)")
        except Exception as e:
            logger.error(f"Failed to append to file {file_path}: {e}")
            raise
    
    def copy_file(self, source: Union[str, Path], destination: Union[str, Path]) -> Path:
        """Copy file from source to destination.
        
        Args:
            source: Source file path
            destination: Destination file path
            
        Returns:
            Path: Path to copied file
        """
        source_path = self._resolve_path(source)
        dest_path = self._resolve_path(destination)
        
        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.copy2(source_path, dest_path)
            logger.info(f"Copied file: {source_path} -> {dest_path}")
            return dest_path
        except Exception as e:
            logger.error(f"Failed to copy file {source_path} to {dest_path}: {e}")
            raise
    
    def move_file(self, source: Union[str, Path], destination: Union[str, Path]) -> Path:
        """Move file from source to destination.
        
        Args:
            source: Source file path
            destination: Destination file path
            
        Returns:
            Path: Path to moved file
        """
        source_path = self._resolve_path(source)
        dest_path = self._resolve_path(destination)
        
        # Ensure destination directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.move(str(source_path), str(dest_path))
            logger.info(f"Moved file: {source_path} -> {dest_path}")
            return dest_path
        except Exception as e:
            logger.error(f"Failed to move file {source_path} to {dest_path}: {e}")
            raise
    
    def delete_file(self, filepath: Union[str, Path]) -> bool:
        """Delete file if it exists.
        
        Args:
            filepath: Path to file to delete
            
        Returns:
            bool: True if file was deleted, False if it didn't exist
        """
        file_path = self._resolve_path(filepath)
        
        if not file_path.exists():
            logger.debug(f"File not found for deletion: {file_path}")
            return False
        
        try:
            file_path.unlink()
            logger.info(f"Deleted file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            raise
    
    def file_exists(self, filepath: Union[str, Path]) -> bool:
        """Check if file exists.
        
        Args:
            filepath: Path to check
            
        Returns:
            bool: True if file exists
        """
        file_path = self._resolve_path(filepath)
        exists = file_path.exists() and file_path.is_file()
        logger.debug(f"File exists check: {file_path} = {exists}")
        return exists
    
    def directory_exists(self, dirpath: Union[str, Path]) -> bool:
        """Check if directory exists.
        
        Args:
            dirpath: Path to check
            
        Returns:
            bool: True if directory exists
        """
        dir_path = self._resolve_path(dirpath)
        exists = dir_path.exists() and dir_path.is_dir()
        logger.debug(f"Directory exists check: {dir_path} = {exists}")
        return exists
    
    def get_file_size(self, filepath: Union[str, Path]) -> int:
        """Get file size in bytes.
        
        Args:
            filepath: Path to file
            
        Returns:
            int: File size in bytes
        """
        file_path = self._resolve_path(filepath)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        size = file_path.stat().st_size
        logger.debug(f"File size: {file_path} = {size} bytes")
        return size
    
    def list_files(self, directory: Union[str, Path] = None, pattern: str = "*") -> list[Path]:
        """List files in directory matching pattern.
        
        Args:
            directory: Directory to search (default: base_dir)
            pattern: Glob pattern to match (default: all files)
            
        Returns:
            list[Path]: List of matching file paths
        """
        search_dir = self._resolve_path(directory or self.base_dir)
        
        if not search_dir.exists():
            logger.warning(f"Directory does not exist: {search_dir}")
            return []
        
        try:
            files = [f for f in search_dir.glob(pattern) if f.is_file()]
            logger.debug(f"Found {len(files)} files in {search_dir} matching '{pattern}'")
            return files
        except Exception as e:
            logger.error(f"Failed to list files in {search_dir}: {e}")
            raise
    
    def _resolve_path(self, path: Union[str, Path]) -> Path:
        """Resolve path relative to base directory if not absolute.
        
        Args:
            path: Path to resolve
            
        Returns:
            Path: Absolute path
        """
        if path is None:
            return self.base_dir
        
        path_obj = Path(path)
        
        if path_obj.is_absolute():
            return path_obj
        else:
            return self.base_dir / path_obj