from datetime import datetime, timedelta
import os
import argparse
import locale
import re


SRT_TIME_FORMAT = "%H:%M:%S,%f"  # hours:minutes:seconds,milliseconds
ARROW = "-->"
TIME_SEPARATOR = "@"
LINEAR = "LINEAR"
TRANSLATION = "TRANSLATION"
WEIRD_SRT = "This is not a path!"


def replace_backslash(s):
    """
    Replaces backslashes with slashes in the path.

    Parameters
    ----------
        s : str

    Returns
    -------
        str

    """
    return re.sub('\\\\', '/', s)


def linear_function(x0, y0, x1, y1, x):
    """
    Parameters
    ----------
    x0, y0, x1, y1, x : float or datetime.datetime

    Returns
    -------
    float or datetime.datetime
        Returns the value of linear function trough
        :math:`(x_0, y_0)` and  :math:`(x_1, y_1)`, in point `x`.

    Examples
    --------
    >>> linear_function(1, 2, 2, 4, 9)
    18.0

    >>> x0 = datetime(2018, 1, 1, 0, 0, 5)
    >>> y0 = datetime(2018, 1, 1, 0, 0, 6)
    >>> x1 = datetime(2018, 1, 1, 0, 1, 4)
    >>> y1 = datetime(2018, 1, 1, 0, 1, 5)
    >>> x = datetime(2018, 1, 1, 0, 2, 59)
    >>> linear_function(x0, y0, x1, y1, x)
    datetime.datetime(2018, 1, 1, 0, 3)

    """
    proportion = (x - x0) / (x1 - x0)
    return proportion * (y1 - y0) + y0


def time_to_string(t):
    """
    SRT-formatted string representation a given time.

    Parameters
    ----------
    t : datetime

    Returns
    -------
    str

    Examples
    --------
    >>> manipulator.time_to_string(datetime(2018, 1, 1, 0, 2, 59, 123))
    '00:02:59,000'

    >>> manipulator.time_to_string(datetime(2018, 1, 1, 0, 2, 59, 123456))
    '00:02:59,123'

    >>> manipulator.time_to_string(datetime(2018, 1, 1, 0, 2, 59, 12399))
    '00:02:59,012'

    >>> manipulator.time_to_string(datetime(2018, 1, 1, 0, 2, 59, 123999))
    '00:02:59,123'

    """
    return t.strftime(SRT_TIME_FORMAT)[:-3]


def load_srt(srt_file):
    """
    Loads the subtitles from a given file.

    Parameters
    ----------
    srt_file : str
        Path to the file with subtitles.

    Returns
    -------
    subs : list of list of object
        List of subtitles. Every subtitle is described as a list

        `[<number>, [<time start>, <time end>], <first line>, ..., <last line>, <empty line>]`

        of length at least four. Its elements are:
         - 1st: consecutive number of subtitle (as str)
         - 2nd: a list, containing the start and the end time
           of the subtitle, parsed to `datetime` objects
         - 3rd--(the last but one)-th: lines of the text in the subtitle (as str)
         - last: the empty string

    Examples
    --------
    >>> s = load_srt('examples/subs.srt')
    >>>

    """
    subs = []
    success = False
    encodings = [locale.getpreferredencoding(False), "utf-8"]
    enc = None
    for enc in encodings:
        try:
            subs = []
            with open(srt_file, encoding=enc) as f:
                current = []
                for line in f:
                    line_nice = line.strip()
                    current.append(line_nice)
                    if not line_nice:
                        subs.append(current)
                        current = []
                if current:
                    subs.append(current)
            success = True
            break
        except UnicodeDecodeError:
            print("WARNING: Reading subtitles with encoding", enc, "was not successful.")
    # convert to datetime objects
    if success:
        print("Subtitles", srt_file, "loaded.")
        for sub in subs:
            sub[1] = [datetime.strptime(t.strip(), SRT_TIME_FORMAT) for t in sub[1].split(ARROW)]
        return subs, enc
    else:
        print("Specify the right encoding of {}!".format(srt_file))
        exit(-1)


