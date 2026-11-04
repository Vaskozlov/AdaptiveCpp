"""Exercise the real Conan CLI without remotes or a compiler installation.

Run with: python3 tests/packaging/test_recipe.py
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which("conan"), "Conan 2 is required")
class RecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="acpp-conan-test-")
        cls.root = Path(cls.temp.name)
        cls.env = dict(os.environ, CONAN_HOME=str(cls.root / "cache"))
        cls.profile = cls.root / "profile"
        cls.profile.write_text(
            "[settings]\nos=Linux\narch=x86_64\ncompiler=clang\n"
            "compiler.version=19\ncompiler.libcxx=libstdc++11\n"
            "compiler.cppstd=17\nbuild_type=Release\n"
            "[conf]\ntools.cmake.cmaketoolchain:generator=Ninja\n"
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def conan(self, *args):
        result = subprocess.run(
            ["conan", *args], cwd=REPO, env=self.env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def graph(self, *args, llvm_version="19.1.7"):
        options = ["-o", f"&:llvm_version={llvm_version}"] if llvm_version else []
        result = self.conan(
            "graph", "info", ".", "-pr:h", str(self.profile), "-pr:b", str(self.profile),
            "--no-remote", "--format=json", *options, *args,
        )
        return json.loads(result)["graph"]["nodes"]["0"]

    def test_default_configuration(self):
        node = self.graph()
        self.assertIsNone(node["info_invalid"])
        self.assertEqual(node["options"]["with_cuda"], "True")
        self.assertFalse(node["dependencies"])

    def test_exact_llvm_version_required(self):
        self.assertIn("exact installed LLVM release", self.graph(llvm_version=None)["info_invalid"])
        self.assertIn("exact installed LLVM release", self.graph(llvm_version="19")["info_invalid"])
        self.assertIn("LLVM 15 through 21", self.graph(llvm_version="14.0.6")["info_invalid"])

    def test_package_identity(self):
        ids = {
            self.graph()["package_id"],
            self.graph(llvm_version="18.1.8")["package_id"],
            self.graph("-o", "&:with_cuda=False")["package_id"],
            self.graph("-o", "&:package_llvm_tools=False")["package_id"],
        }
        self.assertEqual(len(ids), 4, "LLVM and payload variants must not share binaries")

    def test_invalid_platform_and_cpp_standard(self):
        self.assertIn("native Linux and macOS", self.graph("-s:h", "os=Windows")["info_invalid"])
        self.assertTrue(self.graph("-s:h", "compiler.cppstd=14")["info_invalid"])

    def test_consumers_track_llvm_variant(self):
        self.conan("export", ".")
        reference = self.graph()["ref"]
        consumer = self.root / "consumer"
        consumer.mkdir()
        (consumer / "conanfile.py").write_text(
            "from conan import ConanFile\n"
            "class Application(ConanFile):\n"
            "    settings = 'os', 'arch', 'compiler', 'build_type'\n"
            "    package_type = 'application'\n"
            f"    requires = '{reference}'\n"
        )
        ids = set()
        for llvm_version in ("19.1.7", "18.1.8"):
            output = self.conan(
                "graph", "info", str(consumer), "-pr:h", str(self.profile),
                "-pr:b", str(self.profile), "--no-remote", "--format=json",
                "-o", f"adaptivecpp/*:llvm_version={llvm_version}",
            )
            ids.add(json.loads(output)["graph"]["nodes"]["0"]["package_id"])
        self.assertEqual(len(ids), 2, "Applications must track their LLVM/compiler package variant")

    def test_cross_build_rejected(self):
        self.assertTrue(self.graph("-s:h", "arch=armv8")["invalid_build"])

    def test_local_generation_without_remotes(self):
        output = self.root / "local"
        self.conan(
            "install", ".", "-pr:h", str(self.profile), "-pr:b", str(self.profile),
            "--no-remote", "-of", str(output), "-o", "&:llvm_version=19.1.7",
            "-c", "tools.cmake.cmaketoolchain:user_presets=",
        )
        generators = output / "build" / "conan" / "Release" / "generators"
        toolchain = (generators / "conan_toolchain.cmake").read_text()
        self.assertIn("set(ACPP_ALLOW_DOWNLOADS OFF", toolchain)
        self.assertIn("set(ACPP_EXPECTED_LLVM_VERSION \"19.1.7\"", toolchain)
        self.assertIn("set(ACPP_CUDA_DRIVER_ONLY ON", toolchain)
        self.assertIn("set(CPACK_PACKAGING_INSTALL_PREFIX \"/usr\"", toolchain)


if __name__ == "__main__":
    unittest.main(verbosity=2)
