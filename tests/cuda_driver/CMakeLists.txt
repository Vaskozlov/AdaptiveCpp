# Exercise the real backend against a deterministic driver implementation.
# These tests need neither an NVIDIA GPU nor an installed driver/toolkit.
set(cuda_sources
  cuda_driver.cpp cuda_device_manager.cpp cuda_allocator.cpp
  cuda_event.cpp cuda_event_pool.cpp cuda_instrumentation.cpp
  cuda_hardware_manager.cpp cuda_queue.cpp cuda_backend.cpp cuda_code_object.cpp)
set(cuda_test_sources)
foreach(source ${cuda_sources})
  list(APPEND cuda_test_sources "${ACPP_SOURCE_ROOT}/src/runtime/cuda/${source}")
endforeach()
find_package(Threads REQUIRED)
add_executable(cuda-driver-tests driver_tests.cpp ${cuda_test_sources})
target_compile_definitions(cuda-driver-tests PRIVATE ACPP_CUDA_DRIVER_ONLY)
target_include_directories(cuda-driver-tests PRIVATE
  "${ACPP_SOURCE_ROOT}/include" "${ACPP_BINARY_ROOT}/include"
  "${ACPP_SOURCE_ROOT}/src/runtime/cuda" ${CUDA_INCLUDE_DIRS})
target_link_libraries(cuda-driver-tests PRIVATE acpp-rt Threads::Threads)
if(WITH_SSCP_COMPILER)
  target_compile_definitions(cuda-driver-tests PRIVATE HIPSYCL_WITH_SSCP_COMPILER)
  target_link_libraries(cuda-driver-tests PRIVATE llvm-to-ptx)
endif()
add_test(NAME cuda-driver-backend COMMAND cuda-driver-tests)
add_test(NAME cuda-driver-unavailable COMMAND cuda-driver-tests no-driver)
add_test(NAME cuda-driver-missing-symbol COMMAND cuda-driver-tests missing-symbol)

if(WITH_SSCP_COMPILER AND ACPP_EMBED_CUDA_LIBDEVICE)
  include("${ACPP_SOURCE_ROOT}/cmake/CudaPtxTests.cmake")
endif()
