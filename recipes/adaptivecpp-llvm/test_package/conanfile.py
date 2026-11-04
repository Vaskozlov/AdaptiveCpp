import os

from conan import ConanFile
from conan.tools.build import can_run, cmd_args_to_string
from conan.tools.cmake import CMake, cmake_layout
from conan.tools.env import Environment


class AdaptiveCppSDKTest(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    generators = "CMakeDeps", "CMakeToolchain", "VirtualRunEnv"
    test_type = "explicit"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def build_requirements(self):
        self.tool_requires(self.tested_reference_str, package_id_mode="full_mode")

    def layout(self):
        cmake_layout(self)

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if not can_run(self):
            return
        env = Environment()
        env.define("ACPP_APPDB_DIR", os.path.join(self.build_folder, "appdb"))
        env.define("OMP_NUM_THREADS", "2")
        with env.vars(self).apply():
            self.run("acpp --version", env="conanrun")
            executable = os.path.join(self.cpp.build.bindirs[0], "sdk_test.exe")
            self.run(f'"{executable}"', env="conanrun")
            # Exercise the .cmd entry point as well as native CMake integration.
            omp_executable = os.path.join(self.build_folder, "sdk_test_omp.exe")
            self.run(cmd_args_to_string(self, ["acpp", "--acpp-targets=omp", "-O2",
                     os.path.join(self.source_folder, "main.cpp"), "-o", omp_executable]),
                     env=["conanbuild", "conanrun"])
            self.run(f'"{omp_executable}"', env="conanrun")
