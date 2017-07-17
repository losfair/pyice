from setuptools import setup

setup(
    name = "pyice",
    packages = ["pyice"],
    version = "0.1.3",
    description = "Python 3 bindings for the Ice Web Framework",
    author = "Heyang Zhou",
    author_email = "i@ifxor.com",
    url = "https://github.com/losfair/pyice",
    download_url = "https://github.com/losfair/pyice/archive/master.zip",
    keywords = ["web", "http", "framework", "ice"],
    classifiers = [],
    install_requires = ["cffi"],
    python_requires = ">=3.5"
)
