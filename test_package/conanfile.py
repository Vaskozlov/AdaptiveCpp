import os

from conan import ConanFile
from conan.tools.build import can_run
from conan.tools.cmake import CMake, cmake_layout
from conan.tools.env import Environment


class AdaptiveCppTestConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    generators = "CMakeDeps", "CMakeToolchain", "VirtualRunEnv"
    test_type = "explicit"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def layout(self):
        cmake_layout(self)

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if can_run(self):
            env = Environment()
            env.define("ACPP_APPDB_DIR", os.path.join(self.build_folder, "appdb"))
            env.define("OMP_NUM_THREADS", "2")
            with env.vars(self).apply():
                self.run("acpp --version", env="conanrun")
                executable = os.path.join(self.cpp.build.bindirs[0], "package_test")
                self.run(f'"{executable}"', env="conanrun")
