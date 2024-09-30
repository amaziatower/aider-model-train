# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import pydata_sphinx_theme
from sphinx.application import Sphinx
from typing import Any, Dict
from pathlib import Path
import sys
# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


project = "autogen_core"
copyright = "2024, Microsoft"
author = "Microsoft"
version = "0.2"


sys.path.append(str(Path(".").resolve()))

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.graphviz",
    "sphinx_design",
    "sphinx_copybutton",
    "_extension.gallery_directive",
    "myst_nb",
]
suppress_warnings = ["myst.header"]

napoleon_custom_sections = [("Returns", "params_style")]

templates_path = ["_templates"]

autoclass_content = "init"

# TODO: incldue all notebooks excluding those requiring remote API access.
nb_execution_mode = "off"

# Guides and tutorials must succeed.
nb_execution_raise_on_error = True
nb_execution_timeout = 60

myst_heading_anchors = 5

myst_enable_extensions = [
    "colon_fence",
    "linkify",
    "strikethrough",
]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_title = "AutoGen"

html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_sidebars = {'packages/index': []}

html_theme_options = {

    "header_links_before_dropdown": 4,
    "navbar_align": "left",
    "check_switcher": False,
    # "navbar_start": ["navbar-logo", "version-switcher"],
    # "switcher": {
    #     "json_url": "/_static/switcher.json",
    # },
    "show_prev_next": False,
    ""
    "icon_links": [
        {
            "name": "Twitter",
            "url": "https://twitter.com/pyautogen",
            "icon": "fa-brands fa-twitter",
        },
        {
            "name": "GitHub",
            "url": "https://github.com/microsoft/agnext",
            "icon": "fa-brands fa-github",
        },
        {
            "name": "PyPI",
            "url": "/packages",
            "icon": "fa-custom fa-pypi",
        },
    ],
    "announcement": '🚧 AutoGen 0.4 is a <a href="#">work in progress</a>, learn more about what\'s new and different <a href="#">here</a>. To continue using the latest stable version, please visit the <a href="#">0.2 documentation</a>. 🚧',
}

html_js_files = ["custom-icon.js"]
html_sidebars = {
    "reference/index": [],
    "packages/index": [],
}

html_context = {
    'display_github': True,
    "github_user": "microsoft",
    "github_repo": "agnext",
    "github_version": "main",
    "doc_path": "python/packages/autogen-core/docs/src/",
}

autodoc_default_options = {
    "members": True,
    "undoc-members": True,
}



intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}


def setup_to_main(
    app: Sphinx, pagename: str, templatename: str, context, doctree
) -> None:
    """Add a function that jinja can access for returning an "edit this page" link pointing to `main`."""

    def to_main(link: str) -> str:
        """Transform "edit on github" links and make sure they always point to the main branch.

        Args:
            link: the link to the github edit interface

        Returns:
            the link to the tip of the main branch for the same file
        """
        links = link.split("/")
        idx = links.index("edit")
        return "/".join(links[: idx + 1]) + "/main/" + "/".join(links[idx + 2:])

    context["to_main"] = to_main


def setup(app: Sphinx) -> Dict[str, Any]:
    """Add custom configuration to sphinx app.

    Args:
        app: the Sphinx application
    Returns:
        the 2 parallel parameters set to ``True``.
    """
    app.connect("html-page-context", setup_to_main)

    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
