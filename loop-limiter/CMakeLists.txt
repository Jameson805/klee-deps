project(LoopLimiter)
cmake_minimum_required(VERSION 3.1)

find_package(LLVM REQUIRED CONFIG)
add_definitions(${LLVM_DEFINITIONS})
include_directories(${LLVM_INCLUDE_DIRS})
link_directories(${LLVM_LIBRARY_DIRS})

add_library(LoopLimiter MODULE LoopLimiter.cpp)

# Use C++11 to compile our pass (i.e., supply -std=c++11).
target_compile_features(LoopLimiter PRIVATE cxx_range_for cxx_auto_type)

# LLVM is (typically) built with no C++ RTTI. We need to match that.
set_target_properties(LoopLimiter PROPERTIES
    COMPILE_FLAGS "-fno-rtti"
)

# Get proper shared-library behavior (where symbols are not necessarily
# resolved when the shared library is linked) on OS X.
if(APPLE)
    set_target_properties(LoopLimiter PROPERTIES
        LINK_FLAGS "-undefined dynamic_lookup"
    )
endif(APPLE)