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
  // Turing, Ampere, Ada and Blackwell requests must all produce PTX with
  // the installed compiler, even when that compiler predates the GPU.
  const hipsycl::compiler::PtxTarget requests[] = {
      {75, 63}, {86, 71}, {89, 78}, {120, 88}};
  for(auto request : requests) {
    auto target = hipsycl::compiler::selectLLVMToPtxTarget(
        request.architecture, request.version);
    if(target.architecture > request.architecture || target.version > request.version)
      return 1;
    if(request.architecture == 75 && target.architecture != 75)
      return 1;
    auto translator = hipsycl::compiler::createLLVMToPtxTranslator({"test_kernel"});
    translator->setBuildOption("ptx-version", target.version);
    translator->setBuildOption("ptx-target-device", target.architecture);
    std::string output;
    if(!translator->fullTransformation(bc, output)) {
      std::cerr << translator->getErrorLogAsString(); return 1;
    }
    if(output.find(".entry test_kernel") == std::string::npos ||
       output.find(".extern .func") != std::string::npos ||
       output.find(".target sm_" + std::to_string(target.architecture)) == std::string::npos) {
      std::cerr << output; return 2;
    }
    std::cout << "Requested sm_" << request.architecture << " / PTX " << request.version
              << " -> sm_" << target.architecture << " / PTX " << target.version
              << ": embedded libdevice PTX translation passed\n";
  }
}
