cmake_minimum_required(VERSION 3.16)
project(fretboard_math LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

add_library(fretboard_math SHARED
    fretboard_math.cpp
    fretboard_math.h
)

target_include_directories(fretboard_math PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_definitions(fretboard_math PRIVATE FRETENGINE_EXPORTS)

if(WIN32)
    set_target_properties(fretboard_math PROPERTIES
        PREFIX ""
        SUFFIX ".dll"
    )
endif()
