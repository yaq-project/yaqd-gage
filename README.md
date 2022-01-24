# yaqd-gage

[![PyPI](https://img.shields.io/pypi/v/yaqd-gage)](https://pypi.org/project/yaqd-gage)
[![Conda](https://img.shields.io/conda/vn/conda-forge/yaqd-gage)](https://anaconda.org/conda-forge/yaqd-gage)
[![yaq](https://img.shields.io/badge/framework-yaq-orange)](https://yaq.fyi/)
[![black](https://img.shields.io/badge/code--style-black-black)](https://black.readthedocs.io/)
[![ver](https://img.shields.io/badge/calver-YYYY.M.MICRO-blue)](https://calver.org/)
[![log](https://img.shields.io/badge/change-log-informational)](https://gitlab.com/yaq/yaqd-gage/-/blob/main/CHANGELOG.md)

yaq daemons for [GaGe](http://www.gage-applied.com/) hardware

This package contains the following daemon(s):

- https://yaq.fyi/daemons/gage-chopping
- https://yaq.fyi/daemons/gage-compuscope

## driver installation

This package relies on GaGe's official Python interface, provided as part of their C SDK. A license for this SDK must be purchased from GaGe.

GaGe will provide you with a `.pyd` file: `PyGage3_64.pyd` or `PyGage3_32.pyd`. [This is essentially a Windows DLL with special Python functionality](https://docs.python.org/3/faq/windows.html#is-a-pyd-file-the-same-as-a-dll). You must put this file in your PYTHONPATH.

This open source software package is not officially supported by GaGe.

