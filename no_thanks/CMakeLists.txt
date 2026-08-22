cmake_minimum_required(VERSION 3.21)
project(no_thanks CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# game static lib (idempotent: skipped if already added by a parent project).
if(NOT TARGET game)
    add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../game" game_build)
endif()

if(NOT TARGET no_thanks_lib)
    add_library(no_thanks_lib STATIC gameplay.cpp)
    target_include_directories(no_thanks_lib PUBLIC . "${CMAKE_CURRENT_SOURCE_DIR}/..")
    target_link_libraries(no_thanks_lib PUBLIC game)
endif()

# Rules checks plus a batch of random games, to catch a rule that stops the
# game from ever ending.
if(NOT TARGET no_thanks_test)
    add_executable(no_thanks_test test.cpp)
    target_link_libraries(no_thanks_test PRIVATE no_thanks_lib)
endif()
