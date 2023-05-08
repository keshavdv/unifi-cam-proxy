#!/usr/bin/python3
"""flvlib3
======

A library for manipulating, parsing and verifying FLV files.

It includes three example scripts, debug-flv, index-flv ,retimestamp-flv
and cut-flv which demonstrate the possible applications of the library.

Provides an easy and extensible way of writing applications that parse
and transforming FLV files. Checks file correctness based on the
official specification released by Adobe.

Can be used as a drop-in replacement for FLVTool2, from which it is
typically much faster. Unlike FLVTool2 it works on audio-only files and
does not overwrite any previous metadata the file might have.

Example usage
-------------

**Printing FLV file information**

::

    $ debug-flv file.flv | head -5
    === `file.flv' ===
    #00001 <AudioTag at offset 0x0000000D, time 0, size 162, MP3>
    #00002 <AudioTag at offset 0x000000BE, time 0, size 105, MP3>
    #00003 <VideoTag at offset 0x00000136, time 0, size 33903, VP6 (keyframe)>
    #00004 <AudioTag at offset 0x000085B4, time 26, size 105, MP3>


**Indexing and FLV file**

::

    $ index-flv -U file.flv
    $ debug-flv --metadata file.flv
    === `file.flv' ===
    #00001 <ScriptTag onMetaData at offset 0x0000000D, time 0, size 259>
    {b'duration': 9.979000000000001,
     b'keyframes': {'file_positions': [407.0], 'times': [0.0]},
     b'metadata_creator': 'flvlib3 0.x.x'}

**Retimestamping an FLV file**

::

    $ debug-flv file.flv | head -5
    === `file.flv' ===
    #00001 <AudioTag at offset 0x0000000D, time 100, size 162, MP3>
    #00002 <AudioTag at offset 0x000000BE, time 100, size 105, MP3>
    #00003 <VideoTag at offset 0x00000136, time 100, size 33903, VP6 (keyframe)>
    #00004 <AudioTag at offset 0x000085B4, time 126, size 105, MP3>

    $ retimestamp-flv -U file.flv
    $ debug-flv file.flv | head -5
    === `file.flv' ===
    #00001 <AudioTag at offset 0x0000000D, time 0, size 162, MP3>
    #00002 <AudioTag at offset 0x000000BE, time 0, size 105, MP3>
    #00003 <VideoTag at offset 0x00000136, time 0, size 33903, VP6 (keyframe)>
    #00004 <AudioTag at offset 0x000085B4, time 26, size 105, MP3>


**Cutting an FLV file**

::

    $ cut-flv file.flv -s 0 -e 1000 in.flv out.flv

"""

import sys

from setuptools import setup
from flvlib3 import __version__

# Don't install man pages and the README on a non-Linux system
if sys.platform == 'linux':
    data_files = [
        (
            'share/man/man1', [
                'man/debug-flv.1',
                'man/index-flv.1',
                'man/retimestamp-flv.1',
                'man/cut-flv.1'
            ]
        )
    ]
else:
    data_files = []

setup(
    name='flvlib3',
    version=__version__,
    description='Parsing, manipulating and indexing FLV files',
    long_description=__doc__,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Multimedia',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    platforms=['any'],
    license='MIT',
    author='Jan Urbanski',
    maintainer='zkonge',
    author_email='wulczer@wulczer.org',
    maintainer_email='zkonge@outlook.com',
    url='https://github.com/zkonge/flvlib3',
    packages=['flvlib3'],
    data_files=data_files,
    entry_points={
        'console_scripts': [
            'debug-flv=flvlib3.scripts.debug_flv:main',
            'index-flv=flvlib3.scripts.index_flv:main',
            'retimestamp-flv=flvlib3.scripts.retimestamp_flv:main',
            'cut-flv=flvlib3.scripts.cut_flv:main'
        ]
    }
)
