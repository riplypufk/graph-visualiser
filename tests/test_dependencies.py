import io
import tarfile
import gzip
import unittest

from src.dependencies import (
    DependencyError,
    extract_apkindex,
    find_package,
    parse_apkindex,
    parse_dependencies,
)


APKINDEX = """\
P:curl
V:8.10.1-r0
A:x86_64
S:123
I:456
T:HTTP client
D:ca-certificates libcurl nghttp2 zlib

P:libcurl
V:8.10.1-r0
A:x86_64
S:123
I:456
T:URL transfer library
D:nghttp2 zlib

P:zlib
V:1.3.1-r0
A:x86_64
S:123
I:456
T:Compression library
D:

"""


class ApkIndexTests(unittest.TestCase):

    def test_parse_dependencies(self):
        result = parse_dependencies(
            "ca-certificates libcurl nghttp2 zlib"
        )

        self.assertEqual(
            result,
            (
                "ca-certificates",
                "libcurl",
                "nghttp2",
                "zlib",
            ),
        )

    def test_parse_empty_dependencies(self):
        self.assertEqual(
            parse_dependencies(""),
            (),
        )

    def test_parse_apkindex(self):
        packages = parse_apkindex(APKINDEX)

        self.assertEqual(len(packages), 3)

        self.assertEqual(packages[0].name, "curl")
        self.assertEqual(packages[0].version, "8.10.1-r0")

        self.assertEqual(
            packages[0].dependencies,
            (
                "ca-certificates",
                "libcurl",
                "nghttp2",
                "zlib",
            ),
        )

    def test_find_package(self):
        packages = parse_apkindex(APKINDEX)

        package = find_package(
            packages,
            "curl",
            "8.10.1-r0",
        )

        self.assertEqual(package.name, "curl")
        self.assertEqual(package.version, "8.10.1-r0")

    def test_package_version_is_checked(self):
        packages = parse_apkindex(APKINDEX)

        with self.assertRaises(DependencyError):
            find_package(
                packages,
                "curl",
                "wrong-version",
            )

    def test_unknown_package(self):
        packages = parse_apkindex(APKINDEX)

        with self.assertRaises(DependencyError):
            find_package(
                packages,
                "unknown-package",
                "1.0.0",
            )

    def test_extract_apkindex(self):
        tar_buffer = io.BytesIO()

        with tarfile.open(
            fileobj=tar_buffer,
            mode="w",
        ) as archive:
            data = APKINDEX.encode("utf-8")

            info = tarfile.TarInfo("APKINDEX")
            info.size = len(data)

            archive.addfile(
                info,
                io.BytesIO(data),
            )

        gzip_data = gzip.compress(tar_buffer.getvalue())

        result = extract_apkindex(gzip_data)

        self.assertEqual(result, APKINDEX)


if __name__ == "__main__":
    unittest.main()