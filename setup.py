from distutils.core import setup
from Cython.Build import cythonize

setup(
  name = 'Script Scraper',
  ext_modules = cythonize("main.py"),
)