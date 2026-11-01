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
add_test(NAME cuda-driver-backend COMMAND cuda-driver-tests)
add_test(NAME cuda-driver-unavailable COMMAND cuda-driver-tests no-driver)
add_test(NAME cuda-driver-missing-symbol COMMAND cuda-driver-tests missing-symbol)

if(WITH_SSCP_COMPILER AND ACPP_EMBED_CUDA_LIBDEVICE)
  find_program(cuda_test_llvm_as NAMES llvm-as
    HINTS "${LLVM_TOOLS_BINARY_DIR}" NO_DEFAULT_PATH)
  if(NOT cuda_test_llvm_as)
    message(FATAL_ERROR "Embedded libdevice test requires matching llvm-as")
  endif()
  set(test_bitcode "${CMAKE_CURRENT_BINARY_DIR}/libdevice_kernel.bc")
  add_custom_command(OUTPUT "${test_bitcode}"
    COMMAND "${cuda_test_llvm_as}" "${CMAKE_CURRENT_SOURCE_DIR}/libdevice_kernel.ll"
      -o "${test_bitcode}"
    DEPENDS libdevice_kernel.ll VERBATIM)
  add_executable(cuda-embedded-libdevice-test embedded_libdevice_test.cpp "${test_bitcode}")
  target_include_directories(cuda-embedded-libdevice-test PRIVATE
    "${ACPP_SOURCE_ROOT}/include" "${ACPP_BINARY_ROOT}/include")
  target_link_libraries(cuda-embedded-libdevice-test PRIVATE llvm-to-ptx)
  add_dependencies(cuda-embedded-libdevice-test libkernel-sscp-ptx)
  # Match the installed bitcode layout beside the build's common library.
  add_custom_command(TARGET cuda-embedded-libdevice-test POST_BUILD
    COMMAND "${CMAKE_COMMAND}" -E make_directory
      "$<TARGET_FILE_DIR:acpp-common>/hipSYCL/bitcode"
    COMMAND "${CMAKE_COMMAND}" -E copy_if_different
      "${ACPP_BINARY_ROOT}/src/libkernel/sscp/ptx/libkernel-sscp-ptx-full.bc"
      "$<TARGET_FILE_DIR:acpp-common>/hipSYCL/bitcode/libkernel-sscp-ptx-full.bc")
  add_test(NAME cuda-embedded-libdevice COMMAND cuda-embedded-libdevice-test "${test_bitcode}")
endif()
