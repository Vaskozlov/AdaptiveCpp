/*
 * Copyright The AdaptiveCpp Contributors
 * SPDX-License-Identifier: BSD-2-Clause
 */
#include "cuda_driver.hpp"
#include "hipSYCL/common/dylib_loader.hpp"
#include "hipSYCL/runtime/cuda/cuda_backend.hpp"
#include "hipSYCL/runtime/cuda/cuda_device_manager.hpp"
#include "hipSYCL/runtime/operations.hpp"
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <thread>
#include <unordered_map>

#define CHECK(condition) do { if(!(condition)) { \
  std::cerr << "Failed at line " << __LINE__ << ": " << #condition << '\n'; \
  std::abort(); } } while(false)

namespace {
std::string mode;
thread_local CUcontext current = nullptr;
std::atomic<int> retains{0}, releases{0};
int priority = 0, copies3d = 0, copies1d = 0;
bool ready = true;
struct allocation { std::size_t size; unsigned type; unsigned managed; int device; };
std::unordered_map<void *, allocation> allocations;
int active_device() { CHECK(current); return reinterpret_cast<std::uintptr_t>(current) - 1; }

CUresult CUDAAPI init(unsigned) { return CUDA_SUCCESS; }
CUresult CUDAAPI count(int *n) { *n = 2; return CUDA_SUCCESS; }
CUresult CUDAAPI retain(CUcontext *ctx, CUdevice dev) {
  ++retains;
  *ctx = reinterpret_cast<CUcontext>(dev + 1);
  return CUDA_SUCCESS;
}
CUresult CUDAAPI release(CUdevice) { ++releases; return CUDA_SUCCESS; }
CUresult CUDAAPI set_context(CUcontext ctx) { current = ctx; return CUDA_SUCCESS; }
CUresult CUDAAPI name(char *out, int length, CUdevice dev) {
  std::strncpy(out, dev == 0 ? "Mock GPU 0" : "Mock GPU 1", length);
  return CUDA_SUCCESS;
}
CUresult CUDAAPI attribute(int *out, CUdevice_attribute attr, CUdevice) {
  *out = 1;
  if(attr == CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MAJOR) *out = 8;
  if(attr == CU_DEVICE_ATTRIBUTE_COMPUTE_CAPABILITY_MINOR) *out = 0;
  if(attr == CU_DEVICE_ATTRIBUTE_WARP_SIZE) *out = 32;
  if(attr == CU_DEVICE_ATTRIBUTE_MAX_THREADS_PER_BLOCK) *out = 1024;
  return CUDA_SUCCESS;
}
CUresult CUDAAPI total_memory(std::size_t *bytes, CUdevice) { *bytes = 1 << 24; return CUDA_SUCCESS; }
CUresult CUDAAPI can_access(int *out, CUdevice, CUdevice) { *out = 1; return CUDA_SUCCESS; }
CUresult CUDAAPI enable_peer(CUcontext, unsigned) { active_device(); return CUDA_SUCCESS; }
CUresult CUDAAPI allocate(CUdeviceptr *ptr, std::size_t size) {
  auto p = std::malloc(size);
  allocations[p] = {size, CU_MEMORYTYPE_DEVICE, 0, active_device()};
  *ptr = reinterpret_cast<CUdeviceptr>(p);
  return CUDA_SUCCESS;
}
CUresult CUDAAPI allocate_host(void **ptr, std::size_t size) {
  *ptr = std::malloc(size);
  allocations[*ptr] = {size, CU_MEMORYTYPE_HOST, 0, active_device()};
  return CUDA_SUCCESS;
}
CUresult CUDAAPI allocate_managed(CUdeviceptr *ptr, std::size_t size, unsigned flags) {
  CHECK(flags == CU_MEM_ATTACH_GLOBAL);
  auto result = allocate(ptr, size);
  allocations[reinterpret_cast<void *>(*ptr)].managed = 1;
  return result;
}
CUresult CUDAAPI free_device(CUdeviceptr ptr) {
  active_device();
  CHECK(allocations.erase(reinterpret_cast<void *>(ptr)) == 1);
  std::free(reinterpret_cast<void *>(ptr));
  return CUDA_SUCCESS;
}
CUresult CUDAAPI free_host(void *ptr) { return free_device(reinterpret_cast<CUdeviceptr>(ptr)); }
CUresult CUDAAPI pointer_attributes(unsigned n, CUpointer_attribute *attrs, void **values, CUdeviceptr ptr) {
  active_device();
  allocation data{};
  auto it = allocations.find(reinterpret_cast<void *>(ptr));
  if(it != allocations.end()) data = it->second;
  for(unsigned i = 0; i < n; ++i) {
    switch(attrs[i]) {
    case CU_POINTER_ATTRIBUTE_MEMORY_TYPE: *static_cast<unsigned *>(values[i]) = data.type; break;
    case CU_POINTER_ATTRIBUTE_IS_MANAGED: *static_cast<unsigned *>(values[i]) = data.managed; break;
    case CU_POINTER_ATTRIBUTE_DEVICE_ORDINAL: *static_cast<int *>(values[i]) = data.device; break;
    default: CHECK(false);
    }
  }
  return CUDA_SUCCESS;
}
CUresult CUDAAPI stream_create(CUstream *out, unsigned flags) {
  active_device();
  CHECK(flags == CU_STREAM_NON_BLOCKING);
  *out = reinterpret_cast<CUstream>(0x100);
  return CUDA_SUCCESS;
}
CUresult CUDAAPI stream_priority(CUstream *out, unsigned flags, int p) {
  priority = p;
  return stream_create(out, flags);
}
CUresult CUDAAPI stream_success(CUstream) { active_device(); return CUDA_SUCCESS; }
CUresult CUDAAPI stream_query(CUstream) { active_device(); return ready ? CUDA_SUCCESS : CUDA_ERROR_NOT_READY; }
CUresult CUDAAPI event_create(CUevent *out, unsigned flags) {
  active_device(); CHECK(flags == CU_EVENT_DEFAULT);
  *out = reinterpret_cast<CUevent>(0x200); return CUDA_SUCCESS;
}
CUresult CUDAAPI event_success(CUevent) { active_device(); return CUDA_SUCCESS; }
CUresult CUDAAPI event_query(CUevent) { active_device(); return ready ? CUDA_SUCCESS : CUDA_ERROR_NOT_READY; }
CUresult CUDAAPI event_record(CUevent, CUstream) { active_device(); return CUDA_SUCCESS; }
CUresult CUDAAPI copy(CUdeviceptr dst, CUdeviceptr src, std::size_t bytes, CUstream) {
  active_device(); ++copies1d;
  std::memcpy(reinterpret_cast<void *>(dst), reinterpret_cast<void *>(src), bytes);
  return CUDA_SUCCESS;
}
CUresult CUDAAPI copy3d(const CUDA_MEMCPY3D *p, CUstream) {
  active_device(); ++copies3d;
  CHECK(p->srcMemoryType == CU_MEMORYTYPE_HOST || p->srcMemoryType == CU_MEMORYTYPE_DEVICE);
  CHECK(p->dstMemoryType == CU_MEMORYTYPE_HOST || p->dstMemoryType == CU_MEMORYTYPE_DEVICE);
  auto src = p->srcMemoryType == CU_MEMORYTYPE_HOST ? p->srcHost : reinterpret_cast<const void *>(p->srcDevice);
  auto dst = p->dstMemoryType == CU_MEMORYTYPE_HOST ? p->dstHost : reinterpret_cast<void *>(p->dstDevice);
  for(std::size_t z = 0; z < p->Depth; ++z)
    for(std::size_t y = 0; y < p->Height; ++y)
      std::memcpy(static_cast<char *>(dst) + (z * p->dstHeight + y) * p->dstPitch,
          static_cast<const char *>(src) + (z * p->srcHeight + y) * p->srcPitch, p->WidthInBytes);
  return CUDA_SUCCESS;
}
CUresult CUDAAPI memset8(CUdeviceptr dst, unsigned char value, std::size_t bytes, CUstream) {
  active_device(); std::memset(reinterpret_cast<void *>(dst), value, bytes); return CUDA_SUCCESS;
}
// Missing implementations must never silently succeed.
template<class> struct unused;
template<class... Args> struct unused<CUresult(CUDAAPI *)(Args...)> {
  static CUresult CUDAAPI call(Args...) { CHECK(false); return CUDA_ERROR_NOT_SUPPORTED; }
};
}

