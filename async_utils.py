"""Async utilities for file operations and other async helpers."""

import aiofiles
import asyncio
from pathlib import Path
from typing import Optional, List, Union


async def read_file(path: Union[str, Path], encoding: str = 'utf-8') -> str:
    """Async file read.
    
    Args:
        path: File path to read
        encoding: File encoding (default: utf-8)
        
    Returns:
        File contents as string
    """
    path = Path(path)
    async with aiofiles.open(path, 'r', encoding=encoding) as f:
        return await f.read()


async def write_file(path: Union[str, Path], content: str, encoding: str = 'utf-8') -> None:
    """Async file write.
    
    Args:
        path: File path to write
        content: Content to write
        encoding: File encoding (default: utf-8)
    """
    path = Path(path)
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiofiles.open(path, 'w', encoding=encoding) as f:
        await f.write(content)


async def append_file(path: Union[str, Path], content: str, encoding: str = 'utf-8') -> None:
    """Async file append.
    
    Args:
        path: File path to append to
        content: Content to append
        encoding: File encoding (default: utf-8)
    """
    path = Path(path)
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiofiles.open(path, 'a', encoding=encoding) as f:
        await f.write(content)


async def read_json(path: Union[str, Path]) -> any:
    """Async JSON file read.
    
    Args:
        path: JSON file path
        
    Returns:
        Parsed JSON data
    """
    import json
    content = await read_file(path)
    return json.loads(content)


async def write_json(path: Union[str, Path], data: any, indent: int = 2) -> None:
    """Async JSON file write.
    
    Args:
        path: JSON file path
        data: Data to write as JSON
        indent: JSON indentation level
    """
    import json
    content = json.dumps(data, indent=indent)
    await write_file(path, content)


async def file_exists(path: Union[str, Path]) -> bool:
    """Check if file exists asynchronously.
    
    Args:
        path: File path to check
        
    Returns:
        True if file exists
    """
    path = Path(path)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, path.exists)


async def list_files(directory: Union[str, Path], pattern: str = "*") -> List[Path]:
    """List files in directory asynchronously.
    
    Args:
        directory: Directory to list
        pattern: Glob pattern (default: *)
        
    Returns:
        List of file paths
    """
    directory = Path(directory)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: list(directory.glob(pattern)))


async def read_csv_append(path: Union[str, Path], row: str) -> None:
    """Append a row to CSV file asynchronously.
    
    Args:
        path: CSV file path
        row: CSV row to append (should include newline)
    """
    await append_file(path, row)


async def run_in_executor(func, *args, **kwargs):
    """Run a synchronous function in an executor.
    
    Args:
        func: Synchronous function to run
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Function result
    """
    loop = asyncio.get_event_loop()
    if kwargs:
        # Create partial function if we have kwargs
        from functools import partial
        func_with_args = partial(func, *args, **kwargs)
        return await loop.run_in_executor(None, func_with_args)
    else:
        return await loop.run_in_executor(None, func, *args)