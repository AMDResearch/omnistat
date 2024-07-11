from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
import os, sys, subprocess, platform


class CMakeExtension(Extension):
    def __init__(self, name, cmake_lists_dir=".", **kwa):
        Extension.__init__(self, name, sources=[], **kwa)
        self.cmake_lists_dir = os.path.abspath(cmake_lists_dir)


class CMakeBuild(build_ext):
    def build_extensions(self):
        try:
            out = subprocess.check_output(["cmake", "--version"])
        except OSError:
            raise RuntimeError("Cannot find CMake executable")

        for ext in self.extensions:

            extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))
            cfg = "Release"

            cmake_args = [
                "-DCMAKE_BUILD_TYPE=%s" % cfg,
                "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{}={}".format(cfg.upper(), extdir),
                "-DCMAKE_ARCHIVE_OUTPUT_DIRECTORY_{}={}".format(cfg.upper(), self.build_temp),
                "-DPYTHON_EXECUTABLE={}".format(sys.executable),
            ]

            if not os.path.exists(self.build_temp):
                os.makedirs(self.build_temp)

            subprocess.check_call(["cmake", ext.cmake_lists_dir] + cmake_args, cwd=self.build_temp)
            subprocess.check_call(["cmake", "--build", "."], cwd=self.build_temp)


setup(
    name="pyrocprofiler",
    version="0.1",
    ext_modules=[CMakeExtension("pyrocprofiler")],
    cmdclass={"build_ext": CMakeBuild},
)
