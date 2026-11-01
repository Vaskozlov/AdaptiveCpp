/*
 * Copyright The AdaptiveCpp Contributors
 * SPDX-License-Identifier: BSD-2-Clause
 */
#ifndef ACPP_CUDA_DRIVER_HPP
#define ACPP_CUDA_DRIVER_HPP

#include <cuda.h>

// Keep the declarations and symbol loading in sync. The CUDA header expands
// versioned entry points (e.g. cuMemAlloc -> cuMemAlloc_v2) before stringizing.
#define ACPP_CUDA_DRIVER_FUNCTIONS(F) \
  F(cuInit) \
  F(cuDeviceGetCount) \
  F(cuDeviceGetName) \
  F(cuDeviceGetAttribute) \
  F(cuDeviceTotalMem) \
  F(cuDriverGetVersion) \
  F(cuDevicePrimaryCtxRetain) \
  F(cuDevicePrimaryCtxRelease) \
  F(cuCtxSetCurrent) \
  F(cuCtxGetStreamPriorityRange) \
  F(cuDeviceCanAccessPeer) \
  F(cuCtxEnablePeerAccess) \
  F(cuMemAlloc) \
  F(cuMemAllocHost) \
  F(cuMemAllocManaged) \
  F(cuMemFree) \
  F(cuMemFreeHost) \
  F(cuMemGetInfo) \
  F(cuPointerGetAttributes) \
  F(cuMemAdvise) \
  F(cuMemPrefetchAsync) \
  F(cuMemcpyAsync) \
  F(cuMemcpy3DAsync) \
  F(cuMemsetD8Async) \
  F(cuStreamCreate) \
  F(cuStreamCreateWithPriority) \
  F(cuStreamDestroy) \
  F(cuStreamSynchronize) \
  F(cuStreamQuery) \
  F(cuStreamWaitEvent) \
  F(cuStreamAddCallback) \
  F(cuEventCreate) \
  F(cuEventDestroy) \
  F(cuEventRecord) \
  F(cuEventQuery) \
  F(cuEventSynchronize) \
  F(cuEventElapsedTime) \
  F(cuModuleLoadDataEx) \
  F(cuModuleUnload) \
  F(cuModuleGetFunction) \
  F(cuLaunchKernel)

namespace hipsycl::rt::cuda_driver {
#ifdef ACPP_CUDA_DRIVER_ONLY
#define ACPP_DECLARE_CUDA_FUNCTION(name) extern decltype(&::name) name;
#else
#define ACPP_DECLARE_CUDA_FUNCTION(name) using ::name;
#endif
ACPP_CUDA_DRIVER_FUNCTIONS(ACPP_DECLARE_CUDA_FUNCTION)
#undef ACPP_DECLARE_CUDA_FUNCTION

// No entry point may be used before initialize() succeeds.
CUresult initialize();
}

#endif
