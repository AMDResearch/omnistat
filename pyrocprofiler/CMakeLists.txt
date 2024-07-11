cmake_minimum_required(VERSION 3.21)

project(
    pyrocprofiler
    VERSION 0.1
    DESCRIPTION "Python wrapper for rocprofiler's device mode"
)

add_compile_definitions(__HIP_PLATFORM_AMD__)

if(DEFINED ENV{ROCM_PATH} AND NOT "$ENV{ROCM_PATH}" STREQUAL "")
    set(ROCM_PATH "$ENV{ROCM_PATH}")
endif()

find_package(hip REQUIRED)
find_package(PythonLibs REQUIRED)

find_path(
    ROCPROFILER_INCLUDE_DIR
    NAMES rocprofiler.h
    HINTS ${ROCM_PATH}
    PATHS ${ROCM_PATH}
    PATH_SUFFIXES include/rocprofiler/v2
    )

find_library(
    ROCPROFILER_LIBRARY
    NAMES ${CMAKE_SHARED_LIBRARY_PREFIX}rocprofiler64v2${CMAKE_SHARED_LIBRARY_SUFFIX}
    HINTS ${ROCM_PATH}
    PATHS ${ROCM_PATH}
    PATH_SUFFIXES lib lib64
    NO_DEFAULT_PATH)

add_library(rocprofiler::rocprofiler INTERFACE IMPORTED)
target_link_libraries(rocprofiler::rocprofiler INTERFACE ${ROCPROFILER_LIBRARY})

add_library(pyrocprofiler SHARED)

set_target_properties(
    pyrocprofiler
    PROPERTIES
        CMAKE_CXX_STANDARD 17
        CMAKE_CXX_STANDARD_REQUIRED ON
        CMAKE_CXX_EXTENSIONS OFF
        PREFIX ""
        OUTPUT_NAME "pyrocprofiler"
        LINKER_LANGUAGE C
    )

target_sources(pyrocprofiler PRIVATE
    "pyrocprofiler_module.cpp"
    "device_session_py_type.cpp"
    )

target_include_directories(pyrocprofiler PRIVATE ${PYTHON_INCLUDE_DIR})
target_include_directories(pyrocprofiler PRIVATE ${HIP_INCLUDE_DIR})
target_include_directories(pyrocprofiler PRIVATE ${ROCPROFILER_INCLUDE_DIR})

target_link_libraries(pyrocprofiler PRIVATE ${PYTHON_LIBRARIES})
target_link_libraries(pyrocprofiler PRIVATE hip::host)
target_link_libraries(pyrocprofiler PRIVATE rocprofiler::rocprofiler)
