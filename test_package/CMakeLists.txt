cmake_minimum_required(VERSION 3.15)
project(AdaptiveCppPackageTest LANGUAGES CXX)

find_package(AdaptiveCpp CONFIG REQUIRED)
add_executable(package_test src/main.cpp)
target_compile_features(package_test PRIVATE cxx_std_17)
add_sycl_to_target(TARGET package_test)
