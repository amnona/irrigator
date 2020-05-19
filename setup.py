#!/usr/bin/env python

# ----------------------------------------------------------------------------
# irrigator
# a raspberry pi based distributed irrigation system
# supporting fertilization and water counter integration
# ----------------------------------------------------------------------------

from setuptools import setup

from os.path import join, dirname

# get the requirements. pulled from flask-cors setup.py
# https://github.com/corydolphin/flask-cors/blob/master/setup.py
with open(join(dirname(__file__), 'requirements.txt'), 'r') as f:
    install_requires = f.read().split("\n")


classifiers = [
    'Development Status :: 2 - Pre-Alpha',
    'License :: OSI Approved :: MIT License',
    'Environment :: Console',
    'Topic :: Software Development :: Libraries :: Application Frameworks',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Operating System :: Unix',
    'Operating System :: POSIX']


description = 'irrigator: a distributed irrigation computer'

with open('README.md') as f:
    long_description = f.read()

keywords = 'irrigation'

setup(name='irrigator',
      version='0.9',
      license='BSD',
      description=description,
      long_description=long_description,
      keywords=keywords,
      classifiers=classifiers,
      author="amnonim",
      author_email='amnonim@gmail.com',
      maintainer="amnonim",
      url='https://github.com/amnona/irrigator',
      packages=['icomputer', 'iserver'],
      # package_data={'dbbact-server': ['log.cfg', 'dbbact.config']},
      install_requires=install_requires,
      # extras_require={'test': ["nose", "pep8", "flake8"],
      #                 'coverage': ["coveralls"],
      #                 'doc': ["Sphinx >= 1.4", "sphinx-autodoc-typehints", "nbsphinx"]}
      )
