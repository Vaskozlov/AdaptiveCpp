# Building and distributing AdaptiveCpp with Conan 2

The repository's `conanfile.py` builds a native, full-featured AdaptiveCpp
compiler and runtime. NVIDIA support uses the driver API and the bundled
`cuda.h` and embedded libdevice; no CUDA toolkit or NVIDIA driver is needed
on the build machine. Set `with_cuda=False` for a CPU-only generic compiler.
Other GPU backends are disabled explicitly so that the package contents do
not depend on SDK auto-detection.

Conan configures and builds the existing CMake project and packages its
ordinary installation. It does not replace the install rules, native CMake
integration, Runtime/Development components, or CPack. There is no Conan
bootstrap or dependency download hidden inside CMake.

## Prerequisites and a reproducible profile

Use Conan **2.8 or newer**, CMake **3.23 or newer** for preset support, a C++17
compiler, Python 3, and a supported LLVM/Clang **15–21 release** with development
headers, OpenMP, the LLVM host and NVPTX targets, `llvm-link`, `llc`, `opt`, and
LLD. These are system prerequisites, supplied by your build image or toolchain
profile. The recipe does not install system packages or fetch/build LLVM.
Linux and macOS native builds are supported. Cross-building is rejected with
an explanation rather than using target LLVM executables on the build host.

For example, prepare a Debian 13 machine with LLVM 19:

```sh
sudo apt-get install build-essential cmake ninja-build python3 python3-venv \
  clang-19 llvm-19-dev libclang-19-dev libclang-cpp19-dev lld-19 libomp-19-dev \
  dpkg-dev file
python3 -m venv .venv
. .venv/bin/activate
python -m pip install 'conan>=2.8,<3'
```

Save an explicit profile as `linux-llvm19` outside the source tree:

```ini
[settings]
os=Linux
arch=x86_64
compiler=clang
compiler.version=19
compiler.libcxx=libstdc++11
compiler.cppstd=17
build_type=Release

[options]
adaptivecpp/*:llvm_version=19.1.7

[conf]
tools.build:compiler_executables={"c": "/usr/bin/clang-19", "cpp": "/usr/bin/clang++-19"}
tools.cmake.cmaketoolchain:generator=Ninja
tools.build:jobs=4
user.adaptivecpp:llvm_dir=/usr/lib/llvm-19/lib/cmake/llvm
```

Use `arch=armv8` on AArch64. Check the actual installed release with
`/usr/lib/llvm-19/bin/llvm-config --version`. `llvm_version` is required and
must contain the full version: CMake checks the discovered LLVM version against
it. `user.adaptivecpp:llvm_dir` is a machine-specific discovery hint, not part
of the package identity. If omitted, normal CMake LLVM discovery is used, with
the same version check. The compiler in `[settings]` and
`tools.build:compiler_executables` must describe the same compiler.

For macOS, use `os=Macos`, the appropriate architecture, `compiler.libcxx=libc++`,
and paths to a supported LLVM installation. AppleClang can build the runtime,
but the AdaptiveCpp compiler plugin still requires the supported upstream LLVM
and Clang development libraries. Set OpenMP/LLD hints through
`tools.cmake.cmaketoolchain:extra_variables` if the installation needs them.

## Create a Conan package

```sh
conan create . -pr:h /path/to/linux-llvm19 -pr:b /path/to/linux-llvm19 --no-remote
```

The package version comes from `CMakeLists.txt`. Conan recipe/source revisions
identify changes within that version. Source exports include the bundled
NVIDIA inputs, so rebuilding a downloaded recipe does not need a Git checkout,
Git submodules, or additional NVIDIA downloads. An explicitly empty CMake
version suffix keeps local Git branch names and dirty state out of Conan builds.

| Option | Default | Meaning |
| --- | --- | --- |
| `llvm_version` | Required | Exact external LLVM release, included in the binary package ID. |
| `with_cuda` | `True` | Toolkit-free NVIDIA driver backend, PTX translator, and embedded libdevice. `False` keeps the full CPU generic compiler. |
| `package_llvm_tools` | `True` | Install the runtime's copies of `llc`, `opt`, and the LLVM linker. `False` requires matching tools at the configured paths on the execution machine. |

All variants build shared runtime libraries; there is no ineffective `shared`
option. OS, architecture, compiler, C++ library, build type, and the options
above participate in Conan's binary identity. GPU-independent backend and PTX
tests run during NVIDIA builds. `-c tools.build:skip_test=True` skips those
build-time tests. `test_package` compiles and runs a small SYCL program through
the installed compiler and native CMake integration, selecting a CPU explicitly.

The recipe uses Conan's [`full_mode`](https://docs.conan.io/2/reference/binary_model/dependencies.html)
for consumers linking the shared runtime:
an application package must track the exact AdaptiveCpp recipe revision and
binary variant used for its headers and generated kernels.

The package includes both Runtime and Development components, licenses,
compiler configuration, backend plugins, JIT libraries, bitcode and CMake
integration. Runtime plugins are loaded dynamically; they are not all added to
consumers' link lines.

The LLVM license notice is copied alongside bundled tools. For a custom LLVM
layout, set `ACPP_LLVM_LICENSE_FILE` through
`tools.cmake.cmaketoolchain:extra_variables` if automatic discovery cannot find
it. On macOS, installed copies of the tools receive the system LLVM library
search paths and a new ad-hoc signature.

