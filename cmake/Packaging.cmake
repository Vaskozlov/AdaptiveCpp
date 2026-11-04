# generic applications compile kernels at runtime. Their package therefore
# needs the translators, builtin bitcode, and LLVM code generation tools.
option(ACPP_PACKAGE_LLVM_TOOLS "Install LLVM tools required by generic applications" ON)
if(WITH_SSCP_COMPILER AND ACPP_PACKAGE_LLVM_TOOLS)
  if(ACPP_LLVM_COMPONENT)
    install(PROGRAMS "$<TARGET_FILE:llc>" "$<TARGET_FILE:opt>"
      DESTINATION lib/hipSYCL/ext/llvm/bin COMPONENT Runtime)
    if(WIN32)
      set(packaged_lld_name "lld-link${CMAKE_EXECUTABLE_SUFFIX}")
    elseif(APPLE)
      set(packaged_lld_name "ld64.lld")
    else()
      set(packaged_lld_name "ld.lld")
    endif()
    install(PROGRAMS "$<TARGET_FILE:lld>" RENAME "${packaged_lld_name}"
      DESTINATION lib/hipSYCL/ext/llvm/bin COMPONENT Runtime)
  else()
    foreach(tool LLC OPT LLD)
      # Distribution-provided tools are often symlinks outside our prefix.
      get_filename_component(tool_file "${ACPP_${tool}_PATH}" REALPATH)
      get_filename_component(tool_name "${ACPP_${tool}_PATH}" NAME)
      install(PROGRAMS "${tool_file}" RENAME "${tool_name}"
        DESTINATION lib/hipSYCL/ext/llvm/bin COMPONENT Runtime)
      if(APPLE)
        # Copied Homebrew tools use @executable_path/../lib for libLLVM, which
        # no longer points at LLVM after installation into our runtime layout.
        install(CODE "
          set(ACPP_PACKAGED_LLVM_TOOL \"\$ENV{DESTDIR}\${CMAKE_INSTALL_PREFIX}/lib/hipSYCL/ext/llvm/bin/${tool_name}\")
          set(ACPP_LLVM_LIBRARY_DIRS \"${LLVM_LIBRARY_DIRS}\")
          include(\"${ACPP_SOURCE_ROOT}/cmake/PrepareLLVMTool.cmake\")
        " COMPONENT Runtime)
      endif()
    endforeach()
  endif()

  find_file(ACPP_LLVM_LICENSE_FILE NAMES LICENSE.TXT copyright
    HINTS "${LLVM_MAIN_SRC_DIR}" "${LLVM_TOOLS_BINARY_DIR}/.."
      "${LLVM_TOOLS_BINARY_DIR}/../share/doc/llvm"
      "${LLVM_TOOLS_BINARY_DIR}/../share/doc/llvm-${LLVM_VERSION_MAJOR}"
      "${LLVM_TOOLS_BINARY_DIR}/../../../share/doc/llvm-${LLVM_VERSION_MAJOR}"
    DOC "License notice for redistributed LLVM tools" NO_DEFAULT_PATH)
  if(ACPP_LLVM_LICENSE_FILE)
    install(FILES "${ACPP_LLVM_LICENSE_FILE}" RENAME LLVM-LICENSE.txt
      DESTINATION share/licenses/AdaptiveCpp COMPONENT Runtime)
  endif()
endif()

install(FILES "${ACPP_SOURCE_ROOT}/LICENSE"
  DESTINATION share/licenses/AdaptiveCpp COMPONENT Runtime)
if(WITH_CUDA_BACKEND)
  install(FILES "${ACPP_SOURCE_ROOT}/third-party/nvidia/NOTICE.txt"
    DESTINATION share/licenses/AdaptiveCpp/nvidia COMPONENT Runtime)
endif()

set(CPACK_PACKAGE_NAME "AdaptiveCpp")
set(CPACK_PACKAGE_VENDOR "AdaptiveCpp")
set(CPACK_PACKAGE_CONTACT "AdaptiveCpp package maintainer")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "AdaptiveCpp SYCL compiler and runtime")
set(CPACK_PACKAGE_VERSION "${ACPP_VERSION_MAJOR}.${ACPP_VERSION_MINOR}.${ACPP_VERSION_PATCH}")
set(CPACK_RESOURCE_FILE_LICENSE "${ACPP_SOURCE_ROOT}/LICENSE")
set(CPACK_COMPONENTS_ALL Runtime Development)
set(CPACK_COMPONENT_RUNTIME_DISPLAY_NAME "Application runtime")
set(CPACK_COMPONENT_DEVELOPMENT_DISPLAY_NAME "Compiler and headers")
set(CPACK_COMPONENT_DEVELOPMENT_DEPENDS Runtime)
set(CPACK_COMPONENTS_GROUPING IGNORE)
set(CPACK_ARCHIVE_COMPONENT_INSTALL ON)
set(CPACK_DEB_COMPONENT_INSTALL ON)
set(CPACK_RPM_COMPONENT_INSTALL ON)
set(CPACK_DEBIAN_RUNTIME_PACKAGE_NAME "adaptivecpp-runtime")
set(CPACK_DEBIAN_DEVELOPMENT_PACKAGE_NAME "adaptivecpp-dev")
set(CPACK_DEBIAN_ENABLE_COMPONENT_DEPENDS ON)
set(CPACK_DEBIAN_RUNTIME_PACKAGE_SHLIBDEPS ON)
set(CPACK_DEBIAN_DEVELOPMENT_PACKAGE_SHLIBDEPS ON)
if(NOT DEFINED CPACK_DEBIAN_DEVELOPMENT_PACKAGE_DEPENDS)
  set(CPACK_DEBIAN_DEVELOPMENT_PACKAGE_DEPENDS "python3")
  if(BUILD_CLANG_PLUGIN AND NOT ACPP_LLVM_COMPONENT)
    string(APPEND CPACK_DEBIAN_DEVELOPMENT_PACKAGE_DEPENDS
      ", clang-${LLVM_VERSION_MAJOR}, libomp-${LLVM_VERSION_MAJOR}-dev")
  endif()
endif()
set(CPACK_RPM_RUNTIME_PACKAGE_NAME "adaptivecpp-runtime")
set(CPACK_RPM_DEVELOPMENT_PACKAGE_NAME "adaptivecpp-devel")
set(CPACK_RPM_DEVELOPMENT_PACKAGE_REQUIRES
  "adaptivecpp-runtime = ${CPACK_PACKAGE_VERSION}, python3")
if(NOT CPACK_GENERATOR)
  set(CPACK_GENERATOR TGZ)
endif()
include(CPack)
