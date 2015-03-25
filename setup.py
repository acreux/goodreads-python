from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='pygoodreads',
      version=version,
      description="Python wrapper around goodreads.com",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='python goodreads',
      author='',
      author_email='',
      url='',
      license='',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
            "requests-oauthlib==0.4.2",
            "Paste==1.7.5.1",
            "PasteDeploy==1.5.2",
            "PasteScript==1.7.5",
            "xmltodict==0.9.2"

      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
