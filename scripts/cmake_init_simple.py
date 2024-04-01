#!/usr/bin/env python3

from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from sys import stderr

CMAKE_VERSION: str = "3.16"


def eprint(message: str):
    print(f">> {message}", file=stderr)


def notify_skip_file_exist(filepath: Path):
    eprint(f"Skippping '{filepath}': file already exist!")


@dataclass
class Config:
    dir: Path
    name: str
    main: bool = False


def configure_path(path: Path) -> None:
    if not path.exists():
        path.mkdir()

    if not path.is_dir():
        eprint(f"'{dir}' is not a directory")
        return

    # source code goes here
    source = path / "source"
    source.mkdir(exist_ok=True)

    # external libraries not managed by conan (or system) go here
    lib = path / "lib"
    lib.mkdir(exist_ok=True)

    cmake_include_dir = path / "cmake"
    cmake_include_dir.mkdir(exist_ok=True)


def configure_cmake(config: Config, version: str, skip_lib: bool = False) -> None:
    # for main source file
    mainfile = "main" if config.main else config.name

    content = """
        # in-place / in-source build guard

        if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
          message(
            FATAL_ERROR
              "You cannot build in a source directory (or any directory with "
              "CMakeLists.txt file). Please make a build subdirectory. Feel free to "
              "remove 'CMakeCache.txt' and 'CMakeFiles/'.")
        endif()
    """

    cmake_module_dir = config.dir / "cmake"
    cmake_guard = cmake_module_dir / "prelude.cmake"

    if cmake_module_dir.exists():
        if not cmake_guard.exists():
            cmake_guard.write_text(dedent(content.lstrip("\n")))
        else:
            notify_skip_file_exist(cmake_guard.relative_to(config.dir))
    else:
        eprint(
            f"Directory '{cmake_module_dir.relative_to(config.dir)}/' does not exist. Skipped in-place build guard file"
        )

    cmake_guard_include = (
        f"include({str(cmake_guard.relative_to(config.dir))})"
        if (config.dir / "cmake").exists() and cmake_guard.exists()
        else "# DELETE ME: include guard should be included here if it exist "
    )

    content = f"""
        cmake_minimum_required(VERSION {version})
        project({config.name} VERSION 0.1.0)

        {cmake_guard_include}

        set(CMAKE_CXX_STANDARD 20)
        set(CMAKE_CXX_STANDARD_REQUIRED ON)
        set(CMAKE_CXX_EXTENSIONS OFF)
        # set(CMAKE_COLOR_DIAGNOSTICS ON) # You might want to enable this (CMake 3.24+)

        # use mold if it exists in PATH
        find_program(MOLD mold)
        if(MOLD)
          set(CMAKE_EXE_LINKER_FLAGS "-fuse-ld=mold")
          set(CMAKE_SHARED_LINKER_FLAGS "-fuse-ld=mold")
        endif()

        find_package(fmt CONFIG REQUIRED)
        find_package(range-v3 CONFIG REQUIRED)

        # add_subdirectory(lib)

        add_executable({mainfile} source/{mainfile}.cpp)
        target_include_directories({mainfile} PRIVATE source)
        target_link_libraries({mainfile} PRIVATE fmt::fmt range-v3::range-v3)

        # sanitizer
        target_compile_options({mainfile} PRIVATE -fsanitize=address,leak,undefined)
        target_link_options({mainfile} PRIVATE -fsanitize=address,leak,undefined)
    """

    cmake = config.dir / "CMakeLists.txt"
    if not cmake.exists():
        cmake.write_text(dedent(content.lstrip("\n")))
    else:
        notify_skip_file_exist(cmake.relative_to(config.dir))

    if skip_lib:
        return

    # for external libraries
    content = f"""
        # You can add libraries here that are not managed by conan or system.

        # * For example you want to add a new library called 'mylib' to your project.
        #   You have copied the file into 'lib/mylib' directory. It doesn't have a
        #   CMakeLists.txt file, so you need to manually add it to the project.

        set(mylib_DIR "${{CMAKE_CURRENT_SOURCE_DIR}}/mylib")
        set(mylib_INCLUDE_DIRS "${{mylib_DIR}}/include")
        set(mylib_SOURCES "${{mylib_DIR}}/src/mylib.cpp" ...) # declare the sources here

        add_library(mylib STATIC "${{mylib_SOURCES}}")
        target_include_directories(mylib PUBLIC "${{mylib_INCLUDE_DIRS}}")

        # * If the project has a CMakeLists.txt, it is more straightforward. For
        #   example, you have an library copied to 'lib/otherlib':
        add_subdirectory("${{CMAKE_CURRENT_SOURCE_DIR}}/otherlib")

        # you can add more libraries here ...

        # * You can create a variable that emitted from this cmake file that contains
        #   the library targets, so that the parent CMakeLists.txt can use it. Or you
        #   don't, you can just use the library targets directly.
        set(LIB
            mylib
            otherlib
            PARENT_SCOPE)
    """

    cmake_lib = config.dir / "lib" / "CMakeLists.txt"
    if not cmake_lib.exists():
        cmake_lib.write_text(dedent(content.lstrip("\n")))
    else:
        notify_skip_file_exist(cmake_lib.relative_to(config.dir))


