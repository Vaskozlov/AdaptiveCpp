#include <sycl/sycl.hpp>

int main() {
  int result = 0;
  // Exercise generic JIT compilation on the CPU; no NVIDIA GPU is required.
  sycl::queue queue{sycl::cpu_selector_v};
  {
    sycl::buffer<int> buffer{&result, sycl::range<1>{1}};
    queue.submit([&](sycl::handler &handler) {
      auto output = buffer.get_access<sycl::access::mode::write>(handler);
      handler.single_task([=]() { output[0] = 42; });
    });
    queue.wait_and_throw();
  }
  return result == 42 ? 0 : 1;
}
