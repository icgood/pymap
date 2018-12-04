# Copyright (c) 2018 Ian C. Good
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

from setuptools import setup, find_packages  # type: ignore


with open('README.md', 'r') as fh:
    long_description = fh.read()


setup(name='pymap',
      version='0.5.2',
      author='Ian Good',
      author_email='icgood@gmail.com',
      description='Lightweight, asynchronous IMAP serving in Python.',
      long_description=long_description,
      long_description_content_type='text/markdown',
      license='MIT',
      url='https://github.com/icgood/pymap/',
      packages=find_packages(),
      install_requires=['pysasl', 'typing-extensions'],
      tests_require=['pytest', 'pytest-asyncio'],
      entry_points={'console_scripts': ['pymap = pymap.main:main'],
                    'pymap.backend': [
                        'dict = pymap.backend.dict:DictBackend',
                        'maildir = pymap.backend.maildir:MaildirBackend']},
      package_data={'pymap.backend.dict': ['demo/']},
      classifiers=['Development Status :: 3 - Alpha',
                   'Topic :: Communications :: Email :: Post-Office',
                   'Topic :: Communications :: Email :: Post-Office :: IMAP',
                   'Intended Audience :: Developers',
                   'Intended Audience :: Information Technology',
                   'License :: OSI Approved :: MIT License',
                   'Programming Language :: Python',
                   'Programming Language :: Python :: 3.7'])
