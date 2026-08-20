cmake_minimum_required(VERSION 3.21)
project(air_land_sea CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# game static lib (idempotent: skipped if already added by a parent project).
if(NOT TARGET game)
    add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../game" game_build)
endif()

if(NOT TARGET air_land_sea_lib)
    add_library(air_land_sea_lib STATIC gameplay.cpp)
    target_include_directories(air_land_sea_lib PUBLIC . "${CMAKE_CURRENT_SOURCE_DIR}/..")
    target_link_libraries(air_land_sea_lib PUBLIC game)
endif()

# Rules checks plus a batch of random games, to catch a rule that stops the
# game from ever ending.
if(NOT TARGET air_land_sea_test)
    add_executable(air_land_sea_test test.cpp)
    target_link_libraries(air_land_sea_test PRIVATE air_land_sea_lib)
endif()
