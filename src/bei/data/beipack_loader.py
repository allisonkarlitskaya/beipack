# beipack https://github.com/allisonkarlitskaya/beipack

import importlib.abc
import importlib.util
import io
import sys
from types import ModuleType
from typing import BinaryIO, Dict, Iterator, Optional, Sequence


class BeipackLoader(importlib.abc.SourceLoader, importlib.abc.MetaPathFinder):
    if sys.version_info >= (3, 11):
        from importlib.resources.abc import ResourceReader as AbstractResourceReader
    else:
        AbstractResourceReader = object

    class ResourceReader(AbstractResourceReader):
        def __init__(self, contents: Dict[str, bytes], filename: str) -> None:
            self._contents = contents
            self._dir = f'{filename}/'

        def is_resource(self, resource: str) -> bool:
            return f'{self._dir}{resource}' in self._contents

        def open_resource(self, resource: str) -> BinaryIO:
            return io.BytesIO(self._contents[f'{self._dir}{resource}'])

        def resource_path(self, resource: str) -> str:
            raise FileNotFoundError

        def contents(self) -> Iterator[str]:
            dir_length = len(self._dir)
            result = set()

            for filename in self._contents:
                if filename.startswith(self._dir):
                    try:
                        next_slash = filename.index('/', dir_length)
                    except ValueError:
                        next_slash = None
                    result.add(filename[dir_length:next_slash])

            return iter(result)

    contents: Dict[str, bytes]
    modules: Dict[str, str]

    def __init__(self, contents: Dict[str, bytes]) -> None:
        try:
            contents[__file__] = __self_source__  # type: ignore[name-defined]
        except NameError:
            pass

        self.contents = contents
        self.modules = {
            self.get_fullname(filename): filename
            for filename in contents
            if filename.endswith(".py")
        }

    def get_fullname(self, filename: str) -> str:
        assert filename.endswith(".py")
        filename = filename[:-3]
        if filename.endswith("/__init__"):
            filename = filename[:-9]
        return filename.replace("/", ".")

    def get_resource_reader(self, fullname: str) -> ResourceReader:
        return BeipackLoader.ResourceReader(self.contents, fullname.replace('.', '/'))

    def get_data(self, path: str) -> bytes:
        return self.contents[path]

    def get_filename(self, fullname: str) -> str:
        return self.modules[fullname]

    def find_spec(
        self,
        fullname: str,
        path: Optional[Sequence[str]],
        target: Optional[ModuleType] = None
      ) -> Optional[importlib.machinery.ModuleSpec]:
        if fullname not in self.modules:
            return None
        return importlib.util.spec_from_loader(fullname, self)
