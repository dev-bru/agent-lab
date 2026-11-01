"""Check the offline trace viewer in installed Chrome."""

import json
import re
from pathlib import Path

import pytest
from playwright.sync_api import Error, expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "viewer" / "viewer.html"
TRACE = ROOT / "tests" / "fixtures" / "trace_two_tool.jsonl"
KINDS = ["user", "model_request", "model_reply", "tool_call", "tool_result",
         "model_request", "model_reply", "tool_call", "tool_result",
         "model_request", "model_reply", "final"]


@pytest.fixture(scope="module")
def browser():
    """Start installed Chrome once for the viewer checks."""
    playwright = sync_playwright().start()
    try:
        try:
            chrome = playwright.chromium.launch(channel="chrome", headless=True)
        except Error as error:
            raise AssertionError("Chrome not found: install Chrome or set the channel") from error
        try:
            yield chrome
        finally:
            chrome.close()
    finally:
        playwright.stop()


@pytest.fixture
def page(browser):
    """Give each check a clean browser page."""
    tab = browser.new_page()
    tab.set_default_timeout(5000)
    try:
        yield tab
    finally:
        tab.close()


def open_viewer(page):
    """Open the local HTML file."""
    page.goto(VIEWER.as_uri())


def load_trace(page, path=TRACE):
    """Choose one local trace file."""
    page.locator('#file').set_input_files(path)


def test_trace_fixture():
    """Keep the saved hand run complete and in order."""
    lines = TRACE.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 12
    records = [json.loads(line) for line in lines]
    assert all("t" in record and "kind" in record for record in records)
    assert [record["kind"] for record in records] == KINDS
    assert [record["t"] for record in records] == sorted(record["t"] for record in records)
    assert records[0]["text"] == "What is 17 times 23? Save the answer as a note called result."
    assert records[-1]["t"] > 0
    assert records[-1]["text"] == 'The answer is 391. I saved it as the note "result".'


def test_empty_page_and_empty_file(page, tmp_path):
    """Show the same clear state before loading and for an empty trace."""
    open_viewer(page)
    for empty in (False, True):
        if empty:
            path = tmp_path / "empty.jsonl"
            path.write_text("\n", encoding="utf-8", newline="\n")
            load_trace(page, path)
        expect(page.locator('#events')).to_have_count(1)
        expect(page.locator('#empty-events')).to_have_text("Open a trace file from the runs folder.")
        expect(page.locator('#detail')).to_have_text("Open a trace file from the runs folder.")
        expect(page.locator('#count')).to_have_text("0 events, 0.000 s")
        expect(page.locator('#answer')).to_have_text("No final answer")
        expect(page.locator('#position')).to_have_text("0 / 0")
        expect(page.locator('#previous')).to_be_disabled()
        expect(page.locator('#next')).to_be_disabled()


def test_load_trace(page):
    """Show all twelve events and the final answer after choosing a file."""
    open_viewer(page)
    load_trace(page)
    expect(page.locator('#events li')).to_have_count(12)
    expect(page.locator('#summary')).to_contain_text("12 events")
    expect(page.locator('#summary')).to_contain_text('The answer is 391. I saved it as the note "result".')
    expect(page.locator('#position')).to_have_text("1 / 12")


def test_keys_and_steps(page):
    """Move one event at a time and keep one current event."""
    open_viewer(page)
    load_trace(page)
    buttons = page.locator('#events li button')
    expect(page.locator('#previous')).to_be_disabled()
    buttons.first.focus()
    for key, position in (("ArrowDown", "2 / 12"), ("ArrowDown", "3 / 12"),
                          ("ArrowUp", "2 / 12")):
        page.keyboard.press(key)
        expect(page.locator('#position')).to_have_text(position)
        expect(page.locator('#events button[aria-current="true"]')).to_have_count(1)
    page.keyboard.press("ArrowRight")
    expect(page.locator('#detail')).to_contain_text('"kind": "model_reply"')
    buttons.last.click()
    expect(page.locator('#next')).to_be_disabled()
    page.locator('#previous').click()
    expect(page.locator('#position')).to_have_text("11 / 12")
    page.locator('#next').click()
    expect(page.locator('#position')).to_have_text("12 / 12")