// Replace just the OS loader. The production symbol table and initialization
// logic run unmodified, including expansion of CUDA's versioned symbol names.
namespace hipsycl::common {
void *load_library(const std::string &, std::string &) {
  return mode == "no-driver" ? nullptr : reinterpret_cast<void *>(1);
}
void *get_symbol_from_library(void *, const std::string &symbol, std::string &) {
  if(mode == "missing-symbol") return nullptr;
#define STR_IMPL(x) #x
#define STR(x) STR_IMPL(x)
#define SYMBOL(entry, impl) if(symbol == STR(entry)) return reinterpret_cast<void *>(&impl)
  SYMBOL(cuInit, init); SYMBOL(cuDeviceGetCount, count);
  SYMBOL(cuDevicePrimaryCtxRetain, retain); SYMBOL(cuDevicePrimaryCtxRelease, release);
  SYMBOL(cuCtxSetCurrent, set_context); SYMBOL(cuDeviceGetName, name);
  SYMBOL(cuDeviceGetAttribute, attribute); SYMBOL(cuDeviceTotalMem, total_memory);
  SYMBOL(cuDeviceCanAccessPeer, can_access); SYMBOL(cuCtxEnablePeerAccess, enable_peer);
  SYMBOL(cuMemAlloc, allocate); SYMBOL(cuMemAllocHost, allocate_host);
  SYMBOL(cuMemAllocManaged, allocate_managed); SYMBOL(cuMemFree, free_device);
  SYMBOL(cuMemFreeHost, free_host); SYMBOL(cuPointerGetAttributes, pointer_attributes);
  SYMBOL(cuStreamCreate, stream_create); SYMBOL(cuStreamCreateWithPriority, stream_priority);
  SYMBOL(cuStreamDestroy, stream_success); SYMBOL(cuStreamSynchronize, stream_success);
  SYMBOL(cuStreamQuery, stream_query); SYMBOL(cuEventCreate, event_create);
  SYMBOL(cuEventRecord, event_record); SYMBOL(cuEventSynchronize, event_success);
  SYMBOL(cuEventDestroy, event_success); SYMBOL(cuEventQuery, event_query);
  SYMBOL(cuMemcpyAsync, copy); SYMBOL(cuMemcpy3DAsync, copy3d); SYMBOL(cuMemsetD8Async, memset8);
#undef SYMBOL
#define UNUSED(entry) if(symbol == STR(entry)) return reinterpret_cast<void *>(&unused<decltype(&::entry)>::call);
  ACPP_CUDA_DRIVER_FUNCTIONS(UNUSED)
#undef UNUSED
#undef STR
#undef STR_IMPL
  CHECK(false); return nullptr;
}
}

