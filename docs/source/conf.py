# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import os
import sys

sys.path.insert(0, os.path.abspath("."))
# sys.path.insert(0, '/Users/pmryan/ec/projects/galactica/sphinx_basics')

root = os.path.abspath("../../lambda")
modules = [
    "delete_object",
    "api_rejected",
    "new_object_received",
    "call_api",
    "api_succeeded",
    "handle_retries",
    "test_api",
]

sys.path.extend([os.path.join(root, dir) for dir in modules])
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
