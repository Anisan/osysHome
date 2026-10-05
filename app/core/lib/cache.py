"""Filesystem cache helpers (paths under Config.CACHE_FILE_PATH)."""
import os
import shutil
from app.configuration import Config

__cacheDir = Config.CACHE_FILE_PATH

def getCacheDir() -> str:
    """Get the root cache directory path.

    Returns:
        str: Absolute path to the cache root
    """
    return __cacheDir

def getFullFilename(filename:str, directory:str = None, subdir:bool = False) -> str:
    """Build a full path for a file inside the cache.

    Args:
        filename (str): File name
        directory (str, optional): Subdirectory under cache root. Defaults to None.
        subdir (bool, optional): Nest under ``filename[:2]/filename[2:4]/``.
            Defaults to False.

    Returns:
        str: Full file path (file may not exist yet)
    """
    if directory:
        directory_path = os.path.join(__cacheDir, directory)
        if subdir:
            subdir_path = os.path.join(directory_path, filename[:2], filename[2:4])
            file_path = os.path.join(subdir_path, filename)
        else:
            file_path = os.path.join(directory_path, filename)
    else:
        file_path = os.path.join(__cacheDir, filename)
    return file_path

def saveToCache(filename:str, content: str, directory:str=None, subdir:bool=False) -> str:
    """Write content to a cache file (creates parent directories).

    Args:
        filename (str): File name
        content (str): Binary-compatible content to write
        directory (str, optional): Subdirectory under cache root. Defaults to None.
        subdir (bool, optional): Nest under hashed subdirectories. Defaults to False.

    Returns:
        str: Full path of the written file
    """
    file_path = getFullFilename(filename, directory, subdir)
    # Создаем все промежуточные подкаталоги, если они не существуют
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'wb') as f:
        f.write(content)
    return file_path

def copyToCache(source: str, filename:str, directory:str=None, subdir:bool=False):
    """Copy an existing file into the cache.

    Args:
        source (str): Source file path
        filename (str): Destination file name in cache
        directory (str, optional): Subdirectory under cache root. Defaults to None.
        subdir (bool, optional): Nest under hashed subdirectories. Defaults to False.
    """
    file_path = getFullFilename(filename, directory, subdir)
    # Создаем все промежуточные подкаталоги, если они не существуют
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    # Копируем файл
    shutil.copy2(source, file_path)
    pass

def deleteFromCache(filename:str, directory:str=None, subdir:bool=False):
    """Delete a file from the cache.

    Args:
        filename (str): File name
        directory (str, optional): Subdirectory under cache root. Defaults to None.
        subdir (bool, optional): Nest under hashed subdirectories. Defaults to False.
    """
    file_path = getFullFilename(filename, directory, subdir)
    os.remove(file_path)

def clearCache(directory:str=None):
    """Remove a cache subdirectory and recreate its parent path.

    Args:
        directory (str, optional): Subdirectory under cache root. Defaults to None.
    """
    directory_path = os.path.join(__cacheDir, directory)
    shutil.rmtree(directory_path)
    os.makedirs(os.path.dirname(directory_path), exist_ok=True)

def getFilesCache(directory:str=None):
    """List file names in a cache directory.

    Args:
        directory (str, optional): Subdirectory under cache root. Defaults to None.

    Returns:
        list | str: File names, empty list if missing, or an error string
            on permission denial.
    """
    directory_path = os.path.join(__cacheDir, directory)
    try:
        filenames = os.listdir(directory_path)
        return filenames
    except FileNotFoundError:
        return []
    except PermissionError:
        return f"Permission denied for directory {directory_path}."

def existInCache(filename:str, directory:str=None, subdir:bool=False) -> bool:
    """Check whether a file exists in the cache.

    Args:
        filename (str): File name
        directory (str, optional): Subdirectory under cache root. Defaults to None.
        subdir (bool, optional): Nest under hashed subdirectories. Defaults to False.

    Returns:
        bool: True if the file exists
    """
    file_path = getFullFilename(filename,directory,subdir)

    if os.path.exists(file_path):
        return True
    else:
        return False

def findInCache(filename:str, directory:str=None, subdir:bool=False) -> str:
    """Find a file in the cache by name.

    Args:
        filename (str): File name to find
        directory (str, optional): Subdirectory under cache root. Defaults to None.
        subdir (bool, optional): If True, walk nested directories. Defaults to False.

    Returns:
        str: Full path if found, otherwise None
    """
    directory_path = os.path.join(__cacheDir, directory)
    if not os.path.exists(directory_path):
        return None
    if subdir:
        for root, _, files in os.walk(directory_path):
            if filename in files:
                return os.path.join(root, filename)
    else:
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            if os.path.isfile(item_path) and item == filename:
                return item_path
    return None