LLVM/Clang and OpenMP remain **external system dependencies**. Bundling the three
LLVM tools does not bundle LLVM shared libraries, Clang, its headers or Python.
Install compatible system packages on consumers and execution machines. Native
system LLVM paths are retained; use a matching installation layout, or configure
AdaptiveCpp's compiler/tool overrides when moving to another layout. The
Conan package is not a complete relocatable LLVM SDK.

An exact LLVM version does not describe distribution patches, C++ runtime or
glibc compatibility. Use separate profiles and binary channels for incompatible
system images, for example `adaptivecpp/25.10.0@debian13/stable`. Pin the build
image and Conan version in release infrastructure. Publish the recipe and its
binaries to your own Conan remote:

```sh
conan create . --user=debian13 --channel=stable \
  -pr:h /path/to/linux-llvm19 -pr:b /path/to/linux-llvm19 --no-remote
conan upload 'adaptivecpp/25.10.0@debian13/stable:*' -r company --confirm
```

## Use the native CMake integration

A consumer `conanfile.py` can declare:

```python
from conan import ConanFile
from conan.tools.cmake import cmake_layout

class Application(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    requires = "adaptivecpp/25.10.0"
    default_options = {"adaptivecpp/*:llvm_version": "19.1.7"}
    generators = "CMakeToolchain", "CMakeDeps", "VirtualRunEnv"

    def layout(self):
        cmake_layout(self)
```

Keep the normal AdaptiveCpp CMake API:

```cmake
find_package(AdaptiveCpp CONFIG REQUIRED)
add_executable(app main.cpp)
target_compile_features(app PRIVATE cxx_std_17)
add_sycl_to_target(TARGET app)
```

Conan exposes the installed CMake directory and sets `cmake_find_mode=none`.
This preserves `add_sycl_to_target()`, its compiler launcher, and the
`AdaptiveCpp::acpp-rt` target. A replacement generated by CMakeDeps would omit
the compiler integration. `test_package` is a complete working consumer example.
Generate and use the consumer's CMake presets with `conan install .` and
`cmake --list-presets`. For release consumers, use Conan lockfiles to pin recipe
revisions and retain the matching profiles and build image alongside the lockfile.

The package can also be a `tool_requires` when a native build needs `acpp` on
its build environment's PATH. Applications that link the AdaptiveCpp runtime
should use a regular `requires`, so Conan tracks the target runtime dependency.
If using it solely as a compiler tool requirement, declare
`self.tool_requires("adaptivecpp/25.10.0", package_id_mode="full_mode")`
to make the tool version and binary variant affect your application's identity.

## Use Conan to drive CMake, then create DEBs with CPack

The local workflow keeps a reviewable CMake build tree:

```sh
conan install . -pr:h /path/to/linux-llvm19 -pr:b /path/to/linux-llvm19 --no-remote
conan build . -pr:h /path/to/linux-llvm19 -pr:b /path/to/linux-llvm19
cpack --config build/conan/Release/CPackConfig.cmake \
  -G DEB -B build/conan/packages
```

The path above assumes a single-configuration generator and `Release`.
`cmake --list-presets` shows the generated presets if you prefer direct CMake
commands after `conan install`. Conan-generated builds default the CPack install
prefix to `/usr`; the Conan cache package still uses its own install prefix.
Use a fresh local build directory when switching profiles or package options.

CPack still produces `adaptivecpp-runtime` and `adaptivecpp-dev`, with the
existing component split and Debian dependency detection. It does not package
the Conan cache. `dpkg-dev`, `file`, and matching distro Clang/OpenMP packages
are needed for DEBs. Packaging may be customized with CMake variables such as
`CPACK_DEBIAN_DEVELOPMENT_PACKAGE_DEPENDS` through
`tools.cmake.cmaketoolchain:extra_variables`. This does not require an apt
repository. See [the driver-only packaging guide](install-cuda-driver.md) for
component contents and direct CMake/CPack commands.

## Verify an offline build

`ACPP_CUDA_DRIVER_ONLY=ON` defaults other GPU backends to OFF and
`ACPP_ALLOW_DOWNLOADS` to OFF. Explicitly enabling a backend that needs fetched
sources fails before acquisition. Existing non-driver builds retain their
download behavior; combined configurations may opt in with
`ACPP_ALLOW_DOWNLOADS=ON`. The Conan recipe always disables downloads.
`FETCHCONTENT_FULLY_DISCONNECTED` alone would not cover the build-time
LLVM-SPIRV ExternalProject, so it is not used as proof of an offline build.

Reproduce the CI check on a machine with Docker:

```sh
docker build -t acpp-conan-check tests/packaging
mkdir -p build-packaging
docker run --rm --network=none \
  -v "$PWD:/src:ro" -v "$PWD/build-packaging:/output" \
  acpp-conan-check sh /src/tests/packaging/check_driver_offline.sh
```

The image setup acquires the system prerequisites and Conan. The second
command runs with **no network** and a fresh Conan cache: it checks the recipe,
creates and consumes a Conan package, performs a separate CMake driver-only
build, runs the driver/PTX tests, checks the executed CMake trace for download
operations, and generates both DEBs from the Conan build tree. Neither an
NVIDIA driver nor a CUDA toolkit is installed. Artifacts and the trace appear
in `build-packaging/`.
