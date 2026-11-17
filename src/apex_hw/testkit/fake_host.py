"""An in-memory Host for tests."""

from collections.abc import Sequence
import fnmatch
import posixpath

from apex_hw.platform import host as host_lib


class FakeHost:
    """A machine made of a dictionary of files, links and command outputs.

    Directories exist implicitly as prefixes of file and link paths.
    """

    def __init__(
        self,
        files: dict[str, str] | None = None,
        links: dict[str, str] | None = None,
        commands: dict[tuple[str, ...], host_lib.Command] | None = None,
        environ: dict[str, str] | None = None,
    ) -> None:
        self.files = dict(files or {})
        self.links = dict(links or {})
        self.commands = dict(commands or {})
        self.environ = dict(environ or {})
        self.slept = 0.0

    def _paths(self) -> set[str]:
        """Returns every file, link and implied directory."""
        paths = set(self.files) | set(self.links)
        for path in list(paths):
            while path != "/":
                path = posixpath.dirname(path)
                paths.add(path)
        return paths

    def realpath(self, path: str) -> str:
        """Resolves links in any component of a path."""
        parts = path.strip("/").split("/")
        current = "/"
        for part in parts:
            current = posixpath.join(current, part)
            if current in self.links:
                current = posixpath.normpath(
                    posixpath.join(
                        posixpath.dirname(current), self.links[current]
                    )
                )
        return current

    def read(self, path: str) -> str | None:
        """Returns a file's text without trailing whitespace, or None."""
        text = self.files.get(self.realpath(path))
        return None if text is None else text.rstrip()

    def read_bytes(self, path: str) -> bytes | None:
        """Returns a file's bytes, or None."""
        text = self.files.get(self.realpath(path))
        return None if text is None else text.encode("latin-1")

    def glob(self, pattern: str) -> list[str]:
        """Returns the sorted paths that match a glob."""
        depth = pattern.count("/")
        return sorted(
            path
            for path in self._paths()
            if path.count("/") == depth and fnmatch.fnmatchcase(path, pattern)
        )

    def readlink(self, path: str) -> str | None:
        """Returns a link's target, resolving links before its last part."""
        parent = self.realpath(posixpath.dirname(path))
        return self.links.get(posixpath.join(parent, posixpath.basename(path)))

    def access(self, path: str, mode: int) -> bool:
        """Grants access to every file that exists."""
        del mode
        return self.realpath(path) in self.files

    def run(self, argv: Sequence[str]) -> host_lib.Command | None:
        """Returns the canned output for a command, or None."""
        return self.commands.get(tuple(argv))

    def env(self, name: str) -> str | None:
        """Returns a fake environment variable."""
        return self.environ.get(name)

    def sleep(self, seconds: float) -> None:
        """Records the wait instead of waiting."""
        self.slept += seconds
