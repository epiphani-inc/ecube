from setuptools import setup
from os import path
from io import open

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='epiphani-ecube',
    version='1.0.0',
    license='MIT',
    scripts=['e3'],
    install_requires=[
        'websocket-client>=0.57.0',
        'warrant>=0.6.1',
        'requests>=2.22.0',
        'epiphani-appsync-subscription-manager>=0.1.0',
    ],
    python_requires='>=2.7.16',
    author='Praveen Madhav',
    author_email='praveen@epiphani.io',
    url='https://github.com/epiphani-inc/ecube',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=['ecube'],
    include_package_data=True,
    description="epiphani CLI for registering connectors & executing scripts in a sandbox",
)

