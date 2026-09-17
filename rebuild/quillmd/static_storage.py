"""WhiteNoise compression with explicit permissions for compiled public assets."""
from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import stat

from whitenoise.compress import Compressor
from whitenoise.storage import CompressedManifestStaticFilesStorage


class PublicAssetCompressor(Compressor):
    def __init__(self, root, **kwargs):
        super().__init__(**kwargs)
        self.root = Path(root)

    @staticmethod
    def _check(info, *, directory=False):
        kind_ok = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if (not kind_ok or info.st_uid != os.geteuid()
                or (directory and info.st_mode & 0o022)
                or (not directory and info.st_nlink != 1)):
            raise RuntimeError('Unsafe compiled static artifact.')

    @contextmanager
    def _parent(self, path):
        path = Path(path)
        if not self.root.is_absolute() or self.root.resolve(strict=True) != self.root:
            raise RuntimeError('Unsafe compiled static root.')
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            raise RuntimeError('Compressed static artifact is outside its storage root.') from None
        if not relative.parts or '..' in relative.parts:
            raise RuntimeError('Invalid compiled static artifact path.')
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        with ExitStack() as stack:
            parent = os.open(self.root, flags)
            stack.callback(os.close, parent)
            self._check(os.fstat(parent), directory=True)
            for name in relative.parts[:-1]:
                parent = os.open(name, flags, dir_fd=parent)
                stack.callback(os.close, parent)
                self._check(os.fstat(parent), directory=True)
            yield parent, relative.name

    def compress(self, path):
        # Read only the validated descriptor. WhiteNoise's default orchestration
        # reopens a pathname; a swap between validation and that open is unsafe.
        with self._parent(path) as (parent, name):
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                                 dir_fd=parent)
            with os.fdopen(descriptor, 'rb') as source:
                info = os.fstat(source.fileno())
                self._check(info)
                data = source.read()
                after = os.fstat(source.fileno())
                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                self._check(after)
                self._check(current)
                identity = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_nlink',
                            'st_size', 'st_mtime_ns', 'st_ctime_ns')
                if any(getattr(info, key) != getattr(candidate, key)
                       for candidate in (after, current) for key in identity):
                    raise RuntimeError('Compiled static input changed during compression.')
        # Keep the library's algorithms and effectiveness rules unchanged.
        filenames = []
        if self.use_brotli:
            compressed = self.compress_brotli(data)
            if not self.is_compressed_effectively('Brotli', path, len(data), compressed):
                return filenames
            filenames.append(self.write_data(path, compressed, '.br', info))
        if self.use_gzip:
            compressed = self.compress_gzip(data)
            if self.is_compressed_effectively('Gzip', path, len(data), compressed):
                filenames.append(self.write_data(path, compressed, '.gz', info))
        return filenames

    def write_data(self, path, data, suffix, stat_result):
        if suffix not in ('.gz', '.br'):
            raise RuntimeError('Unknown compiled static compression format.')
        filename = str(path) + suffix
        with self._parent(filename) as (parent, name):
            # Do not truncate an existing file until its identity is verified.
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                                 0o644, dir_fd=parent)
            with os.fdopen(descriptor, 'wb') as output:
                self._check(os.fstat(output.fileno()))
                os.fchmod(output.fileno(), 0o644)
                output.truncate(0)
                output.write(data)
                output.flush()
                os.utime(output.fileno(), (stat_result.st_atime, stat_result.st_mtime))
        return filename


class PublicCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    def create_compressor(self, **kwargs):
        return PublicAssetCompressor(self.location, **kwargs)
