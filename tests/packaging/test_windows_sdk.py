"""Conan graph, distribution staging, and launcher checks; no LLVM build needed."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


REPO = Path(__file__).resolve().parents[2]
RECIPE = REPO / "recipes" / "adaptivecpp-llvm"
SDK_REF = "adaptivecpp-llvm/25.10.0-llvm19.1.7"


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="acpp windows sdk ")
        self.root = Path(self.temp.name)
        self.env = dict(os.environ, CONAN_HOME=str(self.root / "cache"))

    def tearDown(self):
        self.temp.cleanup()

    def command(self, *arguments, success=True, env=None):
        result = subprocess.run(
            [str(arg) for arg in arguments], cwd=REPO, env=env or self.env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout + (result.stderr if not success else "")


@unittest.skipUnless(shutil.which("conan"), "Conan 2 is required")
class SDKRecipeTests(CommandTests):
    @property
    def profiles(self):
        sdk_profile = RECIPE / "profiles" / "windows-x64-clang19"
        return ["-pr:h", sdk_profile, "-pr:b", sdk_profile]

    def graph(self, *arguments):
        output = self.command("conan", "graph", "info", RECIPE, *self.profiles,
                              "--no-remote", "--format=json", *arguments)
        return json.loads(output)["graph"]["nodes"]["0"]

    def test_supported_profile_and_variant_identity(self):
        node = self.graph()
        self.assertIsNone(node["info_invalid"])
        self.assertFalse(node["dependencies"])
        self.assertNotEqual(node["package_id"], self.graph("-o", "&:with_cuda=False")["package_id"])

    def test_invalid_configurations(self):
        for arguments in (("-s:h", "arch=armv8"), ("-s:h", "os=Linux"),
                          ("-s:h", "build_type=Debug"), ("-s:h", "compiler.version=20"),
                          ("-s:h", "compiler.runtime=static"),
                          ("-s:h", "compiler.cppstd=14"),
                          ("-c", "tools.cmake.cmaketoolchain:generator=Visual Studio 17 2022")):
            with self.subTest(arguments=arguments):
                self.assertTrue(self.graph(*arguments)["info_invalid"])

    def test_unpinned_version_refused(self):
        self.command("conan", "graph", "info", RECIPE, *self.profiles, "--no-remote",
                     "--version=25.10.0-llvm20.1.8", success=False)

    def test_cross_build_rejected(self):
        build_profile = self.root / "linux-profile"
        build_profile.write_text("[settings]\nos=Linux\narch=x86_64\ncompiler=gcc\n"
                                 "compiler.version=13\ncompiler.libcxx=libstdc++11\nbuild_type=Release\n")
        self.assertTrue(self.graph("-pr:b", build_profile)["invalid_build"])

    def test_source_export_contains_this_checkout_and_nvidia_inputs(self):
        self.command("conan", "export", RECIPE)
        folder = Path(self.command("conan", "cache", "path", SDK_REF,
                                   "--folder=export_source").strip()) / "sources"
        for relative in ("CMakeLists.txt", "bin/acpp", "cmake/acpp.cmd",
                         "cmake/CudaPtxTests.cmake", "tests/cuda_ptx/CMakeLists.txt",
                         "tests/cuda_driver/embedded_libdevice_test.cpp",
                         "third-party/nvidia/libdevice/libdevice.10.bc"):
            self.assertEqual((folder / "AdaptiveCpp" / relative).read_bytes(),
                             (REPO / relative).read_bytes())
        self.assertTrue((folder / "packaging" / "CMakeLists.txt").is_file())

    def test_local_generation_uses_integrated_build_and_common_stage(self):
        output = self.root / "local"
        self.command("conan", "install", RECIPE, *self.profiles, "--no-remote", "-of", output,
                     "-c", "tools.cmake.cmaketoolchain:user_presets=",
                     "-c", "tools.microsoft.msbuild:installation_path=")
        generators = output / "build" / "llvm-sdk" / "Release" / "generators"
        toolchain = (generators / "conan_toolchain.cmake").read_text()
        self.assertIn("set(LLVM_ADAPTIVECPP_LINK_INTO_TOOLS ON", toolchain)
        self.assertIn("set(ACPP_ALLOW_DOWNLOADS OFF", toolchain)
        self.assertIn("set(ACPP_BUILD_CUDA_DRIVER_TESTS OFF", toolchain)
        self.assertIn("set(ACPP_BUILD_CUDA_PTX_TESTS ON", toolchain)
        self.assertIn("set(LLVM_INSTALL_TOOLCHAIN_ONLY ON", toolchain)
        presets = json.loads((generators / "CMakePresets.json").read_text())
        cache = presets["configurePresets"][0]["cacheVariables"]
        self.assertEqual(cache["CMAKE_CXX_COMPILER"], "clang-cl")
        self.assertTrue(cache["CMAKE_INSTALL_PREFIX"].endswith("/Release/stage"))

    def test_consumer_uses_packaged_compiler_and_native_cmake_integration(self):
        # Exercise real Conan host/tool dependency resolution without compiling
        # LLVM. Only the generated compiler paths and package metadata are used.
        output = self.root / "sdk-build"
        common = [*self.profiles, "--no-remote", "-of", output,
                  "-c", "tools.cmake.cmaketoolchain:user_presets=",
                  "-c", "tools.microsoft.msbuild:installation_path="]
        self.command("conan", "install", RECIPE, *common)
        stage = output / "build/llvm-sdk/Release/stage"
        (stage / "bin").mkdir(parents=True)
        (stage / "bin/clang.exe").write_bytes(b"compiler fixture")
        self.command("conan", "export-pkg", RECIPE, *common, "--test-folder=")
        consumer = self.root / "consumer"
        consumer.mkdir()
        (consumer / "conanfile.py").write_text(
            'from conan import ConanFile\n'
            'class Consumer(ConanFile):\n'
            '    settings = "os", "arch", "compiler", "build_type"\n'
            f'    requires = "{SDK_REF}"\n'
            '    generators = "CMakeDeps", "CMakeToolchain", "VirtualRunEnv"\n'
            '    def build_requirements(self):\n'
            f'        self.tool_requires("{SDK_REF}", package_id_mode="full_mode")\n'
        )
        generated = self.root / "consumer-output"
        self.command("conan", "install", consumer, *self.profiles, "--no-remote",
                     "-of", generated, "-c", "tools.microsoft.msbuild:installation_path=")
        graph = json.loads(self.command("conan", "graph", "info", consumer, *self.profiles,
                                        "--no-remote", "--format=json"))["graph"]["nodes"]
        sdk = next(node for node in graph.values() if node.get("ref", "").startswith(SDK_REF))
        package_ref = f"{sdk['ref']}:{sdk['package_id']}"
        package_folder = self.command("conan", "cache", "path", package_ref).strip()
        compiler = str(Path(package_folder) / "bin/clang.exe").replace("\\", "/")
        toolchain = (generated / "conan_toolchain.cmake").read_text()
        self.assertIn(f'set(CMAKE_CXX_COMPILER "{compiler}")', toolchain)
        self.assertIn("lib/cmake/AdaptiveCpp", toolchain)
        self.assertFalse((generated / "AdaptiveCppConfig.cmake").exists())


@unittest.skipUnless(shutil.which("cmake"), "CMake is required")
class SDKDistributionTests(CommandTests):
    def stage_fixture(self):
        # Distribution contract: installed compiler, runtime, native integration,
        # resource headers, JIT bitcode/import library, and all license notices.
        files = (
            "bin/clang.exe", "bin/clang++.exe", "bin/clang-cl.exe", "bin/llc.exe",
            "bin/opt.exe", "bin/lld-link.exe", "bin/llvm-link.exe", "bin/acpp",
            "bin/acpp.cmd", "bin/acpp-rt.dll", "bin/acpp-common.dll", "bin/libomp.dll",
            "bin/hipSYCL/rt-backend-omp.dll", "bin/hipSYCL/rt-backend-cuda.dll",
            "lib/acpp-rt.lib", "lib/acpp-common.lib",
            "lib/hipSYCL/acpp-sscp-host-c-runtime-import.lib",
            "lib/hipSYCL/bitcode/libkernel-sscp-host-full.bc",
            "lib/hipSYCL/bitcode/libkernel-sscp-host-fast-full.bc",
            "lib/hipSYCL/bitcode/libkernel-sscp-ptx-full.bc",
            "lib/cmake/AdaptiveCpp/adaptivecpp-config.cmake",
            "lib/cmake/AdaptiveCpp/adaptivecpp-config-version.cmake",
            "lib/clang/19/include/stddef.h", "licenses/llvm/LICENSE.TXT",
            "licenses/AdaptiveCpp/LICENSE", "licenses/nvidia/NOTICE.txt",
        )
        stage = self.root / "staged SDK"
        for relative in files:
            path = stage / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(relative.encode())
        return stage, files

    def configure(self, stage, success=True):
        return self.command(
            "cmake", "-S", RECIPE / "packaging", "-B", self.root / "installer",
            f"-DACPP_SDK_STAGE={stage}", "-DACPP_SDK_VERSION=25.10.0-llvm19.1.7",
            "-DACPP_VERSION=25.10.0", "-DACPP_LLVM_VERSION=19.1.7",
            "-DACPP_SDK_WITH_CUDA=ON", success=success,
        )

    def test_incomplete_sdk_rejected(self):
        stage, _ = self.stage_fixture()
        (stage / "bin/clang.exe").unlink()
        self.assertIn("missing bin/clang.exe", self.configure(stage, success=False))

    def test_zip_contains_the_entire_sdk_payload(self):
        stage, files = self.stage_fixture()
        self.configure(stage)
        self.command("cpack", "--config", self.root / "installer/CPackConfig.cmake",
                     "-G", "ZIP", "-B", self.root / "artifacts")
        archive = next((self.root / "artifacts").glob("*.zip"))
        with zipfile.ZipFile(archive) as package:
            for relative in files:
                member = next(name for name in package.namelist() if name.endswith("/" + relative))
                self.assertEqual(package.read(member), (stage / relative).read_bytes())

    @unittest.skipUnless(shutil.which("makensis"), "NSIS is required")
    def test_nsis_installer_generation(self):
        stage, _ = self.stage_fixture()
        self.configure(stage)
        self.command("cpack", "--config", self.root / "installer/CPackConfig.cmake",
                     "-G", "NSIS", "-B", self.root / "artifacts")
        installer = next((self.root / "artifacts").glob("*.exe"))
        self.assertEqual(installer.read_bytes()[:2], b"MZ")


@unittest.skipIf(os.name == "nt", "Native Windows installation is checked by check_windows_sdk.ps1")
@unittest.skipUnless(shutil.which("cmake") and shutil.which("c++"), "CMake and C++ are required")
class WindowsLauncherTests(CommandTests):
    def test_launcher_preserves_paths_and_arguments_with_spaces(self):
        prefix = self.root / "Program Files" / "AdaptiveCpp SDK"
        integration = prefix / "lib/cmake/AdaptiveCpp"
        integration.mkdir(parents=True)
        (prefix / "bin").mkdir()
        python = prefix / "bin/python with spaces"
        python.symlink_to(sys.executable)
        compiler = prefix / "bin/c++"
        compiler.symlink_to(shutil.which("c++"))
        log = self.root / "driver arguments.jsonl"
        (prefix / "bin/acpp").write_text(
            "import json, subprocess, sys\n"
            f"with open({str(log)!r}, 'a') as output: output.write(json.dumps(sys.argv[1:])+'\\n')\n"
            f"sys.exit(subprocess.call([{str(compiler)!r}]+sys.argv[1:]))\n"
        )
        (integration / "adaptivecpp-targets.cmake").write_text(
            "add_library(AdaptiveCpp::acpp-rt INTERFACE IMPORTED)\n")
        for filename in ("syclcc-launcher", "syclcc-launch.rule.in"):
            shutil.copyfile(REPO / "cmake" / filename, integration / filename)
        project = self.root / "consumer with spaces"
        project.mkdir()
        (project / "main.cpp").write_text('int main() { return MESSAGE[0] == \'a\' ? 0 : 1; }\n')
        template = (REPO / "cmake/adaptivecpp-config.cmake.in").as_posix()
        (project / "CMakeLists.txt").write_text(
            'cmake_minimum_required(VERSION 3.23)\nproject(LauncherTest CXX)\n'
            'include(CMakePackageConfigHelpers)\n'
            'set(ADAPTIVECPP_INSTALL_COMPILER_DIR bin)\n'
            'set(ADAPTIVECPP_INSTALL_LAUNCHER_DIR lib/cmake/AdaptiveCpp)\n'
            'set(ADAPTIVECPP_INSTALL_LAUNCHER_RULE_DIR lib/cmake/AdaptiveCpp)\n'
            f'configure_package_config_file("{template}" "{integration.as_posix()}/adaptivecpp-config.cmake"\n'
            '  INSTALL_DESTINATION lib/cmake/AdaptiveCpp\n'
            '  PATH_VARS ADAPTIVECPP_INSTALL_COMPILER_DIR ADAPTIVECPP_INSTALL_LAUNCHER_DIR ADAPTIVECPP_INSTALL_LAUNCHER_RULE_DIR)\n'
            'set(WIN32 TRUE)\n'
            f'set(Python3_EXECUTABLE "{python.as_posix()}")\n'
            f'find_package(AdaptiveCpp CONFIG REQUIRED PATHS "{integration.as_posix()}" NO_DEFAULT_PATH)\n'
            'add_executable(launcher_test main.cpp)\n'
            'target_compile_definitions(launcher_test PRIVATE MESSAGE="a value with spaces")\n'
            'add_sycl_to_target(TARGET launcher_test)\n'
        )
        build = self.root / "build with spaces"
        self.command("cmake", "-S", project, "-B", build, f"-DCMAKE_CXX_COMPILER={compiler}")
        self.command("cmake", "--build", build)
        self.command(build / "launcher_test")
        invocations = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertTrue(any('-DMESSAGE="a value with spaces"' in args for args in invocations))


if __name__ == "__main__":
    unittest.main(verbosity=2)
