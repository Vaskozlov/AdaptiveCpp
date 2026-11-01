/*
 * This file is part of AdaptiveCpp, an implementation of SYCL and C++ standard
 * parallelism for CPUs and GPUs.
 *
 * Copyright The AdaptiveCpp Contributors
 *
 * AdaptiveCpp is released under the BSD 2-Clause "Simplified" License.
 * See file LICENSE in the project root for full license details.
 */
// SPDX-License-Identifier: BSD-2-Clause
#ifndef HIPSYCL_CUDA_DEVICE_MANAGER_HPP
#define HIPSYCL_CUDA_DEVICE_MANAGER_HPP

namespace hipsycl {
namespace rt {

/// Activates the device primary context on the calling thread.
/// Hardware contexts own its lifetime. Rebind on every activation, including
/// after external CUDA calls change the current context.
class cuda_device_manager
{
public:
  void activate_device(int device_id);
  int get_active_device() const;

  static cuda_device_manager &get() {
    static thread_local cuda_device_manager instance;
    return instance;
  }

private:
  int _device = -1;

  cuda_device_manager() = default;
};

}
}

#endif
