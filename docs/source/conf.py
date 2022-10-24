# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

from os import walk
from os.path import join, abspath
import sys

sys.path.insert(0, abspath("."))

root = abspath("../../lambda")

source_dirs = []
for (dirpath, dirnames, filenames) in walk(root):

    if not dirnames:
        continue
        # print(f'dirnames = {dirnames}')
    # for dir in dirnames:
    # 	print(join(dirpath, dir))
    source_dirs.extend([join(dirpath, dir) for dir in dirnames])

sys.path.extend(source_dirs)
for dir in sys.path:
    print(dir)


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Uploader"
copyright = "2022, Patrick M. Ryan"
author = "Patrick M. Ryan"
release = "0.1"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["sphinx.ext.autodoc"]

templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "alabaster"
html_static_path = ["_static"]
