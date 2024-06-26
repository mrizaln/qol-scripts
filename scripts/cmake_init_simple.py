#!/usr/bin/env python3

from contextlib import chdir
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from sys import stderr
import subprocess

CMAKE_VERSION: str = "3.16"
BOOTSTRAP_BINARY_DIR = "build/debug"
BOOTSTRAP_COMMAND = f"conan install . -of {BOOTSTRAP_BINARY_DIR} --build missing -s build_type=Debug \
        && mkdir -p {BOOTSTRAP_BINARY_DIR}/.cmake/api/v1/query \
        && touch {BOOTSTRAP_BINARY_DIR}/.cmake/api/v1/query/codemodel-v2 \
        && cmake --preset conan-debug \
        && ln -s {BOOTSTRAP_BINARY_DIR}/compile_commands.json . \
        && cmake --build --preset conan-debug"


@dataclass
class Config:
    dir: Path
    name: str
    main: bool = False


# this is supposed to be a namespace (i don't want to create multiple files)
class Template:
    @staticmethod
    def __clean(content: str) -> str:
        return dedent(content.lstrip("\n"))

    @staticmethod
    def cmake_guard() -> str:
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
        return Template.__clean(content)

    @staticmethod
    def cmake_mold() -> str:
        content = """
            # use mold if it exist in path
            find_program(MOLD mold)
            if(MOLD)
              set(CMAKE_EXE_LINKER_FLAGS "-fuse-ld=mold")
              set(CMAKE_SHARED_LINKER_FLAGS "-fuse-ld=mold")
              message(STATUS "mold executable found: ${MOLD}")
            endif()
        """
        return Template.__clean(content)

    @staticmethod
    def cmake_main(name: str, main: str, version: str, includes: list[Path]) -> str:
        preface = f"""
            cmake_minimum_required(VERSION {version})
            project({name} VERSION 0.0.1)
        """

        inc_fmt = """include({})"""
        include = (
            "\n" + "\n".join([inc_fmt.format(str(p)) for p in includes]) + "\n\n"
            if len(includes) > 0
            else "\n"
        )

        content = f"""
            set(CMAKE_CXX_STANDARD 20)
            set(CMAKE_CXX_STANDARD_REQUIRED ON)
            set(CMAKE_CXX_EXTENSIONS OFF)
            # set(CMAKE_COLOR_DIAGNOSTICS ON) # You might want to enable this (CMake 3.24+)

            find_package(fmt REQUIRED)

            # add_subdirectory(lib)

            add_executable({main} source/{main}.cpp)
            target_include_directories({main} PRIVATE source)
            target_link_libraries({main} PRIVATE fmt::fmt)
            target_compile_options({main} PRIVATE -Wall -Wextra -Wconversion -Wswitch-enum)

            # sanitizer
            target_compile_options({main} PRIVATE -fsanitize=address,leak,undefined)
            target_link_options({main} PRIVATE -fsanitize=address,leak,undefined)
        """

        return Template.__clean(preface) + include + Template.__clean(content)

    @staticmethod
    def cmake_lib() -> str:
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
        return Template.__clean(content)

    @staticmethod
    def conanfile() -> str:
        content = f"""
            from conan import ConanFile

            class Recipe(ConanFile):
                settings   = ["os", "compiler", "build_type", "arch"]
                generators = ["CMakeToolchain", "CMakeDeps"]
                requires   = ["fmt/10.2.1"]

                def layout(self):
                    self.folders.generators = "conan"
        """
        return Template.__clean(content)

    @staticmethod
    def main_cpp(name: str) -> str:
        content = f"""
            #include <fmt/core.h>

            int main() {{
                fmt::println("Hello from '{name}'!");
            }}
        """
        return Template.__clean(content)

    @staticmethod
    def gitignore() -> str:
        content = f"""
            **/build/
            .cache/
        """
        return Template.__clean(content)


def eprint(message: str):
    print(f">> {message}", file=stderr)


