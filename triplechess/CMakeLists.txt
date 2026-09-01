cmake_minimum_required(VERSION 3.21)
project(triplechess CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(SCAMORRA_SOURCES
    gameplay.cpp
    ai.cpp
)

# game static lib (idempotent: skipped if already added by a parent project).
if(NOT TARGET game)
    add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../game" game_build)
endif()

if(NOT TARGET triplechess_lib)
    add_library(triplechess_lib STATIC ${SCAMORRA_SOURCES})
    target_include_directories(triplechess_lib PUBLIC . "${CMAKE_CURRENT_SOURCE_DIR}/..")
    target_link_libraries(triplechess_lib PUBLIC game)
endif()

# Rule checks: capture, push, blocked push, suicide, win, bounded self-play.
if(NOT TARGET test)
    add_executable(test test.cpp)
    target_link_libraries(test PRIVATE triplechess_lib)
endif()
