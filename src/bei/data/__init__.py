import sys

if sys.version_info >= (3, 9):
    import importlib.abc
    import importlib.resources

    def read_data_file(filename: str) -> str:
        return (importlib.resources.files(__name__) / filename).read_text()
else:
    def read_data_file(filename: str) -> str:
        loader = __loader__  # type: ignore[name-defined]
        data = loader.get_data(__file__.replace('__init__.py', filename))
        return data.decode('utf-8')
