#!/usr/bin/env python3 -m pytest

import pytest
import os
import sys
import requests
import hashlib
import re
import math

BLOG_POST_URL = "https://microsoft.github.io/autogen/blog/2023/04/21/LLM-tuning-math"
BLOG_POST_TITLE = "Does Model and Inference Parameter Matter in LLM Applications? - A Case Study for MATH | AutoGen"
BLOG_POST_STRING = "Large language models (LLMs) are powerful tools that can generate natural language texts for various applications, such as chatbots, summarization, translation, and more. GPT-4 is currently the state of the art LLM in the world. Is model selection irrelevant? What about inference parameters?"
BLOG_POST_FIND_ON_PAGE_QUERY = "an example where high * complex"
BLOG_POST_FIND_ON_PAGE_MATCH = "an example where high cost can easily prevent a generic complex"

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/Microsoft"
WIKIPEDIA_TITLE = "Microsoft"
WIKIPEDIA_STRING = "Redmond"

PLAIN_TEXT_URL = "https://raw.githubusercontent.com/microsoft/autogen/main/README.md"

IMAGE_URL = "https://github.com/afourney.png"
IMAGE_METADATA = "ImageSize: 180x180"

DOWNLOAD_URL = "https://arxiv.org/src/2308.08155"

PDF_URL = "https://arxiv.org/pdf/2308.08155.pdf"
PDF_STRING = "Figure 1: AutoGen enables diverse LLM-based applications using multi-agent conversations."

BING_QUERY = "Microsoft"
BING_TITLE = f"{BING_QUERY} - Search"
BING_STRING = f"A Bing search for '{BING_QUERY}' found"

try:
    from autogen.browser_utils import RequestsMarkdownBrowser, BingMarkdownSearch
except ImportError:
    skip_all = True
else:
    skip_all = False

try:
    BING_API_KEY = os.environ["BING_API_KEY"]
except KeyError:
    skip_bing = True
else:
    skip_bing = False


def _rm_folder(path):
    """Remove all the regular files in a folder, then deletes the folder. Assumes a flat file structure, with no subdirectories."""
    for fname in os.listdir(path):
        fpath = os.path.join(path, fname)
        if os.path.isfile(fpath):
            os.unlink(fpath)
    os.rmdir(path)


@pytest.mark.skipif(
    skip_all,
    reason="do not run if dependency is not installed",
)
def test_requests_markdown_browser():
    # Create a downloads folder (removing any leftover ones from prior tests)
    downloads_folder = os.path.join(os.getcwd(), "downloads")
    if os.path.isdir(downloads_folder):
        _rm_folder(downloads_folder)
    os.mkdir(downloads_folder)

    # Instantiate the browser
    viewport_size = 1024
    browser = RequestsMarkdownBrowser(
        viewport_size=viewport_size,
        downloads_folder=downloads_folder,
        search_engine=BingMarkdownSearch(bing_api_key=os.environ["BING_API_KEY"]),
    )

    # Test that we can visit a page and find what we expect there
    top_viewport = browser.visit_page(BLOG_POST_URL)
    assert browser.viewport == top_viewport
    assert browser.page_title.strip() == BLOG_POST_TITLE.strip()
    assert BLOG_POST_STRING in browser.page_content

    # Check if page splitting works
    approx_pages = math.ceil(len(browser.page_content) / viewport_size)  # May be fewer, since it aligns to word breaks
    assert len(browser.viewport_pages) <= approx_pages
    assert abs(len(browser.viewport_pages) - approx_pages) <= 1  # allow only a small deviation
    assert browser.viewport_pages[0][0] == 0
    assert browser.viewport_pages[-1][1] == len(browser.page_content)

    # Make sure we can reconstruct the full contents from the split pages
    buffer = ""
    for bounds in browser.viewport_pages:
        buffer += browser.page_content[bounds[0] : bounds[1]]
    assert buffer == browser.page_content

    # Test scrolling (scroll all the way to the bottom)
    for i in range(1, len(browser.viewport_pages)):
        browser.page_down()
        assert browser.viewport_current_page == i
    # Test scrolloing beyond the limits
    for i in range(0, 5):
        browser.page_down()
        assert browser.viewport_current_page == len(browser.viewport_pages) - 1

    # Test scrolling (scroll all the way to the bottom)
    for i in range(len(browser.viewport_pages) - 2, 0, -1):
        browser.page_up()
        assert browser.viewport_current_page == i
    # Test scrolloing beyond the limits
    for i in range(0, 5):
        browser.page_up()
        assert browser.viewport_current_page == 0

    # Test Wikipedia handling
    assert WIKIPEDIA_STRING in browser.visit_page(WIKIPEDIA_URL)
    assert WIKIPEDIA_TITLE.strip() == browser.page_title.strip()

    # Visit a plain-text file
    response = requests.get(PLAIN_TEXT_URL)
    response.raise_for_status()
    expected_results = re.sub(r"\s+", " ", response.text, re.DOTALL).strip()

    browser.visit_page(PLAIN_TEXT_URL)
    assert re.sub(r"\s+", " ", browser.page_content, re.DOTALL).strip() == expected_results

    # Visit an image causing it to display metadata
    viewport = browser.visit_page(IMAGE_URL)
    assert IMAGE_METADATA in viewport

    # Disrectly download a ZIP file and compute its md5
    response = requests.get(DOWNLOAD_URL, stream=True)
    response.raise_for_status()
    expected_md5 = hashlib.md5(response.raw.read()).hexdigest()

    # Download it with the browser and check for a match
    viewport = browser.visit_page(DOWNLOAD_URL)
    m = re.search(r"Saved file to '(.*?)'", viewport)
    download_loc = m.group(1)
    with open(download_loc, "rb") as fh:
        downloaded_md5 = hashlib.md5(fh.read()).hexdigest()

    # MD%s should match
    assert expected_md5 == downloaded_md5

    # Fetch a PDF
    viewport = browser.visit_page(PDF_URL)
    assert PDF_STRING in viewport

    # Test find in page
    browser.visit_page(BLOG_POST_URL)
    find_viewport = browser.find_on_page(BLOG_POST_FIND_ON_PAGE_QUERY)
    assert BLOG_POST_FIND_ON_PAGE_MATCH in find_viewport
    assert find_viewport is not None

    loc = browser.viewport_current_page
    find_viewport = browser.find_on_page("LLM app*")
    assert find_viewport is not None

    # Find next using the same query
    for i in range(0, 10):
        find_viewport = browser.find_on_page("LLM app*")
        assert find_viewport is not None

        new_loc = browser.viewport_current_page
        assert new_loc != loc
        loc = new_loc

    # Find next using find_next
    for i in range(0, 10):
        find_viewport = browser.find_next()
        assert find_viewport is not None

        new_loc = browser.viewport_current_page
        assert new_loc != loc
        loc = new_loc

    # Bounce around
    browser.viewport_current_page = 0
    find_viewport = browser.find_on_page("For Further Reading")
    assert find_viewport is not None
    loc = browser.viewport_current_page

    browser.page_up()
    assert browser.viewport_current_page != loc
    find_viewport = browser.find_on_page("For Further Reading")
    assert find_viewport is not None
    assert loc == browser.viewport_current_page

    # Find something that doesn't exist
    find_viewport = browser.find_on_page("7c748f9a-8dce-461f-a092-4e8d29913f2d")
    assert find_viewport is None
    assert loc == browser.viewport_current_page  # We didn't move

    # Clean up
    _rm_folder(downloads_folder)


if __name__ == "__main__":
    """Runs this file's tests from the command line."""
    test_requests_markdown_browser()