int main(int argc, char **argv) {
  using namespace hipsycl::rt;
  if(argc > 1) mode = argv[1];
  if(!mode.empty()) {
    cuda_backend backend;
    CHECK(backend.get_hardware_manager()->get_num_devices() == 0);
    std::cout << "Unavailable driver handled: " << mode << '\n';
    return 0;
  }
  cuda_backend backend;
  auto *hardware = backend.get_hardware_manager();
  CHECK(hardware->get_num_devices() == 2);
  CHECK(hardware->get_device(1)->get_device_name() == "Mock GPU 1");
  CHECK(hardware->get_device(1)->get_device_arch() == "sm_80");
  auto dev = hardware->get_device_id(1);
  auto *allocator = backend.get_allocator(dev);
  void *device = allocator->raw_allocate(64, 128);
  void *host = allocator->raw_allocate_optimized_host(64, 128);
  void *managed = allocator->raw_allocate_usm(128);
  CHECK(device && host && managed);
  pointer_info info;
  CHECK(allocator->query_pointer(device, info).is_success() && !info.is_usm && !info.is_optimized_host);
  CHECK(allocator->query_pointer(host, info).is_success() && info.is_optimized_host);
  CHECK(allocator->query_pointer(managed, info).is_success() && info.is_usm);
  int unknown;
  CHECK(!allocator->query_pointer(&unknown, info).is_success());
  // Re-activate even if external code changed this thread's current context.
  current = nullptr;
  cuda_device_manager::get().activate_device(1);
  CHECK(active_device() == 1);
  int previous_releases = releases;
  std::thread worker([] { cuda_device_manager::get().activate_device(0); CHECK(active_device() == 0); });
  worker.join();
  CHECK(releases == previous_releases + 1);
  {
    cuda_queue queue{&backend, dev, -2};
    CHECK(priority == -2);
    auto evt = queue.insert_event();
    ready = false; CHECK(!evt->is_complete());
    ready = true; CHECK(evt->is_complete()); evt->wait();
    memset_operation fill{device, 0x5a, 128};
    current = nullptr; CHECK(queue.submit_memset(fill, {}).is_success());
    CHECK(static_cast<unsigned char *>(device)[12] == 0x5a);
    auto cpu = device_id{backend_descriptor{hardware_platform::cpu, api_platform::omp}, 0};
    int source[60], dest[120];
    for(int i = 0; i < 60; ++i) source[i] = i + 100;
    std::fill(std::begin(dest), std::end(dest), -1);
    // Offset, pitch and slice stride differ at each end of this 3D copy.
    memory_location src{cpu, source, {1, 1, 1}, {3, 4, 5}, sizeof(int)};
    memory_location dst{dev, dest, {0, 2, 2}, {3, 5, 8}, sizeof(int)};
    memcpy_operation op{src, dst, {2, 2, 3}};
    current = nullptr; CHECK(queue.submit_memcpy(op, {}).is_success());
    for(int z = 0; z < 2; ++z)
      for(int y = 0; y < 2; ++y)
        for(int x = 0; x < 3; ++x)
          CHECK(dest[z * 40 + (y + 2) * 8 + x + 2] == source[(z + 1) * 20 + (y + 1) * 5 + x + 1]);
    CHECK(dest[0] == -1 && copies3d == 1);
    memcpy_operation contiguous{{cpu, host, {}, {1, 1, 128}, 1},
        {dev, device, {}, {1, 1, 128}, 1}, {1, 1, 128}};
    CHECK(queue.submit_memcpy(contiguous, {}).is_success() && copies1d == 1);
    inorder_queue_status status;
    ready = false; CHECK(queue.query_status(status).is_success());
    ready = true; CHECK(queue.wait().is_success());
  }
  allocator->raw_free(device); allocator->raw_free(host); allocator->raw_free(managed);
  allocator->raw_free(nullptr);
  CHECK(allocations.empty());
  std::cout << "Driver backend context, allocation, stream, event and copy tests passed\n";
}
