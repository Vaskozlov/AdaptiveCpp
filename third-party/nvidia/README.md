# Bundled NVIDIA build inputs

These files were supplied with this project customization and are preserved
byte for byte. They let driver-only builds work from a source checkout without
an installed CUDA toolkit, an NVIDIA driver, or a network download.

`include/cuda.h` reports CUDA API version 11.8 (`CUDA_VERSION=11080`).
`libdevice/libdevice.10.bc` is the supplied NVIDIA device math bitcode; its
original SDK version was not supplied separately.

| File | SHA-256 |
| --- | --- |
| `include/cuda.h` | `b30a4a84da0bd6d034933fc430955a46432b219d1a61f9a9875b31e8b0494c12` |
| `libdevice/libdevice.10.bc` | `1fc1bc8d4131d5a59a91fc26f4908886e231f842c9e83ae951979ff3df82bdb5` |

CMake uses these files by default when `ACPP_CUDA_DRIVER_ONLY=ON`.
`ACPP_CUDA_DRIVER_INCLUDE_DIR`, `ACPP_CUDA_LIBDEVICE`, and
`CUDA_DEVICE_LIBS_PATH` can select external replacements. Libdevice is embedded
in the PTX JIT library at build time; the runtime package does not need a
separate copy of the bitcode file. The driver header is a private build input.

The NVIDIA files retain their own licensing and are not relicensed under
AdaptiveCpp's BSD license. The header's original notice is retained in full,
reproduced in `NOTICE.txt`, and installed with CUDA-enabled runtime packages.
For the CUDA 11.8 SDK terms, see the
[NVIDIA CUDA EULA](https://docs.nvidia.com/cuda/archive/11.8.0/eula/index.html).
Bundling these files does not grant additional redistribution rights.

When replacing either asset, preserve its notices, update this provenance and
its checksum, and rerun the driver backend and embedded-libdevice tests.
