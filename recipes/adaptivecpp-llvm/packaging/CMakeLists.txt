cmake_minimum_required(VERSION 3.23)
project(AdaptiveCppSDKPackaging NONE)

foreach(variable ACPP_SDK_STAGE ACPP_SDK_VERSION ACPP_VERSION ACPP_LLVM_VERSION)
  if(NOT DEFINED ${variable} OR "${${variable}}" STREQUAL "")
    message(FATAL_ERROR "${variable} is required")
  endif()
endforeach()

# Validate the distribution independently of its producer. In particular,
# merely packaging AdaptiveCpp's two components omits the integrated compiler.
set(required_files
  bin/clang.exe bin/clang++.exe bin/clang-cl.exe
  bin/llc.exe bin/opt.exe bin/lld-link.exe bin/llvm-link.exe
  bin/acpp bin/acpp.cmd bin/acpp-rt.dll bin/acpp-common.dll bin/libomp.dll
  bin/hipSYCL/rt-backend-omp.dll
  lib/acpp-rt.lib lib/acpp-common.lib
  lib/hipSYCL/acpp-sscp-host-c-runtime-import.lib
  lib/hipSYCL/bitcode/libkernel-sscp-host-full.bc
  lib/hipSYCL/bitcode/libkernel-sscp-host-fast-full.bc
  lib/cmake/AdaptiveCpp/adaptivecpp-config.cmake
  lib/cmake/AdaptiveCpp/adaptivecpp-config-version.cmake
  licenses/llvm/LICENSE.TXT licenses/AdaptiveCpp/LICENSE)
string(REGEX MATCH "^[0-9]+" llvm_major "${ACPP_LLVM_VERSION}")
list(APPEND required_files "lib/clang/${llvm_major}/include/stddef.h")
if(ACPP_SDK_WITH_CUDA)
  list(APPEND required_files bin/hipSYCL/rt-backend-cuda.dll
    lib/hipSYCL/bitcode/libkernel-sscp-ptx-full.bc licenses/nvidia/NOTICE.txt)
  set(backend cuda-driver)
else()
  set(backend cpu)
endif()
foreach(relative_path IN LISTS required_files)
  if(NOT EXISTS "${ACPP_SDK_STAGE}/${relative_path}")
    message(FATAL_ERROR "Incomplete Windows SDK: missing ${relative_path}")
  endif()
endforeach()

install(DIRECTORY "${ACPP_SDK_STAGE}/" DESTINATION . USE_SOURCE_PERMISSIONS)

set(CPACK_PACKAGE_NAME AdaptiveCpp-LLVM)
set(CPACK_PACKAGE_VENDOR AdaptiveCpp)
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "AdaptiveCpp SYCL SDK with integrated LLVM")
set(CPACK_PACKAGE_VERSION "${ACPP_VERSION}")
set(CPACK_PACKAGE_FILE_NAME "AdaptiveCpp-${ACPP_SDK_VERSION}-Windows-x86_64-${backend}")
set(CPACK_PACKAGE_INSTALL_DIRECTORY "AdaptiveCpp-${ACPP_SDK_VERSION}-${backend}")
set(CPACK_PACKAGE_INSTALL_REGISTRY_KEY "AdaptiveCpp-LLVM-${ACPP_SDK_VERSION}-${backend}")
set(CPACK_RESOURCE_FILE_LICENSE "${ACPP_SDK_STAGE}/licenses/AdaptiveCpp/LICENSE")
set(CPACK_MONOLITHIC_INSTALL ON)
set(CPACK_GENERATOR "NSIS;ZIP")
set(CPACK_NSIS_INSTALL_ROOT "$PROGRAMFILES64")
set(CPACK_NSIS_DISPLAY_NAME "AdaptiveCpp ${ACPP_VERSION} / LLVM ${ACPP_LLVM_VERSION} (${backend})")
set(CPACK_NSIS_PACKAGE_NAME "AdaptiveCpp LLVM SDK")
set(CPACK_NSIS_MODIFY_PATH ON)
set(CPACK_NSIS_ENABLE_UNINSTALL_BEFORE_INSTALL ON)
set(CPACK_NSIS_COMPRESSOR "/SOLID lzma")
set(CPACK_NSIS_URL_INFO_ABOUT "https://adaptivecpp.github.io")
set(CPACK_NSIS_HELP_LINK "https://github.com/AdaptiveCpp/AdaptiveCpp")
include(CPack)
