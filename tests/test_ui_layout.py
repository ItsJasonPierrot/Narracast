import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from narracast.ui.main_window import MainWindow


def _qt_app():
    app = QApplication.instance()
    return app or QApplication([])


class MainWindowLayoutTests(unittest.TestCase):
    def test_main_window_can_shrink_to_laptop_friendly_size(self):
        _qt_app()
        window = MainWindow()

        minimum = window.minimumSizeHint()

        self.assertLessEqual(minimum.width(), 800)
        self.assertLessEqual(minimum.height(), 620)
        window.resize(800, 600)
        self.assertEqual(window.width(), 800)
        self.assertEqual(window.height(), 600)
        window.deleteLater()


if __name__ == "__main__":
    unittest.main()
