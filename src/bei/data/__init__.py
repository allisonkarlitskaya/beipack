import importlib.abc
import importlib.resources


def get_file(filename: str) -> importlib.abc.Traversable:
    return importlib.resources.files('bei.data') / filename
