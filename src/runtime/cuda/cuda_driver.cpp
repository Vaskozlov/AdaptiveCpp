/*
 * Copyright The AdaptiveCpp Contributors
 * SPDX-License-Identifier: BSD-2-Clause
 */
#include "cuda_driver.hpp"
#include "hipSYCL/common/debug.hpp"
#include "hipSYCL/common/dylib_loader.hpp"

namespace hipsycl::rt::cuda_driver {
#ifdef ACPP_CUDA_DRIVER_ONLY
#define ACPP_DEFINE_CUDA_FUNCTION(name) decltype(&::name) name = nullptr;
ACPP_CUDA_DRIVER_FUNCTIONS(ACPP_DEFINE_CUDA_FUNCTION)
#undef ACPP_DEFINE_CUDA_FUNCTION

CUresult initialize() {
  static const CUresult status = [] {
    std::string message;
#ifdef _WIN32
    const char *library = "nvcuda.dll";
#elif defined(__APPLE__)
    const char *library = "libcuda.dylib";
#else
    const char *library = "libcuda.so.1";
#endif
    void *handle = common::load_library(library, message);
    if(!handle) {
      HIPSYCL_DEBUG_INFO << "cuda_driver: " << message << std::endl;
      return CUDA_ERROR_NO_DEVICE;
    }
    // Keep the driver loaded until process exit: queues, modules and thread
    // local context references can outlive the backend's hardware manager.
#define ACPP_CUDA_STRINGIZE_IMPL(name) #name
#define ACPP_CUDA_STRINGIZE(name) ACPP_CUDA_STRINGIZE_IMPL(name)
#define ACPP_LOAD_CUDA_FUNCTION(name) \
    name = reinterpret_cast<decltype(name)>(common::get_symbol_from_library( \
        handle, ACPP_CUDA_STRINGIZE(name), message)); \
    if(!name) { \
      HIPSYCL_DEBUG_WARNING << "cuda_driver: " << message << std::endl; \
      return CUDA_ERROR_NOT_INITIALIZED; \
    }
    ACPP_CUDA_DRIVER_FUNCTIONS(ACPP_LOAD_CUDA_FUNCTION)
#undef ACPP_LOAD_CUDA_FUNCTION
#undef ACPP_CUDA_STRINGIZE
#undef ACPP_CUDA_STRINGIZE_IMPL
    return cuInit(0);
  }();
  return status;
}
#else
CUresult initialize() { return cuInit(0); }
#endif
}
