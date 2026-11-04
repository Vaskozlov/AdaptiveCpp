"""Conan 2 packaging for native generic/CPU and toolkit-free NVIDIA builds.

LLVM/Clang and OpenMP are supplied by the build and deployment environment.
See doc/install-conan.md for profiles, binary compatibility and CPack usage.
"""

import os
import re

from conan import ConanFile
from conan.errors import ConanException, ConanInvalidConfiguration
from conan.tools.build import check_min_cppstd, cross_building
from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout
from conan.tools.env import Environment
from conan.tools.files import copy, load


class AdaptiveCppConan(ConanFile):
    name = "adaptivecpp"
    description = "AdaptiveCpp SYCL compiler and runtime with generic JIT compilation"
    homepage = "https://adaptivecpp.github.io"
    url = "https://github.com/AdaptiveCpp/AdaptiveCpp"
    license = "BSD-2-Clause", "LicenseRef-NVIDIA-CUDA", "Apache-2.0 WITH LLVM-exception"
    topics = "sycl", "heterogeneous-computing", "cuda", "compiler"
    package_type = "shared-library"
    # Headers and compiler-generated kernels are tied to this build even when
    # the application links the runtime dynamically.
    package_id_non_embed_mode = "full_mode"
    required_conan_version = ">=2.8"

    settings = "os", "arch", "compiler", "build_type"
    options = {
        "with_cuda": [True, False],
        "llvm_version": [None, "ANY"],
        "package_llvm_tools": [True, False],
    }
    default_options = {
        "with_cuda": True,
        "llvm_version": None,
        "package_llvm_tools": True,
    }

    # set_version() also runs when loading an exported recipe from the cache.
    exports = "CMakeLists.txt"
    exports_sources = (
        "CMakeLists.txt", "LICENSE", "bin/acpp", "cmake/*", "include/*",
        "src/*", "third-party/nvidia/*", "tests/cuda_driver/*",
    )

    def set_version(self):
        if not self.version:
            cmake = load(self, os.path.join(self.recipe_folder, "CMakeLists.txt"))
            parts = [re.search(rf"set\(ACPP_VERSION_{part}\s+(\d+)\)", cmake).group(1)
                     for part in ("MAJOR", "MINOR", "PATCH")]
            self.version = ".".join(parts)

    def layout(self):
        cmake_layout(self, build_folder="build/conan")

    def validate(self):
        if self.settings.os not in ("Linux", "Macos"):
            raise ConanInvalidConfiguration("This recipe supports native Linux and macOS builds")
        llvm_version = str(self.options.llvm_version)
        if not re.fullmatch(r"\d+\.\d+\.\d+", llvm_version):
            raise ConanInvalidConfiguration(
                "Set llvm_version to the exact installed LLVM release, e.g. "
                "-o '&:llvm_version=19.1.7'. It is part of the binary package ID."
            )
        if not 15 <= int(llvm_version.split(".")[0]) <= 21:
            raise ConanInvalidConfiguration(
                "The full compiler profile requires supported LLVM 15 through 21"
            )
        if self.settings.compiler.get_safe("cppstd"):
            check_min_cppstd(self, "17")

    def validate_build(self):
        if cross_building(self):
            raise ConanInvalidConfiguration(
                "Cross-building this recipe is not supported: target LLVM libraries "
                "and matching build-host bitcode tools must be configured separately"
            )

    @property
    def _build_driver_tests(self):
        return bool(self.options.with_cuda) and not self.conf.get(
            "tools.build:skip_test", default=False, check_type=bool
        )

    def generate(self):
        tc = CMakeToolchain(self)
        tc.variables.update({
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
            "ACPP_EXPECTED_LLVM_VERSION": str(self.options.llvm_version),
            "ACPP_PACKAGE_LLVM_TOOLS": bool(self.options.package_llvm_tools),
            "ACPP_CONFIG_FILE_GLOBAL_INSTALLATION": False,
            "ACPP_FILESYSTEM_SEARCH_OPTIONS": "Final",
            "ACPP_BUILD_CUDA_DRIVER_TESTS": self._build_driver_tests,
            "DEFAULT_TARGETS": "generic",
            "CPACK_PACKAGING_INSTALL_PREFIX": "/usr",
        })
        # Version discovery precedes project(), hence toolchain loading, in CMake.
        tc.cache_variables["ACPP_VERSION_SUFFIX"] = ""
        llvm_dir = self.conf.get("user.adaptivecpp:llvm_dir", check_type=str)
        if llvm_dir:
            tc.variables["LLVM_DIR"] = llvm_dir.replace("\\", "/")
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
        if self._build_driver_tests:
            env = Environment()
            env.define("CTEST_OUTPUT_ON_FAILURE", "1")
            with env.vars(self).apply():
                cmake.test()

    def package(self):
        # One authoritative install layout, shared with ordinary CMake and CPack.
        CMake(self).install()
        copy(self, "LICENSE", self.source_folder, os.path.join(self.package_folder, "licenses"))
        license_dir = os.path.join(self.package_folder, "share", "licenses", "AdaptiveCpp")
        if self.options.package_llvm_tools:
            if not os.path.isfile(os.path.join(license_dir, "LLVM-LICENSE.txt")):
                raise ConanException(
                    "Bundled LLVM tools require their license notice. Set ACPP_LLVM_LICENSE_FILE "
                    "through tools.cmake.cmaketoolchain:extra_variables."
                )
            copy(self, "LLVM-LICENSE.txt", license_dir, os.path.join(self.package_folder, "licenses"))
        if self.options.with_cuda:
            copy(self, "NOTICE.txt", os.path.join(self.source_folder, "third-party", "nvidia"),
                 os.path.join(self.package_folder, "licenses", "nvidia"))

    def package_info(self):
        # Generated CMakeDeps targets cannot replace add_sycl_to_target(), which
        # invokes the compiler driver. Use the installed native CMake integration.
        self.cpp_info.set_property("cmake_find_mode", "none")
        self.cpp_info.set_property("cmake_file_name", "AdaptiveCpp")
        self.cpp_info.builddirs = ["lib/cmake/AdaptiveCpp"]
        self.cpp_info.includedirs = ["include/AdaptiveCpp"]
        common = self.cpp_info.components["common"]
        common.libs = ["acpp-common"]
        common.includedirs = ["include/AdaptiveCpp"]
        common.builddirs = ["lib/cmake/AdaptiveCpp"]
        common.set_property("cmake_target_name", "AdaptiveCpp::acpp-common")
        runtime = self.cpp_info.components["runtime"]
        runtime.libs = ["acpp-rt"]
        runtime.includedirs = ["include/AdaptiveCpp"]
        runtime.builddirs = ["lib/cmake/AdaptiveCpp"]
        runtime.requires = ["common"]
        runtime.set_property("cmake_target_name", "AdaptiveCpp::acpp-rt")
