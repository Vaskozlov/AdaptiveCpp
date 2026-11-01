/*
 * This file is part of AdaptiveCpp, an implementation of SYCL and C++ standard
 * parallelism for CPUs and GPUs.
 *
 * Copyright The AdaptiveCpp Contributors
 *
 * AdaptiveCpp is released under the BSD 2-Clause "Simplified" License.
 * See file LICENSE in the project root for full license details.
 */
// SPDX-License-Identifier: BSD-2-Clause
#include "cuda_driver.hpp"
#include "hipSYCL/runtime/cuda/cuda_device_manager.hpp"
#include "hipSYCL/runtime/error.hpp"

namespace hipsycl::rt {

void cuda_device_manager::activate_device(int device_id) {
  CUcontext context = nullptr;
  auto err = cuda_driver::cuDevicePrimaryCtxRetain(&context, device_id);
  if(err != CUDA_SUCCESS) {
    register_error(__acpp_here(), error_info{
        "cuda_device_manager: Could not retain primary context",
        error_code{"CUDA", err}});
    return;
  }
  err = cuda_driver::cuCtxSetCurrent(context);
  // cuda_hardware_context keeps a reference for as long as device resources
  // exist. Balance this temporary reference without owning thread-local CUDA
  // resources, which might otherwise be destroyed before global SYCL objects.
  cuda_driver::cuDevicePrimaryCtxRelease(device_id);
  if(err != CUDA_SUCCESS) {
    register_error(__acpp_here(), error_info{
        "cuda_device_manager: Could not set current context",
        error_code{"CUDA", err}});
    return;
  }
  _device = device_id;
}

int cuda_device_manager::get_active_device() const { return _device; }

}
