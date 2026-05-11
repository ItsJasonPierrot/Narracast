"""Tests for narracast.text_cleanup — pure regex utilities."""

import unittest

from narracast.text_cleanup import (
    apply_all,
    clean_pdf_text,
    fix_hyphenated_line_breaks,
    fix_pdf_line_wraps,
    normalize_whitespace,
    remove_page_numbers,
    remove_repeated_pdf_headers_footers,
    strip_urls,
)


class NormalizeWhitespaceTests(unittest.TestCase):
    def test_collapses_inline_spaces(self):
        self.assertEqual(normalize_whitespace("too    many   spaces"), "too many spaces")

    def test_collapses_inline_tabs(self):
        self.assertEqual(normalize_whitespace("a\t\tb"), "a b")

    def test_strips_trailing_spaces_per_line(self):
        result = normalize_whitespace("line one   \nline two  ")
        self.assertNotIn("   ", result)
        self.assertNotIn("  ", result)

    def test_normalises_crlf_to_lf(self):
        self.assertEqual(normalize_whitespace("a\r\nb"), "a\nb")

    def test_normalises_bare_cr_to_lf(self):
        self.assertEqual(normalize_whitespace("a\rb"), "a\nb")

    def test_collapses_excess_blank_lines(self):
        result = normalize_whitespace("a\n\n\n\n\nb")
        self.assertEqual(result, "a\n\nb")

    def test_strips_leading_and_trailing_whitespace(self):
        self.assertEqual(normalize_whitespace("  hello  "), "hello")

    def test_no_op_on_clean_text(self):
        clean = "One paragraph.\n\nTwo paragraph."
        self.assertEqual(normalize_whitespace(clean), clean)


class FixHyphenatedLineBreaksTests(unittest.TestCase):
    def test_rejoins_hard_hyphen_at_line_end(self):
        self.assertEqual(fix_hyphenated_line_breaks("some-\nthing"), "something")

    def test_rejoins_soft_hyphen_at_line_end(self):
        # U+00AD soft hyphen
        self.assertEqual(fix_hyphenated_line_breaks("some­\nthing"), "something")

    def test_does_not_touch_mid_sentence_hyphens(self):
        text = "well-known phrase"
        self.assertEqual(fix_hyphenated_line_breaks(text), text)

    def test_does_not_touch_hyphen_not_at_line_end(self):
        text = "some-thing here\nnext line"
        self.assertEqual(fix_hyphenated_line_breaks(text), text)

    def test_no_op_on_clean_text(self):
        text = "First sentence.\nSecond sentence."
        self.assertEqual(fix_hyphenated_line_breaks(text), text)

    def test_multiple_hyphens_in_one_pass(self):
        text = "some-\nthing and re-\njoining"
        self.assertEqual(fix_hyphenated_line_breaks(text), "something and rejoining")


class RemovePageNumbersTests(unittest.TestCase):
    def test_removes_bare_number_line(self):
        result = remove_page_numbers("Chapter 1\n\n42\n\nSome text")
        self.assertNotIn("42", result)

    def test_removes_page_n_line(self):
        result = remove_page_numbers("Some text\n\nPage 12\n\nMore text")
        self.assertNotIn("Page 12", result)

    def test_removes_page_dot_n_line(self):
        result = remove_page_numbers("Some text\n\nPage. 7\n\nMore text")
        self.assertNotIn("Page. 7", result)

    def test_removes_dash_n_dash_line(self):
        result = remove_page_numbers("A\n\n— 5 —\n\nB")
        self.assertNotIn("— 5 —", result)

    def test_removes_endash_variant(self):
        result = remove_page_numbers("A\n\n– 5 –\n\nB")
        self.assertNotIn("5", result)

    def test_removes_n_of_m_line(self):
        result = remove_page_numbers("A\n\n12 of 345\n\nB")
        self.assertNotIn("12 of 345", result)

    def test_does_not_remove_numbers_mid_sentence(self):
        text = "There were 42 soldiers."
        self.assertIn("42", remove_page_numbers(text))

    def test_no_op_on_clean_text(self):
        text = "Chapter 1\n\nThe quick brown fox."
        self.assertEqual(remove_page_numbers(text), text)


class StripUrlsTests(unittest.TestCase):
    def test_removes_http_url(self):
        result = strip_urls("Visit http://example.com for info")
        self.assertNotIn("http://", result)

    def test_removes_https_url(self):
        result = strip_urls("See https://example.com/path?q=1 here")
        self.assertNotIn("https://", result)

    def test_removes_www_url(self):
        result = strip_urls("Go to www.example.com today")
        self.assertNotIn("www.", result)

    def test_keeps_surrounding_text(self):
        result = strip_urls("Before https://x.com after")
        self.assertIn("Before", result)
        self.assertIn("after", result)

    def test_no_op_on_clean_text(self):
        text = "No links here at all."
        self.assertEqual(strip_urls(text), text)


class ApplyAllTests(unittest.TestCase):
    def test_chains_all_steps(self):
        messy = "some-\nthing\n\n\n\n42\n\nhttps://example.com  extra   spaces"
        result = apply_all(messy)
        self.assertIn("something", result)
        self.assertNotIn("42\n", result)   # page number stripped
        self.assertNotIn("https://", result)
        self.assertNotIn("  ", result)     # double spaces collapsed

    def test_empty_string(self):
        self.assertEqual(apply_all(""), "")

    def test_already_clean_text(self):
        clean = "One paragraph.\n\nTwo paragraph."
        self.assertEqual(apply_all(clean), clean)


class PdfCleanupTests(unittest.TestCase):
    def test_removes_repeated_headers_across_pages(self):
        text = (
            "Book Title\nChapter text one.\n\f"
            "Book Title\nChapter text two.\n\f"
            "Book Title\nChapter text three."
        )

        result = remove_repeated_pdf_headers_footers(text)

        self.assertNotIn("Book Title", result)
        self.assertIn("Chapter text one.", result)
        self.assertIn("Chapter text three.", result)

    def test_does_not_remove_repeated_lines_without_page_breaks(self):
        text = "Important refrain\nImportant refrain\nImportant refrain"

        self.assertEqual(remove_repeated_pdf_headers_footers(text), text)

    def test_fix_pdf_line_wraps_joins_sentence_continuations(self):
        text = "This is a sentence that was\nwrapped by the PDF extractor.\nNext sentence."

        result = fix_pdf_line_wraps(text)

        self.assertIn("was wrapped", result)
        self.assertIn("\nNext sentence.", result)

    def test_fix_pdf_line_wraps_keeps_headings_separate(self):
        text = "Chapter 1\nThe first paragraph starts here"

        self.assertEqual(fix_pdf_line_wraps(text), text)

    def test_clean_pdf_text_combines_conservative_passes(self):
        text = (
            "Book Title\nsome-\nthing was\nwrapped here.\n12\n\f"
            "Book Title\nAnother page has\nmore text.\n13\n\f"
            "Book Title\nFinal page has\nending text.\n14"
        )

        result = clean_pdf_text(text)

        self.assertIn("something was wrapped here.", result)
        self.assertIn("Another page has more text.", result)
        self.assertIn("Final page has ending text.", result)
        self.assertNotIn("Book Title", result)
        self.assertNotIn("\n12\n", result)


if __name__ == "__main__":
    unittest.main()