def load_corrections(corrections_file):
    """
    Loads the corrected values from a given file. Each line of this file
    is of the form  `<old time>@<new time>`, e.g.,
    `01:12:22,300@01:12:23,500`. In the function `update_times`,
    `old times` will be converted to `new times`, according to these values,
    e.g., the file
        
    | `00:10:00,300@00:10:01,500`   
    | `01:12:22,000@01:12:23,200`
    | `01:30:00,000@01:31:00,000`

    will result in the following transformations:
    
    - the times from the interval `00:10:00,300--01:12:22,000` are mapped
      (via linear function)
      to the interval `00:10:01,500--01:12:23,200` (which results in a `1.2`
      second offset),
    - the times from the interval `01:12:22,000--01:30:00,000` are mapped
      (via linear function) to the interval `01:12:23,200--01:31:00,000`
      (no nice interpretation).
    
    
    Parameters
    ----------
    corrections_file : str
        Path to the file with corrections.

    Returns
    -------
    corrected_times : list of list of datetime
        The elements of `corrected_times` are the pairs of the times
        specified in the `corrections_file`.

    See Also
    --------
    update_times 
    linear_function

    Examples
    --------
    >>> c = load_corrections('examples/corrections.txt')
    >>>

    """
    corrected_times = []
    with open(corrections_file) as f:
        for line in f:
            line_nice = line.strip()
            if TIME_SEPARATOR not in line_nice:
                message = "Line {} does not contain time separator {}".format(line, TIME_SEPARATOR)
                raise Exception(message)
            corrected_times.append([t.strip() for t in line.split(TIME_SEPARATOR)])
    for i, t_pair in enumerate(corrected_times):
        corrected_times[i] = [datetime.strptime(t, SRT_TIME_FORMAT) for t in t_pair]
    corrected_times.sort(key=lambda pair: pair[0])
    return corrected_times


def update_with_sentinels(subs, corrected_times, mode):
    """
    Updates the corrections of the times, so that the times span of corrections
    contains the time span of the subtitles.
        
    Parameters
    ----------
    subs : list of list of object
        As returned by `load_srt`
    corrected_times : list of list of datetime
        As returned by `load_corrections`. This list is updated.
    mode : str
        Either `LINEAR` or `TRANSLATION`. If LINEAR, `corrected_times` must
        contain at least two elements to make extrapolation possible.
    
    Returns
    -------
    None

    """
    dt = corrected_times[0][1] - corrected_times[0][0] if mode == TRANSLATION else timedelta(seconds=2)
    if subs[0][1][0] < corrected_times[0][0]:
        if mode == LINEAR:
            print("WARNING: The first subtitle start ({}) "
                  "precedes the first corrected value ({}).".format(time_to_string(subs[0][1][0]),
                                                                    time_to_string(corrected_times[0][0])))
            print("    Extrapolation will be used at the beginning.")
        else:
            sentinel_start = subs[0][1][0]
            corrected_times.insert(0, [sentinel_start, sentinel_start + dt])
    if subs[-1][1][1] > corrected_times[-1][1]:
        if mode == LINEAR:
            print("WARNING: The last subtitle ({}) "
                  "ends after the last corrected value ({}).".format(time_to_string(subs[-1][1][1]),
                                                                     time_to_string(corrected_times[-1][1])))
            fake_time = subs[-1][1][1] + dt
            t0_wrong, t0_right = corrected_times[-2]
            t1_wrong, t1_right = corrected_times[-1]
            corrected_times.append([fake_time, linear_function(t0_wrong, t0_right, t1_wrong, t1_right, fake_time)])
            print("    Extrapolation will be used at the end.")
        else:
            sentinel_end = subs[-1][1][1]
            corrected_times.append([sentinel_end, sentinel_end + dt])


