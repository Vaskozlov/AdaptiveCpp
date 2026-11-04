# Assemble with the same LLVM that provides the PTX translator. An integrated
# build must use its build target, which does not exist on disk at configure time.
if(ACPP_LLVM_COMPONENT)
  set(cuda_test_llvm_as "$<TARGET_FILE:llvm-as>")
  set(cuda_test_llvm_as_dependency llvm-as)
else()
  find_program(cuda_test_llvm_as NAMES llvm-as
    HINTS "${LLVM_TOOLS_BINARY_DIR}" NO_DEFAULT_PATH)
  if(NOT cuda_test_llvm_as)
    message(FATAL_ERROR "Embedded libdevice test requires matching llvm-as")
  endif()
  set(cuda_test_llvm_as_dependency "${cuda_test_llvm_as}")
endif()

set(cuda_test_source_dir "${ACPP_SOURCE_ROOT}/tests/cuda_driver")
set(test_bitcode "${CMAKE_CURRENT_BINARY_DIR}/libdevice_kernel.bc")
add_custom_command(OUTPUT "${test_bitcode}"
  COMMAND "${cuda_test_llvm_as}" "${cuda_test_source_dir}/libdevice_kernel.ll"
    -o "${test_bitcode}"
  DEPENDS "${cuda_test_source_dir}/libdevice_kernel.ll" ${cuda_test_llvm_as_dependency}
  VERBATIM)
add_executable(cuda-embedded-libdevice-test
  "${cuda_test_source_dir}/embedded_libdevice_test.cpp" "${test_bitcode}")
target_include_directories(cuda-embedded-libdevice-test PRIVATE
  "${ACPP_SOURCE_ROOT}/include" "${ACPP_BINARY_ROOT}/include")
target_link_libraries(cuda-embedded-libdevice-test PRIVATE llvm-to-ptx)
add_dependencies(cuda-embedded-libdevice-test libkernel-sscp-ptx)
if(WIN32 AND ACPP_LLVM_COMPONENT)
  # Keep the test executable alongside the DLLs it loads.
  set_target_properties(cuda-embedded-libdevice-test PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${LLVM_RUNTIME_OUTPUT_INTDIR}")
endif()
add_custom_command(TARGET cuda-embedded-libdevice-test POST_BUILD
  COMMAND "${CMAKE_COMMAND}" -E make_directory
    "$<TARGET_FILE_DIR:acpp-common>/hipSYCL/bitcode"
  COMMAND "${CMAKE_COMMAND}" -E copy_if_different
    "${ACPP_BINARY_ROOT}/src/libkernel/sscp/ptx/libkernel-sscp-ptx-full.bc"
    "$<TARGET_FILE_DIR:acpp-common>/hipSYCL/bitcode/libkernel-sscp-ptx-full.bc"
  VERBATIM)
add_test(NAME cuda-embedded-libdevice
  COMMAND cuda-embedded-libdevice-test "${test_bitcode}")
