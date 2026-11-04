AdaptiveCpp Windows LLVM SDK

This SDK contains LLVM 19.1.7 with AdaptiveCpp linked into its compiler tools,
the AdaptiveCpp runtime, OpenMP, headers, CMake integration and JIT resources.

To compile applications, install Python 3 and Visual Studio 2022 Build Tools
with the C++ tools and Windows SDK. Use a Developer Command Prompt/PowerShell.
The Microsoft C++ runtime must be available when running compiled applications.
The installer does not download or install these prerequisites.

Add this SDK's bin directory to PATH, or use its full path. acpp.cmd invokes
Python from PATH; ACPP_PYTHON can name an explicit Python executable.

For CMake applications use Ninja, this SDK's bin/clang.exe as the C++ compiler,
find_package(AdaptiveCpp CONFIG REQUIRED), and add_sycl_to_target(TARGET app).
Set CMAKE_PREFIX_PATH to the SDK prefix when consuming the installer directly.
Conan consumers obtain the integration paths from the package automatically.

NVIDIA support uses the system driver's nvcuda.dll and embedded libdevice.
The CUDA toolkit is not needed. An absent NVIDIA driver leaves CPU support
available. Actual GPU execution requires a compatible NVIDIA GPU and driver.

Generic applications compile kernels at runtime. Preserve the installed
runtime plugins, bitcode, import libraries, and LLVM JIT tools when deploying.
The compiler tools and runtime must come from the same SDK/source version.

Licenses and NVIDIA notices are installed in licenses and share/licenses.
Documentation: https://adaptivecpp.github.io
