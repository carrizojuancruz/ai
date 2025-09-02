#!/usr/bin/env python3
"""Script to manage version bumps."""
import json
from pathlib import Path


def get_version_file():
    """Get the path to version.json file."""
    root_dir = Path(__file__).parent.parent.parent
    return root_dir / "version.json"


def get_version():
    """Get current version from version.json."""
    version_file = get_version_file()
    if version_file.exists():
        with open(version_file, 'r') as f:
            data = json.load(f)
            return data.get('version', '0.1.0')
    return '0.1.0'


def set_version(version):
    """Set version in version.json."""
    version_file = get_version_file()
    data = {'version': version}
    with open(version_file, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def increment_patch():
    """Increment patch version."""
    current = get_version()
    parts = current.split('.')
    if len(parts) == 3:
        major, minor, patch = parts
        new_patch = int(patch) + 1
        new_version = f"{major}.{minor}.{new_patch}"
        set_version(new_version)
        return new_version
    return current


def set_major_minor(major, minor):
    """Set major and minor version, reset patch to 0."""
    new_version = f"{major}.{minor}.0"
    set_version(new_version)
    return new_version


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Manage version")
    parser.add_argument("--patch", action="store_true", help="Increment patch version")
    parser.add_argument("--major", type=int, help="Set major version")
    parser.add_argument("--minor", type=int, help="Set minor version")
    parser.add_argument("--current", action="store_true", help="Show current version")

    args = parser.parse_args()

    if args.current:
        print(get_version())
    elif args.patch:
        new_version = increment_patch()
        print(f"Version bumped to {new_version}")
    elif args.major is not None and args.minor is not None:
        new_version = set_major_minor(args.major, args.minor)
        print(f"Version set to {new_version}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
