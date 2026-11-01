# Generate build-local C++ data from the caller-supplied NVIDIA bitcode.
# No NVIDIA files are copied into the source tree or patch.
if(NOT EXISTS "${INPUT}")
  message(FATAL_ERROR "Cannot embed missing file: ${INPUT}")
endif()
file(READ "${INPUT}" contents HEX)
if(NOT contents MATCHES "^4243c0de")
  message(FATAL_ERROR "Expected LLVM bitcode in ${INPUT}")
endif()
string(REGEX REPLACE "([0-9a-f][0-9a-f])" "0x\\1," contents "${contents}")
file(WRITE "${OUTPUT}" "// Generated from libdevice; do not edit.\n#pragma once\nstatic const unsigned char acpp_embedded_libdevice[] = {\n${contents}\n};\n")
