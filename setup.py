# Copyright (c) 2020 Ian C. Good
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

from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

with open('LICENSE.md') as f:
    license = f.read()

setup(name='pymap',
      version='0.24.5',
      author='Ian Good',
      author_email='ian@icgood.net',
      description='Lightweight, asynchronous IMAP serving in Python.',
      long_description=readme + license,
      long_description_content_type='text/markdown',
      license='MIT',
      url='https://github.com/icgood/pymap/',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Topic :: Communications :: Email :: Post-Office',
          'Topic :: Communications :: Email :: Post-Office :: IMAP',
          'Intended Audience :: Developers',
          'Intended Audience :: Information Technology',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3.9'],
      python_requires='~=3.9',
      include_package_data=True,
      packages=find_packages(),
      install_requires=[
          'pysasl ~= 0.8.0',
          'proxy-protocol ~= 0.6.0'],
      extras_require={
          'admin': ['pymap-admin ~= 0.7.0', 'googleapis-common-protos'],
          'macaroon': ['pymacaroons'],
          'redis': ['aioredis ~= 1.3.1', 'msgpack ~= 1.0'],
          'sieve': ['sievelib'],
          'swim': ['swim-protocol ~= 0.3.6'],
          'systemd': ['systemd-python'],
          'optional': ['hiredis', 'passlib', 'pid']},
      entry_points={
          'console_scripts': [
              'pymap = pymap.main:main'],
          'pymap.backend': [
              'dict = pymap.backend.dict:DictBackend',
              'maildir = pymap.backend.maildir:MaildirBackend',
              'redis = pymap.backend.redis:RedisBackend [redis]'],
          'pymap.service': [
              'imap = pymap.imap:IMAPService',
              'admin = pymap.admin:AdminService [admin]',
              'managesieve = pymap.sieve.manage:ManageSieveService [sieve]',
              'swim = pymap.cluster.swim:SwimService [swim]'],
          'pymap.filter': [
              'sieve = pymap.sieve:SieveCompiler [sieve]'],
          'pymap.token': [
              'macaroon = pymap.token.macaroon:MacaroonTokens [macaroon]'],
          'pymap.admin.handlers': [
              'server = pymap.admin.handlers.system:SystemHandlers',
              'mailbox = pymap.admin.handlers.mailbox:MailboxHandlers',
              'user = pymap.admin.handlers.user:UserHandlers']})
