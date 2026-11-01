# NVIDIA driver API builds without the CUDA toolkit

AdaptiveCpp includes `cuda.h` and `libdevice.10.bc` in `third-party/nvidia`
and uses them by default for driver-only builds. Neither nvcc, CUDA runtime
headers, libcudart, nor an installed NVIDIA driver is needed on the build machine. LLVM/Clang
development files, the NVPTX LLVM target, LLVM tools and OpenMP are still needed.
Use a supported LLVM version as for an ordinary full AdaptiveCpp installation.
The bundled driver header targets CUDA 11.8. No additional NVIDIA files or
network downloads are needed to build this configuration.

On the execution machine, the backend loads the system NVIDIA driver's
`libcuda.so.1`. An absent driver or an incompatible driver exposes no CUDA
devices; OpenMP remains available. Driver symbols are resolved with the ABI
versions selected by `cuda.h`, so a newer header may require a newer driver.
The driver must also support the PTX version generated for the GPU.

`generic` compiles GPU code through LLVM and loads the resulting PTX with the
driver API. `omp` targets the CPU. Legacy compiler targets such as `cuda:sm_80`
and `cuda-nvcxx` require toolkit facilities and are rejected in a driver-only
build. Existing toolkit builds remain available when `ACPP_CUDA_DRIVER_ONLY`
is disabled.

## Configure and build on Linux

For example, with LLVM 19 installed from distribution packages:

```sh
# Debian 13 / LLVM 19 build and packaging prerequisites:
sudo apt-get install build-essential cmake ninja-build clang-19 llvm-19-dev \
  libclang-19-dev libclang-cpp19-dev lld-19 libomp-19-dev dpkg-dev file

cmake -S . -B build-driver -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr \
  -DCMAKE_C_COMPILER=clang-19 \
  -DCMAKE_CXX_COMPILER=clang++-19 \
  -DLLVM_DIR=/usr/lib/llvm-19/lib/cmake/llvm \
  -DACPP_COMPILER_FEATURE_PROFILE=full \
  -DACPP_CUDA_DRIVER_ONLY=ON \
  -DACPP_EMBED_CUDA_LIBDEVICE=ON \
  -DWITH_CUDA_BACKEND=ON \
  -DWITH_ROCM_BACKEND=OFF \
  -DWITH_OPENCL_BACKEND=OFF \
  -DWITH_LEVEL_ZERO_BACKEND=OFF \
  -DWITH_VULKAN_BACKEND=OFF \
  -DWITH_METAL_BACKEND=OFF \
  -DDEFAULT_TARGETS=generic \
  -DACPP_BUILD_CUDA_DRIVER_TESTS=ON
cmake --build build-driver --parallel
ctest --test-dir build-driver --output-on-failure
```

The source checkout and exported binary-capable patch contain both NVIDIA
build inputs. Their checksums and licensing notices are recorded in
[`third-party/nvidia/README.md`](../third-party/nvidia/README.md). The original
NVIDIA notices are preserved and installed with the runtime package; these
files retain their NVIDIA licensing.

To use different files, set `ACPP_CUDA_DRIVER_INCLUDE_DIR` to the directory
containing `cuda.h`, and `ACPP_CUDA_LIBDEVICE` to a bitcode file. Alternatively,
`CUDA_DEVICE_LIBS_PATH` can select a bitcode directory when no explicit bitcode
file is set. Use a fresh build directory or clear an earlier cached
`ACPP_CUDA_LIBDEVICE` before switching to the directory option.

Embedding places the libdevice bytes inside `llvm-to-ptx`; the JIT then links them directly from
memory. The source bitcode file and its original directory are not needed when
executing compiled applications. Changing the input bitcode rebuilds the
embedded data and library.

`ACPP_EMBED_CUDA_LIBDEVICE` defaults to ON for driver-only builds.
If embedding is explicitly disabled, the existing runtime file discovery is
used. Do not disable embedding when a runtime filesystem dependency on
libdevice is undesirable.

The tests use a mock driver to check context rebinding, device properties,
allocation types, events, stream priority, and copies with offsets and pitches.
They also test absent drivers, missing symbols, and PTX generation using a
libdevice math function through the embedded library. They do not replace testing
kernel execution on an NVIDIA GPU.

## Build DEB packages with CPack

Install `dpkg-dev` and `file` on the Linux packaging machine, then run:

```sh
cpack --config build-driver/CPackConfig.cmake -G DEB -B build-driver/packages
```

The two components are:

| Package | Contents |
| --- | --- |
| `adaptivecpp-runtime` | AdaptiveCpp shared libraries, enabled runtime backend plugins, JIT translator libraries, full builtin bitcode libraries, and LLVM tools needed by generic applications. Embedded libdevice is part of the PTX translator. |
| `adaptivecpp-dev` | `acpp` compiler driver and aliases, compiler plugin, headers, CMake integration, compiler configuration, and developer tools. Depends on the matching runtime package. |

The development package uses the matching distribution Clang and OpenMP
development packages; it does not bundle a complete Clang installation.
`dpkg-shlibdeps` determines shared-library dependencies such as LLVM, OpenMP and
the C++ runtime. Those dependencies are installed by the package manager.
The NVIDIA driver is provided by the execution environment, allowing the same
runtime package to be installed on CPU-only machines.

For distributions with different Clang/OpenMP package names, override
`CPACK_DEBIAN_DEVELOPMENT_PACKAGE_DEPENDS` at configuration time. Ordinary
full installs contain both components. They can also be staged individually:

```sh
DESTDIR=/tmp/acpp-runtime cmake --install build-driver --component Runtime
DESTDIR=/tmp/acpp-dev cmake --install build-driver --component Development
```

`cpack -G TGZ` produces component archives. Unlike DEB packages, these archives
do not install system dependencies automatically. `ACPP_PACKAGE_LLVM_TOOLS=OFF`
omits the runtime copies of `llc`, `opt`, and the LLVM linker; this is only
appropriate if matching tools remain available at their configured paths.

After installing both packages:

```sh
acpp --acpp-targets=generic -O2 app.cpp -o app
./app
acpp --acpp-targets=omp -O2 app.cpp -o app-omp
./app-omp
```

A generic application still needs JIT libraries, bitcode and LLVM tools after
compilation, which is why these belong in the runtime package. The development
package is not needed to execute an already compiled application.

## Validation reference

The driver-only configuration has been built with LLVM 19 on Debian 13 arm64
and macOS arm64. All four GPU-independent tests pass. On Debian, both DEBs
were installed, generic and OpenMP applications were compiled, and those
applications and a libdevice-dependent PTX translation ran successfully after
the development package was removed and the original LLVM tool directory was
disabled. The NVIDIA header and standalone libdevice were absent from that
execution environment. Actual NVIDIA GPU kernel execution still needs testing
on a machine with a compatible NVIDIA driver and GPU.

## Carrying the change forward

Keep this change on its own branch or export its commit with
`git format-patch -1 --binary`. Apply that patch to an updated checkout using
`git am -3 /path/to/patch`. For an uncommitted diff, use `git apply --3way`.
Resolve any conflicts against the updated CUDA backend and installation rules,
then repeat the build, mock-driver tests, DEB packaging, and an NVIDIA GPU run.

The context handling uses retained device primary contexts, shared with the
CUDA runtime if an application also uses it. See NVIDIA's
[primary-context documentation](https://docs.nvidia.com/cuda/archive/11.8.0/cuda-driver-api/group__CUDA__PRIMARY__CTX.html)
and [driver memory API](https://docs.nvidia.com/cuda/archive/11.8.0/cuda-driver-api/group__CUDA__MEM.html).
