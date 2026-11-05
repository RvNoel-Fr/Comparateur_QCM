"""
main.py — Point d'entrée du Comparateur QCM PDF.
"""

import sys
import os

# S'assure que le répertoire courant est dans le path Python
sys.path.insert(0, os.path.dirname(__file__))

from app.gui import QCMApp


def main():
    app = QCMApp()
    app.mainloop()


if __name__ == "__main__":
    main()