def configure_conanfile(config: Config) -> None:
    content = f"""
        from conan import ConanFile

        class Recipe(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain", "CMakeDeps", "VirtualRunEnv"

            def layout(self):
                self.folders.generators = "conan"

            def requirements(self):
                self.requires("fmt/10.1.1")
                self.requires("range-v3/0.12.0")
    """

    conanfile = config.dir / "conanfile.py"
    if not conanfile.exists():
        conanfile.write_text(dedent(content.lstrip("\n")))
    else:
        notify_skip_file_exist(conanfile.relative_to(config.dir))


def configure_cpp_template(config: Config) -> None:
    mainfile = "main" if config.main else config.name

    code = f"""
        #include <fmt/core.h>

        int main() {{
            fmt::println("Hello from '{config.name}'!");
        }}
    """

    cpp = config.dir / "source" / f"{mainfile}.cpp"
    if not cpp.exists():
        cpp.write_text(dedent(code.lstrip("\n")))
    else:
        notify_skip_file_exist(cpp.relative_to(config.dir))


# def configure_gitignore(config: Config):
#     content = f"""
#         build/
#         .cache/
#     """

#     gitignore = config.dir / ".gitignore"
#     if not gitignore.exists():
#         gitignore.write_text(dedent(content))
#     else:
#         notify_skip_file_exist(gitignore.relative_to(config.dir))


def configure_project(config: Config) -> bool:
    # check if CMakeLists.txt already exists and exit
    if (config.dir / "CMakeLists.txt").exists():
        return False

    configure_path(config.dir)
    configure_cmake(config, CMAKE_VERSION)
    configure_conanfile(config)
    configure_cpp_template(config)
    # configure_gitignore(config)

    return True


def main() -> int:
    parse = ArgumentParser(description="CMake Init Simple")
    a = parse.add_argument

    a("dir", help="Directory to initialize")
    a("--name", help="Project name, defaults to directory name", nargs="?")
    a("--main", help="Use 'main' as the main file name", action="store_true")

    a("--only-conan", help="Generate conanfile.py only", action="store_true")
    a("--only-cmake", help="Generate CMakeLists.txt only", action="store_true")

    args = parse.parse_args()

    dir = Path(args.dir).resolve()
    name = args.name or dir.name

    config = Config(dir, name, args.main)

    should_configure_project = not args.only_conan and not args.only_cmake

    if should_configure_project:
        success = configure_project(config)
        if success:
            print(f"Project '{config.name}' initialized in '{config.dir}'")
            return 0
        else:
            eprint(f"Project already initialized in '{config.dir}'")
            return 1
    else:
        if args.only_conan:
            configure_conanfile(config)
        if args.only_cmake:
            configure_cmake(config, CMAKE_VERSION, skip_lib=True)
        print(f"Generation success")
        return 0


if __name__ == "__main__":
    ret = main()
    exit(ret)
