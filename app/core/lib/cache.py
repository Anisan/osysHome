""" Cache module """
import os
import shutil
from settings import Config

__cacheDir = Config.CACHE_FILE_PATH

def getCacheDir() -> str:
    """ Get root path cache

    Returns:
        str: Root path cache
    """
    return __cacheDir

def getFullFilename(filename:str, directory:str=None, subdir:bool=False) -> str:
    """ Get fullpath for filename in cache
    
    Args:
        filename (str): Filename
        directory (str, optional): Directory. Defaults to None.
        subdir (bool, optional): Subdirectory. Defaults to False.
    
    Returns:
        str: Full filename
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
    """ Save file to cache

    Args:
        filename (str): File name
        content (str): Content for save
        directory (str, optional): Directory in cache. Defaults to None.
        subdir (bool, optional): Split by subdirectories . Defaults to False.

    Returns:
        str: Filepath in cache
    """
    file_path = getFullFilename(filename, directory, subdir)
    # Создаем все промежуточные подкаталоги, если они не существуют
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'wb') as f:
        f.write(content)
    return file_path

def copyToCache(source: str, filename:str, directory:str=None, subdir:bool=False):
    """ Copy file to cache

    Args:
        source (str): File path
        filename (str): File name
        directory (str, optional): Directory in cache. Defaults to None.
        subdir (bool, optional): Split by subdirectories . Defaults to False.
    """
    file_path = getFullFilename(filename, directory, subdir)
    # Создаем все промежуточные подкаталоги, если они не существуют
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    # Копируем файл
    shutil.copy2(source, file_path)
    pass

def deleteFromCache(filename:str, directory:str=None, subdir:bool=False):
    """ Delete file from cache

    Args:
        filename (str): File name
        directory (str, optional): Directory in cache. Defaults to None.
        subdir (bool, optional): Split by subdirectories . Defaults to False.
    """
    file_path = getFullFilename(filename, directory, subdir)
    os.remove(file_path)

def clearCache(directory:str=None):
    """ Clear cache directory
    
    Args:
        directory (str, optional): Directory in cache. Defaults to None.
    """
    directory_path = os.path.join(__cacheDir, directory)
    shutil.rmtree(directory_path)
    os.makedirs(os.path.dirname(directory_path), exist_ok=True)

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
    


def existInCache(filename:str, directory:str=None, subdir:bool=False) -> bool:
    """Exist file in cache

    Args:
        filename (str): File name
        directory (str, optional): Directory in cache. Defaults to None.
        subdir (bool, optional): Split by subdirectories. Defaults to False.

    Returns:
        bool: True if file exist in cache
    """
    file_path = getFullFilename(filename,directory,subdir)

    if os.path.exists(file_path):
        return True
    else:
        return False
    
def findInCache(filename:str, directory:str=None, subdir:bool=False) -> str:
    """Find file in cache

    Args:
        filename (str): File name
        directory (str, optional): Directory in cache. Defaults to None.
        subdir (bool, optional): Find in subdirectories. Defaults to False.

    Returns:
        str: Filepath in cache
    """
    directory_path = os.path.join(__cacheDir, directory)
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