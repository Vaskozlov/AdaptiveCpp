"""Native Windows SDK: one LLVM/AdaptiveCpp build, Conan and CPack outputs."""

import os
import re
import shutil
from pathlib import Path

from conan import ConanFile
from conan.errors import ConanException, ConanInvalidConfiguration
from conan.tools.build import check_min_cppstd, cross_building, cmd_args_to_string
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.files import copy, get, load


class AdaptiveCppLLVMConan(ConanFile):
    name = "adaptivecpp-llvm"
    version = "25.10.0-llvm19.1.7"
    description = "Windows AdaptiveCpp SDK with compiler passes linked into LLVM"
    homepage = "https://adaptivecpp.github.io"
    url = "https://github.com/AdaptiveCpp/AdaptiveCpp"
    license = "BSD-2-Clause", "Apache-2.0 WITH LLVM-exception", "LicenseRef-NVIDIA-CUDA"
    package_type = "shared-library"
    package_id_non_embed_mode = "full_mode"
    required_conan_version = ">=2.8"
    settings = "os", "arch", "compiler", "build_type"
    options = {"with_cuda": [True, False]}
    default_options = {"with_cuda": True}

    @property
    def _source_data(self):
        try:
            return self.conan_data["sources"][str(self.version)]
        except KeyError:
            raise ConanInvalidConfiguration(f"No pinned LLVM source for SDK {self.version}")

    def export_sources(self):
        root = Path(self.recipe_folder).parents[1]
        destination = os.path.join(self.export_sources_folder, "sources", "AdaptiveCpp")
        for pattern in ("CMakeLists.txt", "LICENSE", "bin/acpp", "cmake/*",
                        "include/*", "src/*", "third-party/nvidia/*",
                        "tests/cuda_driver/embedded_libdevice_test.cpp",
                        "tests/cuda_driver/libdevice_kernel.ll", "tests/cuda_ptx/*"):
            copy(self, pattern, str(root), destination)
        copy(self, "*", os.path.join(self.recipe_folder, "packaging"),
             os.path.join(self.export_sources_folder, "sources", "packaging"))

    def layout(self):
        cmake_layout(self, src_folder="sources", build_folder="build/llvm-sdk")

    def validate(self):
        self._source_data
        if self.settings.os != "Windows" or self.settings.arch != "x86_64":
            raise ConanInvalidConfiguration("This integrated SDK targets native Windows x86_64")
        if self.settings.build_type != "Release":
            raise ConanInvalidConfiguration("The initial Windows SDK supports Release builds")
        if self.settings.compiler != "clang" or str(self.settings.compiler.version) != "19":
            raise ConanInvalidConfiguration("Use the Clang 19 MSVC-ABI profile for this SDK")
        if self.settings.compiler.get_safe("runtime") != "dynamic":
            raise ConanInvalidConfiguration("Use compiler.runtime=dynamic (MSVC /MD)")
        if self.settings.compiler.get_safe("runtime_type") != "Release":
            raise ConanInvalidConfiguration("Use compiler.runtime_type=Release")
        if self.settings.compiler.get_safe("runtime_version") != "v143":
            raise ConanInvalidConfiguration("Use compiler.runtime_version=v143 (VS 2022)")
        if self.settings.compiler.get_safe("cppstd"):
            check_min_cppstd(self, "17")
        generator = self.conf.get("tools.cmake.cmaketoolchain:generator", default="Ninja")
        if generator != "Ninja":
            raise ConanInvalidConfiguration("The integrated Windows SDK requires Ninja")

    def validate_build(self):
        if cross_building(self):
            raise ConanInvalidConfiguration("Cross-building the Windows SDK is not supported")

    def source(self):
        data = self._source_data
        get(self, data["url"], sha256=data["sha256"],
            destination="llvm-project", strip_root=True)

    def _source_path(self, name):
        exported = os.path.join(self.source_folder, name)
        if os.path.isdir(exported):
            return exported
        # Local `conan source/install/build` uses the checkout directly; cached
        # builds always use the immutable source export above.
        if name == "AdaptiveCpp":
            return str(Path(self.recipe_folder).parents[1])
        return os.path.join(self.recipe_folder, name)

    @property
    def _stage(self):
        return os.path.join(self.build_folder, "stage")

    def generate(self):
        acpp_source = self._source_path("AdaptiveCpp")
        cmake_source = load(self, os.path.join(acpp_source, "CMakeLists.txt"))
        parts = [re.search(rf"set\(ACPP_VERSION_{part}\s+(\d+)\)", cmake_source).group(1)
                 for part in ("MAJOR", "MINOR", "PATCH")]
        if ".".join(parts) != self._source_data["adaptivecpp_version"]:
            raise ConanInvalidConfiguration("The AdaptiveCpp checkout does not match the SDK version")
        tc = CMakeToolchain(self, generator="Ninja")
        tc.blocks["output_dirs"].values["package_folder"] = self._stage.replace("\\", "/")
        bootstrap = self.conf.get("user.adaptivecpp-llvm:bootstrap_compiler",
                                  default="clang-cl", check_type=str)
        tc.cache_variables.update({
            "CMAKE_INSTALL_PREFIX": self._stage.replace("\\", "/"),
            "CMAKE_C_COMPILER": bootstrap.replace("\\", "/"),
            "CMAKE_CXX_COMPILER": bootstrap.replace("\\", "/"),
            "ACPP_VERSION_SUFFIX": "",
        })
        tc.variables.update({
            "LLVM_EXTERNAL_PROJECTS": "AdaptiveCpp",
            "LLVM_EXTERNAL_ADAPTIVECPP_SOURCE_DIR": acpp_source.replace("\\", "/"),
            "LLVM_ADAPTIVECPP_LINK_INTO_TOOLS": True,
            "LLVM_ENABLE_PROJECTS": "clang;openmp;lld;compiler-rt",
            "LLVM_TARGETS_TO_BUILD": "X86;NVPTX",
            "LLVM_PARALLEL_LINK_JOBS": 1,
            "LLVM_INCLUDE_TESTS": False,
            "LLVM_INCLUDE_EXAMPLES": False,
            "LLVM_INCLUDE_BENCHMARKS": False,
            "LLVM_ENABLE_LIBXML2": False,
            "LLVM_ENABLE_ZLIB": False,
            "LLVM_ENABLE_ZSTD": False,
            "LLVM_INSTALL_TOOLCHAIN_ONLY": True,
            "LLVM_TOOLCHAIN_TOOLS": "clang;clang++;clang-cl;llc;opt;lld;lld-link;llvm-link;llvm-ar;llvm-readobj;llvm-dlltool;llvm-lib;llvm-rc;llvm-mt",
            "CLANG_ENABLE_ARCMT": False,
            "CLANG_ENABLE_STATIC_ANALYZER": False,
            "OPENMP_ENABLE_LIBOMPTARGET": False,
            "COMPILER_RT_BUILD_SANITIZERS": False,
            "COMPILER_RT_BUILD_XRAY": False,
            "COMPILER_RT_BUILD_LIBFUZZER": False,
            "COMPILER_RT_BUILD_PROFILE": False,
            "COMPILER_RT_INCLUDE_TESTS": False,
            "ACPP_COMPILER_FEATURE_PROFILE": "full",
            "ACPP_CUDA_DRIVER_ONLY": bool(self.options.with_cuda),
            "ACPP_EMBED_CUDA_LIBDEVICE": bool(self.options.with_cuda),
            "WITH_CUDA_BACKEND": bool(self.options.with_cuda),
            "WITH_ROCM_BACKEND": False,
            "WITH_OPENCL_BACKEND": False,
            "WITH_LEVEL_ZERO_BACKEND": False,
            "WITH_VULKAN_BACKEND": False,
            "WITH_METAL_BACKEND": False,
            "ACPP_ALLOW_DOWNLOADS": False,
            "ACPP_BUILD_CUDA_DRIVER_TESTS": False,
            "ACPP_BUILD_CUDA_PTX_TESTS": bool(self.options.with_cuda) and not self.conf.get(
                "tools.build:skip_test", default=False, check_type=bool),
            "ACPP_HOST_FORCE_MCPU_TARGET": "native",
            "ACPP_FILESYSTEM_SEARCH_OPTIONS": "Final",
            "ACPP_CONFIG_FILE_GLOBAL_INSTALLATION": False,
            "DEFAULT_TARGETS": "generic",
        })
        tc.generate()

    def _cmake(self, *args):
        executable = self.conf.get("tools.cmake:cmake_program", default="cmake")
        self.run(cmd_args_to_string(self, [executable, *args]))

    def build(self):
        cmake = CMake(self)
        cmake.configure(build_script_folder="llvm-project/llvm")
        cmake.build()
        if self.options.with_cuda and not self.conf.get(
                "tools.build:skip_test", default=False, check_type=bool):
            self.run(cmd_args_to_string(self, ["ctest", "--test-dir",
                     os.path.join(self.build_folder, "tools", "AdaptiveCpp"),
                     "-C", "Release", "--output-on-failure", "--no-tests=error"]))
        # One install tree feeds both Conan and the installer, including LLVM's
        # install components that are outside AdaptiveCpp's Runtime/Development.
        shutil.rmtree(self._stage, ignore_errors=True)
        self._cmake("--install", self.build_folder, "--config", "Release", "--prefix", self._stage)
        copy(self, "LICENSE.TXT", os.path.join(self.source_folder, "llvm-project", "llvm"),
             os.path.join(self._stage, "licenses", "llvm"))
        copy(self, "LICENSE", self._source_path("AdaptiveCpp"),
             os.path.join(self._stage, "licenses", "AdaptiveCpp"))
        if self.options.with_cuda:
            copy(self, "NOTICE.txt", os.path.join(self._source_path("AdaptiveCpp"), "third-party", "nvidia"),
                 os.path.join(self._stage, "licenses", "nvidia"))
        copy(self, "README-WINDOWS.txt", self._source_path("packaging"), self._stage)
        self._cmake("-S", self._source_path("packaging"),
                    "-B", os.path.join(self.build_folder, "installer"),
                    f"-DACPP_SDK_STAGE={self._stage}", f"-DACPP_SDK_VERSION={self.version}",
                    f"-DACPP_VERSION={self._source_data['adaptivecpp_version']}",
                    f"-DACPP_LLVM_VERSION={self._source_data['llvm_version']}",
                    f"-DACPP_SDK_WITH_CUDA={'ON' if self.options.with_cuda else 'OFF'}")

    def package(self):
        if not os.path.isfile(os.path.join(self._stage, "bin", "clang.exe")):
            raise ConanException("SDK stage is missing; run conan build before export-pkg")
        copy(self, "*", self._stage, self.package_folder)

    def package_info(self):
        self.cpp_info.set_property("cmake_find_mode", "none")
        self.cpp_info.set_property("cmake_file_name", "AdaptiveCpp")
        self.cpp_info.builddirs = ["lib/cmake/AdaptiveCpp"]
        self.cpp_info.includedirs = ["include/AdaptiveCpp"]
        for name, library in (("common", "acpp-common"), ("runtime", "acpp-rt")):
            component = self.cpp_info.components[name]
            component.libs = [library]
            component.includedirs = ["include/AdaptiveCpp"]
            component.builddirs = ["lib/cmake/AdaptiveCpp"]
            component.set_property("cmake_target_name", f"AdaptiveCpp::{library}")
        self.cpp_info.components["runtime"].requires = ["common"]
        compiler = os.path.join(self.package_folder, "bin", "clang.exe")
        self.conf_info.define("tools.build:compiler_executables", {"c": compiler, "cpp": compiler})
