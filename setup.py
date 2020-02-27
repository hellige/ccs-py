import os

from setuptools import find_packages, setup

# TODO random links...
# https://docs.pytest.org/en/latest/goodpractices.html?highlight=src#tests-outside-application-code
# https://blog.ionelmc.ro/2014/05/25/python-packaging/#the-structure
# https://realpython.com/pypi-publish-python-package/
# https://github.com/navdeep-G/samplemod/blob/master/setup.py
# https://github.com/navdeep-G/setup.py/blob/master/setup.py
# https://packaging.python.org/guides/distributing-packages-using-setuptools/
# https://github.com/tobgu/pyrsistent
# https://github.com/tobgu/pyrsistent/blob/master/requirements.txt
# https://setuptools.readthedocs.io/en/latest/setuptools.html

# TODO also look at pytest for package layout, they have a nice almost-everything-private code layout

# TODO set up codecov


VERSION = "0.1.0"
PYTHON_REQUIRES = "~=3.6"


def read(*names, **kwargs):
    with open(
        os.path.join(os.path.dirname(__file__), *names),
        encoding=kwargs.get("encoding", "utf8"),
    ) as fh:
        return fh.read()


setup(
    name="ccs-py",
    use_scm_version={"write_to": "src/ccs/_version.py"},
    description="CCS language for config files",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    author="Matt Hellige",
    author_email="matt@immute.net",
    url="https://github.com/hellige/ccs-py",
    python_requires=PYTHON_REQUIRES,
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    keywords="ccs config configuration",
    install_requires=["pyrsistent"],
    packages=find_packages("src"),
    package_dir={"": "src"},
    setup_requires=["setuptools-scm",],
    entry_points={"console_scripts": ["ccs = ccs.cli:main",]},
)
