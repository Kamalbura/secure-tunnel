#!/usr/bin/env python3
"""
Script to log all .py files in the codebase recursively.
Outputs to 'codebase_log.txt' with filename headings and separators.
"""

import os
import sys

def log_codebase(root_dir, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            for filename in filenames:
                if filename.endswith('.py'):
                    filepath = os.path.join(dirpath, filename)
                    rel_path = os.path.relpath(filepath, root_dir)
                    f.write(f"{rel_path}\n")
                    f.write("=" * 50 + "\n")
                    try:
                        with open(filepath, 'r', encoding='utf-8') as py_file:
                            content = py_file.read()
                            f.write(content)
                    except Exception as e:
                        f.write(f"Error reading file: {e}\n")
                    f.write("\n" + "=" * 50 + "\n\n")

if __name__ == "__main__":
    root_dir = os.getcwd()
    output_file = "codebase_log.txt"
    log_codebase(root_dir, output_file)
    print(f"Codebase logged to {output_file}")