def test_theme(page):
    """Switch theme state and page colour while keeping the button name."""
    open_viewer(page)
    before = page.locator('html').get_attribute('data-theme')
    colour = page.locator('body').evaluate('(body) => getComputedStyle(body).backgroundColor')
    page.locator('#theme').click()
    after = 'dark' if before == 'light' else 'light'
    expect(page.locator('html')).to_have_attribute('data-theme', after)
    expect(page.locator('#theme')).to_have_attribute('aria-pressed', str(after == 'dark').lower())
    expect(page.locator('#theme')).to_have_text('Dark theme')
    assert page.locator('body').evaluate('(body) => getComputedStyle(body).backgroundColor') != colour
    if after == 'dark':
        page.locator('#theme').click()
    unpressed = page.locator('#theme').evaluate('(button) => getComputedStyle(button).backgroundColor')
    page.locator('#theme').click()
    expect(page.locator('#theme')).to_have_attribute('aria-pressed', 'true')
    assert page.locator('#theme').evaluate('(button) => getComputedStyle(button).backgroundColor') != unpressed


def test_bad_lines_and_replacement(page, tmp_path):
    """Count unreadable lines and clear the warning on the next file."""
    path = tmp_path / 'bad.jsonl'
    path.write_text('\ufeff{"t":0,"kind":"user","text":"one"}\nnot json\n5\n'
                    '{"t":1,"kind":"final","text":"two"}\n', encoding='utf-8', newline='\n')
    open_viewer(page)
    load_trace(page, path)
    expect(page.locator('#events li')).to_have_count(2)
    expect(page.locator('#problems')).to_have_text('2 lines could not be read.')
    load_trace(page)
    expect(page.locator('#events li')).to_have_count(12)
    expect(page.locator('#problems')).to_be_hidden()
    expect(page.locator('#problems')).to_be_empty()
    expect(page.locator('#position')).to_have_text('1 / 12')
    page.locator('#events li button').last.click()
    with page.expect_file_chooser() as chooser:
        page.locator('#file').click()
    chooser.value.set_files(TRACE)
    expect(page.locator('#position')).to_have_text('1 / 12')


def test_model_text_is_literal(page, tmp_path):
    """Keep model text from becoming a page element or script."""
    path = tmp_path / 'literal.jsonl'
    text = '<img src=x onerror=alert(1)>'
    path.write_text(json.dumps({"t": 0, "kind": "final", "text": text}) + '\n',
                    encoding='utf-8', newline='\n')
    dialogs = []
    page.on('dialog', lambda dialog: dialogs.append(dialog.message))
    open_viewer(page)
    load_trace(page, path)
    expect(page.locator('#summary')).to_contain_text(text)
    expect(page.locator('#detail')).to_contain_text(text)
    assert page.locator('img').count() == 0
    assert dialogs == []


def test_no_network(page):
    """Use only local resources and block a direct network fetch."""
    requests = []
    failed = []
    page.on('request', lambda request: requests.append(request.url))
    page.on('requestfailed', lambda request: failed.append(request.url))
    open_viewer(page)
    load_trace(page)
    buttons = page.locator('#events li button')
    expect(buttons).to_have_count(12)
    for index in range(12):
        buttons.nth(index).click()
        expect(page.locator('#position')).to_have_text(f'{index + 1} / 12')
    assert all(url.startswith(('file:', 'data:')) for url in requests)
    assert failed == []
    assert re.search(r'(?i)https?://|//[a-z]', VIEWER.read_text(encoding='utf-8')) is None
    assert page.evaluate("fetch('http://127.0.0.1:9/').then(() => 'fetched', () => 'blocked')") == 'blocked'


def test_layout(page):
    """Stack the panes on narrow screens without page overflow."""
    open_viewer(page)
    load_trace(page)
    page.set_viewport_size({"width": 360, "height": 900})
    assert page.evaluate('document.documentElement.scrollWidth') <= 360
    page.set_viewport_size({"width": 700, "height": 900})
    events = page.locator('#events').bounding_box()
    detail = page.locator('#detail').bounding_box()
    assert events['y'] + events['height'] <= detail['y']
    page.set_viewport_size({"width": 1000, "height": 900})
    events = page.locator('#events').bounding_box()
    detail = page.locator('#detail').bounding_box()
    assert detail['x'] > events['x'] + events['width']
    assert page.locator('.detail-pane').evaluate(
        '(pane) => [getComputedStyle(pane).position, getComputedStyle(pane).top, '
        'getComputedStyle(pane).maxHeight, getComputedStyle(pane).overflowY]'
    ) == ['sticky', '16px', '868px', 'auto']
