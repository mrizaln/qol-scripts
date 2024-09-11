#!/usr/bin/env python3

from contextlib import chdir
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from sys import stderr
from enum import Enum
import subprocess
import platform

BOOTSTRAP_BINARY_DIR = "build/Debug"
BOOTSTRAP_CMD = f"conan install . --build missing -s build_type=Debug \
        && mkdir -p {BOOTSTRAP_BINARY_DIR}/.cmake/api/v1/query \
        && touch {BOOTSTRAP_BINARY_DIR}/.cmake/api/v1/query/codemodel-v2 \
        && cmake --preset conan-debug \
        && ln -s {BOOTSTRAP_BINARY_DIR}/compile_commands.json . \
        && cmake --build --preset conan-debug"

CPP_STD_TO_CMAKE_VER = {
    20: "3.16",
    23: "3.22",
}

CPP_STD_DEFAULT = 20

MOLD_COMMAND = "mold"


class ProjectType(Enum):
    EXE = 0
    LIB = 1


@dataclass
class Config:
    dir: Path
    name: str
    cpp_ver: int
    cmake_ver: str
    use_mold: bool
    init_git: bool


class CmakeType(Enum):
    EXE_WITH_LIB = 0
    EXE_NO_LIB = 1
    LIB = 2


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
    def cmake_main(
        name: str, main: str, version: str, std: int, includes: list[Path]
    ) -> str:
        preface = f"""
            cmake_minimum_required(VERSION {version})
            project({name} VERSION 0.0.0)
        """

        inc_fmt = """include({})"""
        include = (
            "\n" + "\n".join([inc_fmt.format(str(p)) for p in includes]) + "\n\n"
            if len(includes) > 0
            else "\n"
        )

        content = f"""
            set(CMAKE_CXX_STANDARD {std})
            set(CMAKE_CXX_STANDARD_REQUIRED ON)
            set(CMAKE_CXX_EXTENSIONS OFF)
            # set(CMAKE_COLOR_DIAGNOSTICS ON) # You might want to enable this (CMake 3.24+)

            find_package(fmt REQUIRED)

            # include(cmake/fetched-libs.cmake)

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
    def cmake_library(name: str, description: str) -> str:
        content = f"""
            cmake_minimum_required(VERSION 3.12)

            project(
              {name}
              VERSION     0.0.0
              LANGUAGES   CXX
              DESCRIPTION \"{description}\")

            add_library({name} INTERFACE)
            target_include_directories({name} INTERFACE include)
            target_compile_features({name} INTERFACE cxx_std_20)
            set_target_properties({name} PROPERTIES CXX_EXTENSIONS OFF)
        """

        return Template.__clean(content)

    @staticmethod
    def cmake_fetch() -> str:
        content = """
            set(FETCHCONTENT_QUIET FALSE)

            include(FetchContent)

            # example:
            # ~~~

            # FetchContent_Declare(
            #   vkfw
            #   GIT_REPOSITORY https://github.com/Cvelth/vkfw
            #   GIT_TAG d8bc2f96aa083037ce75b998ec2ac23f9b7782b8)
            # FetchContent_MakeAvailable(vkfw)

            # add_library(vkfw INTERFACE)
            # target_include_directories(vkfw INTERFACE ${vkfw_SOURCE_DIR}/include)
            # target_link_libraries(vkfw INTERFACE glfw)

            # add_library(fetch::vkfw ALIAS vkfw)

            # ~~~
        """
        return Template.__clean(content)

    @staticmethod
    def cmake_lib() -> str:
        content = """
            # You can add libraries here that are not managed by conan or system.

            # * For example you want to add a new library called 'mylib' to your project.
            #   You have copied the file into 'lib/mylib' directory. It doesn't have a
            #   CMakeLists.txt file, so you need to manually add it to the project.

            set(mylib_DIR "${CMAKE_CURRENT_SOURCE_DIR}/mylib")
            set(mylib_INCLUDE_DIRS "${mylib_DIR}/include")
            set(mylib_SOURCES "${mylib_DIR}/src/mylib.cpp" ...) # declare the sources here

            add_library(mylib STATIC "${mylib_SOURCES}")
            target_include_directories(mylib PUBLIC "${mylib_INCLUDE_DIRS}")

            # * If the project has a CMakeLists.txt, it is more straightforward. For
            #   example, you have an library copied to 'lib/otherlib':
            add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/otherlib")

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
            from conan.tools.cmake import cmake_layout

            class Recipe(ConanFile):
                settings   = ["os", "compiler", "build_type", "arch"]
                generators = ["CMakeToolchain", "CMakeDeps"]
                requires   = ["fmt/10.2.1"]

                def layout(self):
                    cmake_layout(self)
        """
        return Template.__clean(content)

    @staticmethod
    def main_cpp(name: str, std: int) -> str:
        content = ""
        match std:
            case 20:
                content = f"""
                    #include <fmt/core.h>

                    int main()
                    {{
                        fmt::println("Hello from '{name}'!");
                    }}
                """
            case 23:
                content = f"""
                    #include <print>

                    int main()
                    {{
                        std::println("Hello from '{name}'!");
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


def command_exists(command: str) -> bool:
    cmd = "where" if platform.system() == "Windows" else "which"
    try:
        null = subprocess.DEVNULL
        subprocess.run([cmd, command], stdout=null, stderr=null).check_returncode()
        return True
    except:
        return False


def configure_path(path: Path, project_type: ProjectType) -> None:
    if not path.exists():
        path.mkdir()

    if not path.is_dir():
        eprint(f"'{dir}' is not a directory")
        return

    # source code goes here
    source = path / "source"
    source.mkdir(exist_ok=True)

    match project_type:
        case ProjectType.EXE:
            # external libraries not managed by conan (or system) go here
            lib = path / "lib"
            lib.mkdir(exist_ok=True)

            cmake_include_dir = path / "cmake"
            cmake_include_dir.mkdir(exist_ok=True)
        case ProjectType.LIB:
            include = path / "include"
            include.mkdir(exist_ok=True)


def configure_cmake(config: Config, cmake_type: CmakeType) -> None:
    match cmake_type:
        case CmakeType.EXE_WITH_LIB:
            configure_cmake_exe(config, skip_lib=False)
        case CmakeType.EXE_NO_LIB:
            configure_cmake_exe(config, skip_lib=True)
        case CmakeType.LIB:
            configure_cmake_library(config)


def configure_cmake_library(config: Config) -> None:
    cmake_main = config.dir / "CMakeLists.txt"
    if not cmake_main.exists():
        text = Template.cmake_library(config.name, "<Library description>")
        cmake_main.write_text(text)
    else:
        notify_skip_file_exist(cmake_main.relative_to(config.dir))
    pass


def configure_cmake_exe(config: Config, skip_lib: bool = False) -> None:
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
    if cmake_module_dir.exists() and config.use_mold and command_exists(MOLD_COMMAND):
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
        text = Template.cmake_main(
            config.name, "main", config.cmake_ver, config.cpp_ver, includes
        )
        cmake.write_text(text)
    else:
        notify_skip_file_exist(cmake.relative_to(config.dir))

    if skip_lib:
        return

    # -------- [ cmake for FetchContent ] --------
    cmake_fetch = cmake_module_dir / "fetched-libs.cmake"
    if cmake_module_dir.exists():
        if not cmake_fetch.exists():
            text = Template.cmake_fetch()
            cmake_fetch.write_text(text)
        else:
            notify_skip_file_exist(cmake_fetch.relative_to(config.dir))
    else:
        err_cmake_dir("Skipped FetchContent configuration")

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
    cpp = config.dir / "source" / "main.cpp"
    if not cpp.exists():
        text = Template.main_cpp(config.name, config.cpp_ver)
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


def configure_project(config: Config, project_type: ProjectType) -> bool:
    # check if CMakeLists.txt already exists and exit
    if (config.dir / "CMakeLists.txt").exists():
        return False

    match project_type:
        case ProjectType.EXE:
            configure_path(config.dir, project_type)
            configure_cmake(config, CmakeType.EXE_WITH_LIB)
            configure_conanfile(config)
            configure_cpp_template(config)
        case ProjectType.LIB:
            configure_path(config.dir, project_type)
            configure_cmake(config, CmakeType.LIB)

    if config.init_git:
        configure_git(config)

    return True


def bootstrap_project(config: Config) -> Path | None:
    command = " ".join(BOOTSTRAP_CMD.split())  # remove repeated spaces
    completed_process = subprocess.run(command, shell=True)
    try:
        completed_process.check_returncode()
    except subprocess.CalledProcessError as e:
        eprint(f"Failed to bootstrap: {e}")
        return None

    return config.dir / BOOTSTRAP_BINARY_DIR / "main"


def main() -> int:
    parse = ArgumentParser(description="CMake Init Simple")
    a = parse.add_argument

    a("dir", help="Directory to initialize")
    a("--name", help="Project name, defaults to directory name", nargs="?")
    a("--lib", help="Initialize as library", action="store_true")
    a("--std", help=f"C++ standard, defaults to {CPP_STD_DEFAULT}", nargs="?", type=int)
    a("--git", help="Initialize git repository", action="store_true")
    a("--no-bootstrap", help="Don't bootstrap the project", action="store_true")
    a("--mold", help="Use mold as linker if it exists on path", action="store_true")

    a("--bootstrap-only", help="Bootstrap only the project", action="store_true")
    a("--cmake-only", help="Generate CMakeLists.txt only", action="store_true")
    a("--conan-only", help="Generate conanfile.py only", action="store_true")

    args = parse.parse_args()

    dir = Path(args.dir).resolve()
    std = args.std or CPP_STD_DEFAULT
    name = args.name or dir.name
    name = name.replace(" ", "-")
    use_mold = args.mold
    init_git = args.git
    project_type = ProjectType.LIB if args.lib else ProjectType.EXE

    if std not in CPP_STD_TO_CMAKE_VER:
        eprint(f"Invalid C++ version: {std}")
        eprint(f"Supported versions: {list(CPP_STD_TO_CMAKE_VER.keys())}")
        return 1

    if dir.exists() and not dir.is_dir():
        eprint(f"'{dir}' is not a directory!")
        return 1

    if dir.exists() and any(dir.iterdir()):
        response = input(f"'{dir}' is not empty, continue? [y/N] ")
        if not response.lower() == "y" and not response.lower() == "yes":
            eprint(f"Operation aborted")
            return 1

    config = Config(dir, name, std, CPP_STD_TO_CMAKE_VER[std], use_mold, init_git)

    should_configure = not (args.conan_only or args.cmake_only or args.bootstrap_only)
    should_bootstrap = not args.no_bootstrap and not args.lib

    if not should_configure:
        if args.conan_only:
            configure_conanfile(config)
        if args.cmake_only:
            configure_cmake(config, CmakeType.EXE_NO_LIB)
        if args.bootstrap_only:
            print("Bootstrapping project...")
            binary = bootstrap_project(config)
            if binary is None:
                print("Bootstrapping failed, see previous error")
            else:
                print("\nBootstrapping completed.\n")
                subprocess.run(binary)
        print(f"Generation success")
        return 0

    success = configure_project(config, project_type)
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
