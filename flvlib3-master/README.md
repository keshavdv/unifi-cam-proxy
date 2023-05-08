# flvlib3

*This is a replacement for the old [flvlib](https://pypi.org/project/flvlib/) library in Python3*

This is flvlib3, a library for manipulating, parsing and verifying FLV
files.  It also includes two example scripts, debug-flv and index-flv,
which demonstrate the possible applications of the library.

If you got the source tarball, you can run the automated test suite
and install the library with:

```bash
$ tar xjf flvlib3-x.x.x.tar.bz2
$ cd flvlib3-x.x.x
$ python3 setup.py test
$ sudo python3 setup.py install
```

After that you can debug FLV files with:

```bash
$ debug-flv file.flv
```

and index them with:

```bash
$ index-flv -U file.flv
```

Try:

```bash
$ debug-flv --help
$ index-flv --help
```


for more available parameters.

The library and the scripts are distributed under the MIT License.
You can contact the maintainer at zkonge(a|t)outlook.com.