def notify_skip_file_exist(filepath: Path):
    eprint(f"Skippping '{filepath}': file already exist!")


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
    cmake_module_dir = config.dir / "cmake"
    err_cmake_dir = lambda msg: eprint(
        f"Directory '{cmake_module_dir.relative_to(config.dir)}' does not exist. {msg}"
    )

    # -------- [ in-place build guard ] ----------
    cmake_guard = cmake_module_dir / "prelude.cmake"
    if cmake_module_dir.exists():
        if not cmake_guard.exists():
            text = Template.cmake_guard()
            cmake_guard.write_text(text)
        else:
            notify_skip_file_exist(cmake_guard.relative_to(config.dir))
    else:
        err_cmake_dir("Skipped in-place build guard file")

    # -------- [ mold include ] ----------
    cmake_mold = cmake_module_dir / "mold.cmake"
    if cmake_module_dir.exists():
        if not cmake_mold.exists():
            text = Template.cmake_mold()
            cmake_mold.write_text(text)
        else:
            notify_skip_file_exist(cmake_mold.relative_to(config.dir))
    else:
        err_cmake_dir("Skipped mold configuration")

    # -------- [ main cmake file ] ----------
    cmake = config.dir / "CMakeLists.txt"
    if not cmake.exists():
        includes: list[Path] = []
        if (config.dir / "cmake").exists() and cmake_guard.exists():
            includes.append(cmake_guard.relative_to(config.dir))
        if (config.dir / "cmake").exists() and cmake_mold.exists():
            includes.append(cmake_mold.relative_to(config.dir))
        mainfile = "main" if config.main else config.name
        text = Template.cmake_main(config.name, mainfile, version, includes)
        cmake.write_text(text)
    else:
        notify_skip_file_exist(cmake.relative_to(config.dir))

    if skip_lib:
        return

    # -------- [ cmake for external libraries ] ----------
    cmake_lib = config.dir / "lib" / "CMakeLists.txt"
    if not cmake_lib.exists():
        text = Template.cmake_lib()
        cmake_lib.write_text(text)
    else:
        notify_skip_file_exist(cmake_lib.relative_to(config.dir))


def configure_conanfile(config: Config) -> None:
    conanfile = config.dir / "conanfile.py"
    if not conanfile.exists():
        text = Template.conanfile()
        conanfile.write_text(text)
    else:
        notify_skip_file_exist(conanfile.relative_to(config.dir))


def configure_cpp_template(config: Config) -> None:
    mainfile = "main" if config.main else config.name
    cpp = config.dir / "source" / f"{mainfile}.cpp"
    if not cpp.exists():
        text = Template.main_cpp(config.name)
        cpp.write_text(text)
    else:
        notify_skip_file_exist(cpp.relative_to(config.dir))


def configure_git(config: Config):
    try:
        with chdir(config.dir):
            subprocess.run(["git", "init"]).check_returncode()
    except subprocess.CalledProcessError as e:
        eprint(f"Failed to initialize git: {e}")

    gitignore = config.dir / ".gitignore"
    if not gitignore.exists():
        text = Template.gitignore()
        gitignore.write_text(text)
    else:
        notify_skip_file_exist(gitignore.relative_to(config.dir))


def configure_project(config: Config, init_git: bool) -> bool:
    # check if CMakeLists.txt already exists and exit
    if (config.dir / "CMakeLists.txt").exists():
        return False

    configure_path(config.dir)
    configure_cmake(config, CMAKE_VERSION)
    configure_conanfile(config)
    configure_cpp_template(config)

    if init_git:
        configure_git(config)

    return True


def bootstrap_project(config: Config) -> Path | None:
    command = " ".join(BOOTSTRAP_COMMAND.split())  # remove repeated spaces
    completed_process = subprocess.run(command, shell=True)
    try:
        completed_process.check_returncode()
    except subprocess.CalledProcessError as e:
        eprint(f"Failed to bootstrap: {e}")
        return None

    mainfile = "main" if config.main else config.name
    return config.dir / BOOTSTRAP_BINARY_DIR / mainfile


def main() -> int:
    parse = ArgumentParser(description="CMake Init Simple")
    a = parse.add_argument

    a("dir", help="Directory to initialize")
    a("--name", help="Project name, defaults to directory name", nargs="?")
    a("--main", help="Use 'main' as the main file name", action="store_true")
    a("--git", help="Initialize git repository", action="store_true")
    a("--no-bootstrap", help="Don't bootstrap the project", action="store_true")

    a("--conan-only", help="Generate conanfile.py only", action="store_true")
    a("--cmake-only", help="Generate CMakeLists.txt only", action="store_true")

    args = parse.parse_args()

    dir = Path(args.dir).resolve()
    name = args.name or dir.name

    config = Config(dir, name, args.main)

    should_configure_project = not args.conan_only and not args.cmake_only
    should_bootstrap = not args.no_bootstrap

    if not should_configure_project:
        if args.conan_only:
            configure_conanfile(config)
        if args.cmake_only:
            configure_cmake(config, CMAKE_VERSION, skip_lib=True)
        print(f"Generation success")
        return 0

    success = configure_project(config, args.git)
    if not success:
        eprint(f"Project already initialized in '{config.dir}'")
        return 1

    print(f"Project '{config.name}' initialized in '{config.dir}'")

    if not should_bootstrap:
        return 0

    with chdir(dir):
        print("Bootstrapping project...")
        binary = bootstrap_project(config)
        if binary is None:
            print("Bootstrapping failed, see previous error")
        else:
            print("\nBootstrapping completed.\n")
            subprocess.run(binary)

    return 0


if __name__ == "__main__":
    ret = main()
    exit(ret)
