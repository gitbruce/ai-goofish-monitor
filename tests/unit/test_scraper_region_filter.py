import asyncio
import re

from src import scraper


class _FakeLocator:
    def __init__(self, count: int = 0):
        self._count = count
        self.clicked = False
        self.locator_calls = []
        self.text_calls = []
        self.role_calls = []
        self.first = self
        self.last = self

    def locator(self, selector, **kwargs):
        self.locator_calls.append((selector, kwargs))
        return _FakeLocator(0)

    def get_by_text(self, pattern):
        self.text_calls.append(pattern)
        return _FakeLocator(0)

    def get_by_role(self, role, **kwargs):
        self.role_calls.append((role, kwargs))
        return _FakeLocator(0)

    async def count(self):
        return self._count

    async def click(self):
        self.clicked = True

    async def wait_for(self, **_kwargs):
        return None

    async def scroll_into_view_if_needed(self, **_kwargs):
        return None


class _TextFallbackColumn(_FakeLocator):
    def __init__(self):
        super().__init__(0)
        self.text_option = _FakeLocator(1)

    def get_by_text(self, pattern):
        self.text_calls.append(pattern)
        return self.text_option


class _TextFallbackPopover(_FakeLocator):
    def __init__(self):
        super().__init__(0)
        self.text_button = _FakeLocator(1)

    def get_by_text(self, pattern):
        self.text_calls.append(pattern)
        return self.text_button


def test_click_region_option_falls_back_to_exact_text(monkeypatch):
    async def no_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr(scraper, "random_sleep", no_sleep)
    column = _TextFallbackColumn()

    clicked = asyncio.run(scraper._click_region_option(column, "广东", "省份"))

    assert clicked is True
    assert column.text_option.clicked is True
    assert column.text_calls
    assert isinstance(column.text_calls[0], re.Pattern)
    assert column.text_calls[0].match(" 广东 ")


def test_find_region_submit_button_falls_back_to_button_text():
    popover = _TextFallbackPopover()

    button = asyncio.run(scraper._find_region_submit_button(popover))

    assert button is popover.text_button
    assert popover.text_calls
    assert isinstance(popover.text_calls[0], re.Pattern)
    assert popover.text_calls[0].search("查看12件宝贝")
