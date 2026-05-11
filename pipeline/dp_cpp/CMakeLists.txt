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
set(SR_SOURCES
    src/physics.cpp
    src/geo_grid.cpp
    src/route.cpp
    src/nodes.cpp
    src/weather.cpp
    src/frame.cpp
    src/atomic_edges.cpp
    src/bellman.cpp
    src/SR_main.cpp
)

add_executable(dp_SR ${SR_SOURCES})

target_include_directories(dp_SR PRIVATE
    src
    ${HDF5_INCLUDE_DIRS}
)

target_link_libraries(dp_SR PRIVATE
    ${HDF5_LIBRARIES}
    yaml-cpp
)

# ---- Luo DP (integer-nm block grid) ----
set(LUO_SOURCES
    src/physics.cpp
    src/geo_grid.cpp
    src/route.cpp
    src/nodes.cpp
    src/weather.cpp
    src/frame.cpp
    src/luo_main.cpp
)

add_executable(dp_luo ${LUO_SOURCES})

target_include_directories(dp_luo PRIVATE
    src
    ${HDF5_INCLUDE_DIRS}
)

target_link_libraries(dp_luo PRIVATE
    ${HDF5_LIBRARIES}
    yaml-cpp
)
