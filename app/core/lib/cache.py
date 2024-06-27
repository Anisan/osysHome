""" Cache module """
import os
from settings import Config

__cacheDir = Config.CACHE_FILE_PATH

def getCacheDir() -> str:
    """ Get root path cache

    Returns:
        str: Root path cache
    """
    return __cacheDir

def saveToCache(filename:str, content: str, directory:str=None, subdir:bool=False) -> str:
    """ Save file to cache

    Args:
        filename (str): File name
        content (str): Content for save
        directory (str, optional): Directory in cache. Defaults to None.
        subdir (bool, optional): Split by subdirectories . Defaults to False.

    Returns:
        str: Filepath in cache
    """

    if directory:
        directory_path = os.path.join(__cacheDir, directory)
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
        if subdir:
            subdir_path = os.path.join(directory_path, filename[:2])
            if not os.path.exists(subdir_path):
                os.makedirs(subdir_path)
            subdir_path = os.path.join(subdir_path, filename[2:4])
            if not os.path.exists(subdir_path):
                os.makedirs(subdir_path)
            file_path = os.path.join(subdir_path, filename)
        else:
            file_path = os.path.join(directory_path, filename)
    else:
        file_path = os.path.join(__cacheDir, filename)

    with open(file_path, 'wb') as f:
        f.write(content)
    
    return file_path

def getFilesCache(directory:str=None):
    """ Get files in cache

    Args:
        directory (str, optional): Directory in cache. Defaults to None.

    Return:
        list: List of files in cache
    """
    directory_path = os.path.join(__cacheDir, directory)
    try:
        filenames = os.listdir(directory_path)
        return filenames
    except FileNotFoundError:
        return []
    except PermissionError:
        return f"Permission denied for directory {directory_path}."
    


def findInCache(filename:str, directory:str=None, subdir:bool=False) -> str:
    """Find file in cache

    Args:
        filename (str): File name
        directory (str, optional): Directory in cache. Defaults to None.
        subdir (bool, optional): Split by subdirectories. Defaults to False.

    Returns:
        str: Filepath in cache
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

    if os.path.exists(file_path):
        return file_path
    else:
        return None
    