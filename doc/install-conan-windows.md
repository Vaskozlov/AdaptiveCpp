# Windows SDK with Conan 2 and NSIS

`recipes/adaptivecpp-llvm` builds LLVM and AdaptiveCpp together, with the
AdaptiveCpp compiler passes linked into LLVM's tools. This follows the
repository's [integrated build](installing.md#building-an-llvm-toolchain-with-adaptivecpp-linked-in-necessary-for-windows)
and supports `generic` CPU JIT compilation and accelerated OpenMP. The default
variant also provides the NVIDIA driver backend and embedded libdevice, without
requiring the CUDA toolkit on the build or execution machine.

The package is `adaptivecpp-llvm/25.10.0-llvm19.1.7`. Its version identifies
both source releases; the Conan recipe revision identifies this exact
AdaptiveCpp checkout. LLVM's release archive and SHA-256 are pinned in
`conandata.yml`. Changing LLVM requires a new SDK version and matching source
entry, rather than a settings-dependent download in `source()`.

The initial profile targets **native Windows x86_64, Release, Clang 19,
VS 2022/v143, dynamic Microsoft runtime (/MD)**. Other architectures, Debug,
static CRT, different compiler majors and cross-builds are rejected explicitly.
The [Linux/macOS recipe](install-conan.md) keeps its external LLVM design and
CPack's Runtime/Development DEBs.

## Prerequisites

Use a Visual Studio 2022 Developer PowerShell with the x64 C++ Build Tools and
Windows SDK available. Install bootstrap LLVM/Clang **19.1.7**, Python 3,
Conan **2.8 or newer**, CMake **3.23 or newer**, and Ninja. Building an integrated
LLVM SDK needs substantial disk space and time; use short build/cache paths.
NSIS is needed only for `.exe` installer generation.

The native CI pins Conan 2.34.0, CMake 3.31.6, Ninja 1.12.1, and NSIS 3.11.
For example, after installing VS Build Tools and LLVM:

```powershell
python -m pip install conan==2.34.0 cmake==3.31.6 ninja==1.12.1
choco install nsis --version=3.11 --yes --no-progress
$env:PATH = "${env:ProgramFiles(x86)}\NSIS;$env:PATH"
$env:CONAN_HOME = 'C:\acpp-conan'
```

`clang-cl`, `link`, and `rc` must resolve in this shell. The profile does not
hardcode a compiler executable: the SDK build uses bootstrap `clang-cl`, while
consumers use the packaged compiler through the tool requirement. A custom
bootstrap location can be supplied with
`-c user.adaptivecpp-llvm:bootstrap_compiler=C:/LLVM/bin/clang-cl.exe`.

## Build once, produce Conan and CPack outputs

Run from the repository root:

```powershell
$recipe = (Resolve-Path 'recipes/adaptivecpp-llvm').Path
$profile = Join-Path $recipe 'profiles/windows-x64-clang19'
$output = 'C:/acpp-sdk'

# This is the explicit network/source-acquisition step.
conan source $recipe

conan install $recipe -of $output -pr:h $profile -pr:b $profile --no-remote
conan build $recipe -of $output -pr:h $profile -pr:b $profile --no-remote
conan export-pkg $recipe -of $output -pr:h $profile -pr:b $profile --no-remote

$cpack = "$output/build/llvm-sdk/Release/installer/CPackConfig.cmake"
cpack --config $cpack -G NSIS -B "$output/artifacts"
cpack --config $cpack -G ZIP -B "$output/artifacts"
```

`conan source` places LLVM under `recipes/adaptivecpp-llvm/sources/llvm-project`;
it does not accept an output-folder argument. Subsequent configuration and
compilation disable AdaptiveCpp downloads. All package resolution above uses
the local cache. To use an internal LLVM mirror, update the source URL while
retaining the verified checksum in your recipe revision.

The build installs into `$output/build/llvm-sdk/Release/stage`. Conan copies
that complete tree, and the separate CPack project packages that same tree.
It includes Clang and resource headers, OpenMP, LLVM JIT tools, AdaptiveCpp
headers, runtime plugins, native CMake integration, bitcode, Windows host JIT
import libraries, command launchers and license notices. Packaging validates
the required files before producing an installer. LLVM development archives
and its source tree are not part of the distributed toolchain.

