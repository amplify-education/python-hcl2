"""Used by dependencies_check.yml to verify if dependencies between pyproject.yml and requirements.txt are in sync"""
import sys
from typing import Set
import difflib
import tomli


def get_pyproject_deps() -> Set[str]:
    with open("pyproject.toml", "rb") as f:
        pyproject_data = tomli.load(f)
    return set(pyproject_data.get("project", {}).get("dependencies", set()))


def get_requirements_deps() -> Set[str]:
    result = set()
    with open("requirements.txt", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                result.add(line)
    return result


def main():

    pyproject_deps = get_pyproject_deps()
    requirements_deps = get_requirements_deps()

    pyproject_lines = list(sorted(pyproject_deps))

    if pyproject_deps == requirements_deps:
        print("All dependencies are in sync:")
        for line in pyproject_lines:
            print(line)
        sys.exit(0)

    print("Failed, dependencies mismatch:")
    requirements_lines = list(sorted(requirements_deps))

    diff = difflib.unified_diff(
        pyproject_lines,
        requirements_lines,
        fromfile="pyproject.toml",
        tofile="requirements.txt",
        lineterm="",
    )
    for line in diff:
        print(line)

    sys.exit(1)


if __name__ == "__main__":
    main()
