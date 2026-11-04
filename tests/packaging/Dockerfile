FROM debian:trixie-slim

# Dependency acquisition is deliberately separate from the network-disabled
# configure/build/package test. No CUDA toolkit or NVIDIA driver is installed.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates cmake ninja-build git \
      clang-19 llvm-19-dev libclang-19-dev libclang-cpp19-dev lld-19 libomp-19-dev \
      dpkg-dev file python3 python3-venv \
    && python3 -m venv /opt/conan \
    && /opt/conan/bin/pip install --no-cache-dir 'conan==2.34.0' \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/conan/bin:${PATH}"
ENV CONAN_HOME=/work/conan
WORKDIR /work