The [CPack NSIS generator](https://cmake.org/cmake/help/latest/cpack_gen/nsis.html)
produces a monolithic x64 SDK installer; ZIP provides the same portable
payload. The installer supports selecting PATH integration and uninstalling.
SDK/LLVM version and CUDA/CPU variant are included in its filename, install
directory and registry identity. Python, VS Build Tools/Windows SDK and the
Microsoft C++ runtime remain external prerequisites; the installer does not
fetch or silently install them. NSIS generation uses the existing CMake/CPack
tools, independently of Conan's remote distribution.

For a CPU-only SDK, add `-o:h '&:with_cuda=False'` to **each** local
install/build/export-pkg command. Use a fresh output directory when changing
options or profiles. PTX translation tests run by default for CUDA builds,
without requiring a GPU or driver. `-c tools.build:skip_test=True` skips those
build-time tests.

For Conan-only creation, use:

```powershell
conan create $recipe -pr:h $profile -pr:b $profile --no-remote
```

Conan then acquires the pinned LLVM source in its cache, builds, packages and
runs `test_package`. To retain a separate build tree and installer artifacts,
use the local workflow above. To distribute the cached recipe and binaries:

```powershell
conan upload 'adaptivecpp-llvm/25.10.0-llvm19.1.7:*' -r company --confirm
```

## Use the SDK as a dependency and compiler

Applications need a regular requirement for the target runtime and a tool
requirement for the compiler used during their build:

```python
from conan import ConanFile
from conan.tools.cmake import CMake, cmake_layout

class Application(ConanFile):
    settings = "os", "arch", "compiler", "build_type"
    requires = "adaptivecpp-llvm/25.10.0-llvm19.1.7"
    generators = "CMakeDeps", "CMakeToolchain", "VirtualRunEnv"

    def build_requirements(self):
        self.tool_requires("adaptivecpp-llvm/25.10.0-llvm19.1.7",
                           package_id_mode="full_mode")

    def layout(self):
        cmake_layout(self)

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
```

Use the same SDK profile in both contexts:

```powershell
conan install . -pr:h $profile -pr:b $profile --no-remote
conan build . -pr:h $profile -pr:b $profile --no-remote
```

The tool requirement supplies `bin/clang.exe` through Conan's compiler
configuration. The regular requirement exposes the installed native CMake
package and runtime DLLs. Keep the normal CMake API:

```cmake
cmake_minimum_required(VERSION 3.23)
project(Application LANGUAGES CXX)
find_package(AdaptiveCpp 25.10 CONFIG REQUIRED)
add_executable(app main.cpp)
target_compile_features(app PRIVATE cxx_std_17)
add_sycl_to_target(TARGET app)
```

`cmake_find_mode=none` preserves `add_sycl_to_target()` and its compiler
launcher. Consumers track the complete SDK variant/revision through
`full_mode`; pin revisions with a Conan lockfile for releases. Match the
host/build SDK options, especially when selecting the CPU-only variant:
`-o:h 'adaptivecpp-llvm/*:with_cuda=False'`
and `-o:b 'adaptivecpp-llvm/*:with_cuda=False'`.

For an SDK installed through NSIS or extracted from ZIP, set
`CMAKE_PREFIX_PATH` to its prefix and `CMAKE_CXX_COMPILER` to its
`bin/clang.exe`. Add its `bin` directory to PATH for runtime DLLs. `acpp.cmd`,
`syclcc.cmd` and `syclcc-clang.cmd` invoke Python from PATH; `ACPP_PYTHON` may
name an explicit Python executable. CMake's Windows launcher quotes paths so
that installation under `Program Files` works.

Generic applications need the SDK's runtime plugins, LLVM JIT executables,
bitcode and Windows import libraries at execution time. Preserve those
resources together when deploying. NVIDIA execution additionally needs a
compatible GPU and the system driver's `nvcuda.dll`; CPU execution remains
available without an NVIDIA driver.

## Validate on Windows

The native workflow is `.github/workflows/conan-windows.yml`. The same check
can be run locally in a prepared Developer PowerShell:

```powershell
./tests/packaging/check_windows_sdk.ps1 -OutputDirectory C:/acpp-sdk
```

It builds and tests the SDK, consumes the Conan package, generates NSIS/ZIP
and a Conan cache archive, installs the NSIS payload under a path containing
spaces, compiles/runs CPU SYCL programs through CMake and `acpp.cmd`, and
uninstalls. The CUDA variant also tests embedded-libdevice PTX translation for
several requested GPU architectures without GPU hardware. Actual NVIDIA GPU
execution requires a separate hardware runner.

CI adds `-BlockBuildNetwork` after source acquisition. On an isolated Windows
machine, that switch requires an elevated shell and temporarily blocks outbound
connections from the resolved build/download tools with Windows Firewall;
rules are removed in `finally`. This checks those programs' network access;
it does not disconnect the entire runner. Source/tool provisioning is an
explicit earlier stage.
