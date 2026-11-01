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

#include "hipSYCL/runtime/cuda/cuda_allocator.hpp"
#include "hipSYCL/runtime/cuda/cuda_device_manager.hpp"
#include "hipSYCL/runtime/error.hpp"
#include "hipSYCL/runtime/hints.hpp"

namespace hipsycl {
namespace rt {

cuda_allocator::cuda_allocator(backend_descriptor desc, int cuda_device)
    : _backend_descriptor{desc}, _dev{cuda_device}
{}
      
void *cuda_allocator::raw_allocate(size_t min_alignment, size_t size_bytes,
                                   const allocation_hints &hints)
{
  CUdeviceptr ptr = 0;
  cuda_device_manager::get().activate_device(_dev);
  CUresult err = cuda_driver::cuMemAlloc(&ptr, size_bytes);

  if (err != CUDA_SUCCESS) {
    register_error(__acpp_here(),
                   error_info{"cuda_allocator: cuMemAlloc() failed",
                              error_code{"CUDA", err},
                              error_type::memory_allocation_error});
    return nullptr;
  }

  return reinterpret_cast<void *>(ptr);
}

void *
cuda_allocator::raw_allocate_optimized_host(size_t min_alignment,
                                            size_t bytes,
                                            const allocation_hints &hints) {
  void *ptr;
  cuda_device_manager::get().activate_device(_dev);

  CUresult err = cuda_driver::cuMemAllocHost(&ptr, bytes);

  if (err != CUDA_SUCCESS) {
    register_error(__acpp_here(),
                   error_info{"cuda_allocator: cuMemAllocHost() failed",
                              error_code{"CUDA", err},
                              error_type::memory_allocation_error});
    return nullptr;
  }
  return ptr;
}

void cuda_allocator::raw_free(void *mem) {
  if(!mem)
    return;
  cuda_device_manager::get().activate_device(_dev);

  pointer_info info;
  result query_result = query_pointer(mem, info);

  if (!query_result.is_success()) {
    register_error(query_result);
    return;
  }
  
  CUresult err;
  if (info.is_optimized_host)
    err = cuda_driver::cuMemFreeHost(mem);
  else
    err = cuda_driver::cuMemFree(reinterpret_cast<CUdeviceptr>(mem));
  
  if (err != CUDA_SUCCESS) {
    register_error(__acpp_here(),
                   error_info{"cuda_allocator: cuMemFree() failed",
                              error_code{"CUDA", err},
                              error_type::memory_allocation_error});
  }
}

void * cuda_allocator::raw_allocate_usm(size_t bytes,
                                        const allocation_hints &hints)
{
  cuda_device_manager::get().activate_device(_dev);
  
  CUdeviceptr ptr = 0;
  auto err = cuda_driver::cuMemAllocManaged(&ptr, bytes, CU_MEM_ATTACH_GLOBAL);
  if (err != CUDA_SUCCESS) {
    register_error(__acpp_here(),
                   error_info{"cuda_allocator: cuMemAllocManaged() failed",
                              error_code{"CUDA", err},
                              error_type::memory_allocation_error});
    return nullptr;
  }

  return reinterpret_cast<void *>(ptr);
}

bool cuda_allocator::is_usm_accessible_from(backend_descriptor b) const
{
  // TODO: Formulate this better - this assumes that either CUDA+CPU or
  // ROCm + CPU are active at the same time
  return true;
}

result cuda_allocator::query_pointer(const void *ptr, pointer_info &out) const {
  cuda_device_manager::get().activate_device(_dev);
  unsigned int memory_type = 0;
  unsigned int is_managed = 0;
  int device = -1;
  CUpointer_attribute attributes[] = {CU_POINTER_ATTRIBUTE_MEMORY_TYPE,
      CU_POINTER_ATTRIBUTE_IS_MANAGED, CU_POINTER_ATTRIBUTE_DEVICE_ORDINAL};
  void *values[] = {&memory_type, &is_managed, &device};
  auto err = cuda_driver::cuPointerGetAttributes(3, attributes, values,
      reinterpret_cast<CUdeviceptr>(ptr));
  // cuPointerGetAttributes succeeds with zeroed attributes for unknown pointers.
  if(err != CUDA_SUCCESS || memory_type == 0) {
    return make_error(__acpp_here(), error_info{
        "cuda_allocator: query_pointer(): pointer is unknown by backend",
        error_code{"CUDA", err}, error_type::invalid_parameter_error});
  }

  out.dev = rt::device_id{_backend_descriptor, device};
  out.is_from_host_backend = false;
  out.is_optimized_host = memory_type == CU_MEMORYTYPE_HOST;
  out.is_usm = is_managed != 0;
  out.native_handle = nullptr;
  out.native_offset = 0;
  
  return make_success();
}

result cuda_allocator::mem_advise(const void *addr, std::size_t num_bytes,
                            int advise) const {
#ifndef _WIN32
  cuda_device_manager::get().activate_device(_dev);
#if CUDA_VERSION >= 13000
  CUmemLocation location{};
  location.id = _dev;
  location.type = CU_MEM_LOCATION_TYPE_DEVICE;
#else
  int location = _dev;
#endif
  CUresult err = cuda_driver::cuMemAdvise(reinterpret_cast<CUdeviceptr>(addr),
      num_bytes, static_cast<CUmem_advise>(advise), location);
  if(err != CUDA_SUCCESS) {
    return make_error(
      __acpp_here(),
      error_info{"cuda_allocator: cuMemAdvise() failed", error_code{"CUDA", err}}
    );
  }
#else
  HIPSYCL_DEBUG_WARNING << "cuda_allocator: Ignoring mem_advise() hint"
                        << std::endl;
#endif // _WIN32
  return make_success();
}

device_id cuda_allocator::get_device() const {
  return device_id{_backend_descriptor, _dev};
}

}
}
