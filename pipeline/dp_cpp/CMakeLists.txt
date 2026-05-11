cmake_minimum_required(VERSION 3.17)
project(dp_cpp C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Release by default for speed; override with -DCMAKE_BUILD_TYPE=Debug
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_compile_options(-Wall -Wextra -O2)

# ---- Dependencies ----
find_package(HDF5 REQUIRED COMPONENTS C)
find_package(yaml-cpp REQUIRED)

# ---- Sources ----
set(SOURCES
    src/physics.cpp
    src/geo_grid.cpp
    src/route.cpp
    src/nodes.cpp
    src/weather.cpp
    src/frame.cpp
    src/atomic_edges.cpp
    src/bellman.cpp
    src/bellman_locked.cpp
    src/main.cpp
)

add_executable(dp_rebuild ${SOURCES})

target_include_directories(dp_rebuild PRIVATE
    src
    ${HDF5_INCLUDE_DIRS}
)

target_link_libraries(dp_rebuild PRIVATE
    ${HDF5_LIBRARIES}
    yaml-cpp
)
