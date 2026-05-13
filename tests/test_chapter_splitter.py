import unittest

from narracast.chapter_splitter import import_chapters, split_chapters


class ChapterSplitterTests(unittest.TestCase):
    def test_splits_common_chapter_headings(self):
        chapters = split_chapters(
            "Chapter 1\nFirst text.\n\nCHAPTER II\nSecond text."
        )

        self.assertEqual([c.title for c in chapters], ["Chapter 1", "CHAPTER II"])
        self.assertEqual([c.text for c in chapters], ["First text.", "Second text."])

    def test_splits_markdown_headings(self):
        chapters = split_chapters("# Introduction\nHello.\n\n## Chapter 2\nWorld.")

        self.assertEqual([c.title for c in chapters], ["Introduction", "Chapter 2"])

    def test_splits_scripture_like_headings(self):
        chapters = split_chapters("Genesis 1\nText one.\n\nGenesis 2\nText two.")

        self.assertEqual([c.title for c in chapters], ["Genesis 1", "Genesis 2"])

    def test_uses_custom_marker(self):
        chapters = split_chapters(
            "One\nFirst text.\n---SPLIT---\nTwo\nSecond text.",
            custom_marker="---SPLIT---",
        )

        self.assertEqual([c.title for c in chapters], ["One", "Two"])
        self.assertEqual([c.text for c in chapters], ["First text.", "Second text."])
        self.assertEqual({c.split_method for c in chapters}, {"custom_marker"})

    def test_returns_empty_when_no_headings(self):
        self.assertEqual(split_chapters("Just one plain block."), [])

    def test_import_chapters_falls_back_to_single_draft(self):
        chapters = import_chapters(
            "Just one plain block.",
            fallback_title="Whole book",
        )

        self.assertEqual(len(chapters), 1)
        self.assertEqual(chapters[0].title, "Whole book")
        self.assertEqual(chapters[0].text, "Just one plain block.")
        self.assertEqual(chapters[0].split_method, "fallback")

    def test_import_chapters_prefers_detected_chapters(self):
        chapters = import_chapters("Chapter 1\nText.", fallback_title="Whole book")

        self.assertEqual([c.title for c in chapters], ["Chapter 1"])
        self.assertEqual(chapters[0].split_method, "heading")


if __name__ == "__main__":
    unittest.main()
