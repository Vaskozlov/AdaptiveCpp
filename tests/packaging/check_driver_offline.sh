#!/bin/sh
# Run inside tests/packaging/Dockerfile with docker run --network=none.
set -eu

source_dir=${1:-/src}
output_dir=${2:-/output}
mkdir -p /work/source "$output_dir"
# Keep the bind-mounted checkout read-only and exclude local build artifacts.
tar -C "$source_dir" --exclude=.git --exclude='build*' --exclude=__pycache__ \
  --exclude=CMakeUserPresets.json --exclude=.venv \
  -cf - . | tar -C /work/source -xf -
cd /work/source

case "$(uname -m)" in
  aarch64) conan_arch=armv8 ;;
  x86_64) conan_arch=x86_64 ;;
  *) echo 'Unsupported validation architecture' >&2; exit 1 ;;
esac
cat > /work/profile <<EOF
[settings]
os=Linux
arch=$conan_arch
compiler=clang
compiler.version=19
compiler.libcxx=libstdc++11
compiler.cppstd=17
build_type=Release
[options]
adaptivecpp/*:llvm_version=19.1.7
[conf]
tools.build:compiler_executables={"c": "/usr/bin/clang-19", "cpp": "/usr/bin/clang++-19"}
tools.cmake.cmaketoolchain:generator=Ninja
tools.build:jobs=2
user.adaptivecpp:llvm_dir=/usr/lib/llvm-19/lib/cmake/llvm
[buildenv]
CTEST_OUTPUT_ON_FAILURE=1
OMP_NUM_THREADS=2
EOF

python3 tests/packaging/test_recipe.py
export ACPP_APPDB_DIR=/work/appdb
conan create . -pr:h /work/profile -pr:b /work/profile --no-remote
package_version=$(conan inspect . --format=json | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')

# Test the unmodified source build too: driver-only mode alone must choose
# the full profile and disable other GPU backends without auxiliary flags.
cmake -S . -B /work/direct -G Ninja \
  -DACPP_CUDA_DRIVER_ONLY=ON -DACPP_BUILD_CUDA_DRIVER_TESTS=ON \
  -DLLVM_DIR=/usr/lib/llvm-19/lib/cmake/llvm \
  -DCMAKE_C_COMPILER=clang-19 -DCMAKE_CXX_COMPILER=clang++-19 \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr \
  --trace-expand --trace-format=json-v1 --trace-redirect="$output_dir/configure-trace.jsonl"
cmake --build /work/direct --parallel 2
ctest --test-dir /work/direct --output-on-failure
python3 - "$output_dir/configure-trace.jsonl" <<'PY'
import json
import sys
for line in open(sys.argv[1]):
    entry = json.loads(line)
    command = entry.get("cmd", "").lower()
    if command in ("fetchcontent_makeavailable", "fetchcontent_populate", "externalproject_add"):
        raise SystemExit(f"Unexpected dependency acquisition: {entry}")
    if command == "file" and entry["args"][0].upper() in ("DOWNLOAD", "UPLOAD"):
        raise SystemExit(f"Unexpected file transfer: {entry}")
print("No download operations in the executed CMake trace")
PY

# Fail closed even when a caller explicitly selects another GPU backend.
if cmake -S . -B /work/reject-download \
    -DACPP_CUDA_DRIVER_ONLY=ON -DWITH_LEVEL_ZERO_BACKEND=ON \
    -DLLVM_DIR=/usr/lib/llvm-19/lib/cmake/llvm \
    -DCMAKE_C_COMPILER=clang-19 -DCMAKE_CXX_COMPILER=clang++-19 \
    > "$output_dir/reject-download.log" 2>&1; then
  echo 'A backend requiring downloads unexpectedly configured' >&2
  exit 1
fi
grep -q 'explicitly enable ACPP_ALLOW_DOWNLOADS' "$output_dir/reject-download.log"

# The option identifying the external LLVM dependency must match reality.
if cmake -S . -B /work/reject-llvm \
    -DACPP_CUDA_DRIVER_ONLY=ON -DACPP_EXPECTED_LLVM_VERSION=18.1.8 \
    -DLLVM_DIR=/usr/lib/llvm-19/lib/cmake/llvm \
    -DCMAKE_C_COMPILER=clang-19 -DCMAKE_CXX_COMPILER=clang++-19 \
    > "$output_dir/reject-llvm.log" 2>&1; then
  echo 'An incorrect LLVM package identity unexpectedly configured' >&2
  exit 1
fi
grep -q 'Expected LLVM 18.1.8, found 19.1.7' "$output_dir/reject-llvm.log"

# The Conan build tree must remain usable by ordinary CPack.
conan graph info --requires="adaptivecpp/$package_version" \
  -pr:h /work/profile -pr:b /work/profile --no-remote --format=json > /work/graph.json
package_id=$(python3 -c 'import json; print(json.load(open("/work/graph.json"))["graph"]["nodes"]["1"]["package_id"])')
cache_build=$(conan cache path "adaptivecpp/$package_version:$package_id" --folder=build)
cpack --config "$cache_build/build/conan/Release/CPackConfig.cmake" -G DEB -B "$output_dir"
for deb in "$output_dir"/*.deb; do
  dpkg-deb --info "$deb"
done
dpkg-deb --contents "$output_dir/AdaptiveCpp-$package_version-Linux-Runtime.deb" \
  > "$output_dir/runtime-contents.txt"
dpkg-deb --contents "$output_dir/AdaptiveCpp-$package_version-Linux-Development.deb" \
  > "$output_dir/development-contents.txt"
grep -q './usr/lib/hipSYCL/ext/llvm/bin/llc' "$output_dir/runtime-contents.txt"
grep -q './usr/share/licenses/AdaptiveCpp/LLVM-LICENSE.txt' "$output_dir/runtime-contents.txt"
grep -q './usr/bin/acpp' "$output_dir/development-contents.txt"
dpkg-deb -f "$output_dir/AdaptiveCpp-$package_version-Linux-Runtime.deb" Depends \
  > "$output_dir/runtime-dependencies.txt"
grep -q 'libllvm19' "$output_dir/runtime-dependencies.txt"