def update_times(srt_file, corrected_times_file, offset):
    """
    Computes the updated times according to the specified corrections.
    The results are written to a new file that appears in the same directory
    as the file with original subtitles.

    Precisely one of the parameters `corrected_times_file` and `offset` must
    be `None`. If the latter is None, the corrections are loaded from the
    specified file `corrected_times_file`. If the former is None,
    the corrections are computed automatically.
    
    Parameters
    ----------
    srt_file : str
        Path to the file with the original subtitles
    corrected_times_file : str or None
        Path to the file with the suggested corrections of the times
    offset : float or None
        Time (in seconds) for which the subtitles should be translated.
        Positive values are used when the original subtitles appear too early.

    Returns
    -------
    srt_out_file : str
        The name of the file with modified subtitles.

    Examples
    --------
    >>> update_times('examples/subs.srt', 'examples/corrections.txt', None)
    Subtitles examples/subs.srt loaded.
    WARNING: The last subtitle (01:06:14,881) ends after the last corrected value (01:06:12,205).
        Extrapolation will be used at the end.
    Updated subtitles written to examples/subs_corrections.srt
    'examples/subs_corrections.srt'

    >>> update_times('examples/subs.srt', None, timedelta(seconds=2.5))
    Subtitles examples/subs.srt loaded.
    Updated subtitles written to examples/subs_plus2point5s.srt
    'examples/subs_plus2point5s.srt'

    """

    def find_output_name():
        dot = srt_file.rfind('.')
        orig_part = srt_file if dot < 0 else srt_file[:dot]
        appendix = "" if dot < 0 else srt_file[dot:]
        if mode == LINEAR:
            slash = corrected_times_file.rfind("/")
            dot_corrected = corrected_times_file.rfind(".")
            if dot_corrected > 0:
                corrected_name = corrected_times_file[slash + 1:dot_corrected]
            else:
                corrected_name = corrected_times_file[slash + 1:]
            new_part = "_" + corrected_name
        else:
            sign = ["plus", "minus"][offset < timedelta()]
            abs_offset = str(abs(offset).total_seconds())
            new_part = "_{}{}s".format(sign, re.sub('[.]', 'point', abs_offset))
        return orig_part + new_part + appendix

    number_none = (corrected_times_file is None) + (offset is None)
    assert number_none == 1
    subs, encoding = load_srt(srt_file)
    if corrected_times_file is None:
        mode = TRANSLATION
        now = datetime.now()
        corrected_times = [[now, now + offset]]
    else:
        mode = LINEAR
        corrected_times = load_corrections(corrected_times_file)
    if mode == LINEAR and len(corrected_times) < 2:
        print("ERROR:  Need at lest two corrected time points, but have", len(corrected_times))
        exit(-1)
    update_with_sentinels(subs, corrected_times, mode)
    # update
    srt_file_out = find_output_name()
    which_pair = 0
    with open(srt_file_out, "w", encoding=encoding) as f:
        for sub in subs:
            for i, t in enumerate(sub[1]):
                while t > corrected_times[which_pair + 1][0]:
                    which_pair += 1
                t0_wrong, t0_right = corrected_times[which_pair]
                t1_wrong, t1_right = corrected_times[which_pair + 1]
                sub[1][i] = time_to_string(linear_function(t0_wrong, t0_right, t1_wrong, t1_right, t))
            sub[1] = "{} {} {}".format(sub[1][0], ARROW, sub[1][1])
            print("\n".join(sub), file=f)
    print("Updated subtitles written to", srt_file_out)
    return srt_file_out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('srt_path', default=WEIRD_SRT,
                        help='path to the srt file with subtitles, e.g., C:\\Users\\joe\\Downloads\\myMovie\\subs.srt')
    parser.add_argument('-cor', dest='corrections_path', default=None,
                        help='path to the file with corrections, e.g., C:\\Users\\joe\\Downloads\\myMovie\\corr.txt')
    parser.add_argument('-off', dest='offset_value', default=None, type=float,
                        help='number of seconds for which the subtitles should be moved, e.g., '
                             '2.5 (if the subtitles are 2.5 seconds too early) or '
                             '-3 (if the subtitles are 3 seconds too late)')
    is_ok = True
    args = parser.parse_args()
    # subtitles file
    srt_path = args.srt_path
    if not (os.path.exists(srt_path) and os.path.isfile(srt_path)):
        print("ERROR: The specified srt file", srt_path, "does not exist.")
        is_ok = False
    srt_path = replace_backslash(srt_path)
    # corrections file
    corrections_path = args.corrections_path
    if corrections_path is not None:
        corrections_path = replace_backslash(corrections_path)
    # offset value
    offset_value = args.offset_value
    if offset_value is not None:
        offset_value = timedelta(seconds=offset_value)
    # sanity check
    nb_none = (corrections_path is None) + (offset_value is None)
    if nb_none != 1:
        print("ERROR: Precisely one of the options -cor and -off must be specified.")
        is_ok = False

    if is_ok:
        update_times(srt_path, corrections_path, offset_value)
    else:
        print("Nothing will happen ... Here is some help:\n")
        parser.print_help()
