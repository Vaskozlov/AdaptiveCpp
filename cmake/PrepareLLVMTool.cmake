# The system LLVM shared libraries remain external dependencies. Preserve their
# discoverability when installing copies of LLVM's Mach-O executables.
execute_process(COMMAND /usr/bin/otool -l "${ACPP_PACKAGED_LLVM_TOOL}"
  OUTPUT_VARIABLE load_commands RESULT_VARIABLE tool_result)
if(NOT tool_result EQUAL 0)
  message(FATAL_ERROR "Cannot inspect installed LLVM tool ${ACPP_PACKAGED_LLVM_TOOL}")
endif()

foreach(library_dir IN LISTS ACPP_LLVM_LIBRARY_DIRS)
  string(FIND "${load_commands}" "path ${library_dir} (offset" rpath_position)
  if(rpath_position EQUAL -1)
    execute_process(COMMAND /usr/bin/install_name_tool -add_rpath
      "${library_dir}" "${ACPP_PACKAGED_LLVM_TOOL}" RESULT_VARIABLE tool_result)
    if(NOT tool_result EQUAL 0)
      message(FATAL_ERROR "Cannot update installed LLVM tool ${ACPP_PACKAGED_LLVM_TOOL}")
    endif()
  endif()
endforeach()

# Changing a Mach-O load command invalidates its original signature.
execute_process(COMMAND /usr/bin/codesign --force --sign - "${ACPP_PACKAGED_LLVM_TOOL}"
  RESULT_VARIABLE tool_result)
if(NOT tool_result EQUAL 0)
  message(FATAL_ERROR "Cannot sign installed LLVM tool ${ACPP_PACKAGED_LLVM_TOOL}")
endif()
