import os

CWD: str = os.getcwd()


def get_file_list(path: str, ext: str = "", recurse: bool = False) -> list[str]:
    """
    Compile an appropriate list of files based on the path provided.

    :param path: The path to the file or directory to search.
    :param ext: The file extension to search for. Ignored if path is a file.
    :param recurse: Whether or not to recurse through subdirectories. Ignored if path
        is a file.
    """
    file_list: list[str] = []

    # determine if path is a file or directory
    if os.path.isfile(path):
        # Path is a file, so just add it to the list and move on
        file_list.append(path)
    elif os.path.isdir(path):
        if not ext:
            # No extension provided, so we can't search for files
            raise ValueError("No extension provided, so we can't search for files.")
        # Path is a directory, so we need to search for files
        if recurse:
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(f".{ext}"):
                        file_list.append(os.path.join(root, file))
        else:
            # Just get the files in the current directory
            for file in os.listdir(path):
                if os.path.isfile(file) and file.endswith(f".{ext}"):
                    file_list.append(os.path.join(path, file))
    else:
        raise FileNotFoundError(f"Path '{path}' not found.")

    return file_list


def get_dirs_from_files(files: list[str]) -> list[str]:
    """
    Get the directories from a list of files.

    :param files: A list of files to get the directories from.
    """
    dirs: list[str] = []
    for file in files:
        dirname: str = os.path.dirname(file)
        if dirname not in dirs:
            dirs.append(dirname)
    return dirs
