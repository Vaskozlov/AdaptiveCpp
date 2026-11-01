/*
 * Copyright The AdaptiveCpp Contributors
 * SPDX-License-Identifier: BSD-2-Clause
 */
#include "hipSYCL/compiler/llvm-to-backend/LLVMToBackend.hpp"
#include "hipSYCL/compiler/llvm-to-backend/ptx/LLVMToPtxFactory.hpp"
#include <fstream>
#include <iostream>
#include <iterator>
int main(int argc, char **argv) {
  if(argc != 2) return 1;
  std::ifstream input{argv[1], std::ios::binary};
  std::string bc{std::istreambuf_iterator<char>{input}, {}};
  auto translator = hipsycl::compiler::createLLVMToPtxTranslator({"test_kernel"});
  translator->setBuildOption("ptx-version", 60);
  translator->setBuildOption("ptx-target-device", 60);
  std::string output;
  if(!translator->fullTransformation(bc, output)) {
    std::cerr << translator->getErrorLogAsString(); return 1;
  }
  if(output.find(".entry test_kernel") == std::string::npos ||
     output.find(".extern .func") != std::string::npos) {
    std::cerr << output; return 2;
  }
  std::cout << "PTX translation with embedded libdevice succeeded (" << output.size() << " bytes)\n";
}
