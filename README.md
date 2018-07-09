# Adjust subtitles

The subtitles of your favourite film may be a bit off:

1. They may be constantly 2 seconds behind the sound and picture, or
2. They may be 2 seconds behind at the beginning and 2 minutes behind at the end.

With some trial and error process, the first problem can be easily solved within decent media players,
such as [VLC](https://www.videolan.org/vlc/index.sl.html).
The second problem can be also solved within a decent media player,
but in this case not without tedious guessing
(or annoying from-time-to-time adjustments of the first kind). So ...

Here is a python3 script that solves both problems.

# Usage

1. Open Terminal
2. Execute one of the following commands.

## Case 1: Constant discrepancy

Your friend is `python manipulator.py <path to the file with subtitles> -off <lag in seconds>`.
For example, the call

```
python manipulator.py examples/subs.srt -off -2.5
```

created the correction `examples/subs_minus2point5s.srt` of the subtitles `examples/subs.srt`
which were `2.5` seconds behind the sound and picture, hence the negative value.
To adjust the subtitles that are `2.5` seconds too early, set the `-off` parameter to a positive value of `2.5`.

## Case 2: Non-constant discrepancy

Your friend is `python manipulator.py <path to the file with subtitles> -cor <path to the file with corrections>`.
For example, the call

```
python manipulator.py examples/subs.srt -cor examples/corrections.txt
```

created the correction `examples/subs_corrections.srt` of the subtitles `examples/subs.srt`.
The file with corrections must specify at least two pairs of the current and corrected time stamps.
In the file `examples/corrections.txt`, these pairs are:

1. Subtitle appearing at `01:06:04,245` should appear at `01:06:05,245`
2. Subtitle appearing at `1:06:10,205` should appear at `01:06:12,205`

The syntax is simple: one correction per line where the current and new time are separated by `@`.
Continuing the upper example, this results in a file with two lines:

```
01:06:04,245@01:06:05,245
01:06:10,205@01:06:12,205
```

In general, we specify can specify more than two corrections:

```
<t1 current>@<t1 corrected>
<t2 current>@<t2 corrected>
<t3 current>@<t3 corrected>
...
```

This means that every time `<t_i current>` will be mapped to `<t_i corrected>`.
For the times `t` in between the specified current times, linear interpolation is used.
If `t < t1, t2, t3 ...` or `t > t1, t2, t3 ...`, linear extrapolation is used (and you will be given a warning).

# Notes

You will need Python 3.

The script `manipulator.py` assumes the standard time format: `HH:MM:SS,mmm` for `srt` files, i.e.,
two places for hours, colon, two places for minutes, colon, two places for seconds, comma,
and three places for milliseconds.

The supported encodings for the `srt` files are the default (obtained by `locale.getpreferredencoding(False)`)
and `utf-8`. Should you need another one, either convert your `srt` file or add your encoding to the list of encodings
in the function `load_srt`.

Documentation for the functions in `manipulator.py` can be found in `docs` directory. More precisely,
it can be generated with `make html` command in Terminal, provided you have
[sphinx](http://www.sphinx-doc.org/en/master/) and its extension
[numpydoc](https://pypi.org/project/numpydoc/).
