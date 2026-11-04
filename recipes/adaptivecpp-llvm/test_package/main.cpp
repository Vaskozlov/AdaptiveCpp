#include <sycl/sycl.hpp>

int main() {
  sycl::queue queue{sycl::cpu_selector_v};
  int *result = sycl::malloc_shared<int>(1, queue);
  if(!result)
    return 1;
  *result = 0;
  queue.single_task([=] { *result = 42; }).wait_and_throw();
  const bool passed = *result == 42;
  sycl::free(result, queue);
  return passed ? 0 : 1;
}
