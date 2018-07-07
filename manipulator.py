from datetime import datetime, timedelta
import os
import argparse
import locale


ARROW = "-->"
TIME_SEPARATOR = "@"
SRT_TIME_FORMAT = "%H:%M:%S,%f"  # hours:minutes:seconds,milliseconds
LINEAR = "LINEAR"
TRANSLATION = "TRANSLATION"
WEIRD_SRT = "This is not a path!"


def linear_function(x0, y0, x1, y1, x):
    proportion = (x - x0) / (x1 - x0)
    return proportion * (y1 - y0) + y0


def load_srt(srt_file):
    """
    contains lists like ['1', '00:00:04,846 --> 00:00:05,544', 'Hello, there.', 'Hello.']
    :param srt_file:
    :return:
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
    # sentinels: time span of corrections must contain the t. s. of subtitles
    dt = corrected_times[0][1] - corrected_times[0][0] if mode == TRANSLATION else timedelta(seconds=2)
    if subs[0][1][0] < corrected_times[0][0]:
        if mode == LINEAR:
            print("WARNING: The first subtitle start ({}) "
                  "precedes the first corrected value ({}).".format(subs[0][1][0].strftime(SRT_TIME_FORMAT),
                                                                    corrected_times[0][0].strftime(SRT_TIME_FORMAT)))
            print("    Extrapolation will be used at the beginning.")
        else:
            sentinel_start = subs[0][1][0]
            corrected_times.insert(0, [sentinel_start, sentinel_start + dt])
    if subs[-1][1][1] > corrected_times[-1][1]:
        if mode == LINEAR:
            print("WARNING: The last subtitle ({}) "
                  "ends after the last corrected value ({}).".format(subs[-1][1][1].strftime(SRT_TIME_FORMAT),
                                                                     corrected_times[-1][1].strftime(SRT_TIME_FORMAT)))
            fake_time = subs[-1][1][1] + dt
            t0_wrong, t0_right = corrected_times[-2]
            t1_wrong, t1_right = corrected_times[-1]
            corrected_times.append([fake_time, linear_function(t0_wrong, t0_right, t1_wrong, t1_right, fake_time)])
            print("    Extrapolation will be used at the end.")
        else:
            sentinel_end = subs[-1][1][1]
            corrected_times.append([sentinel_end, sentinel_end + dt])


def update_times(srt_file, corrected_times_file, offset):
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
    # out file name
    dot = srt_file.rfind('.')
    if dot < 0:
        srt_file_out = srt_file + "_new.srt"
    else:
        srt_file_out = srt_file[:dot] + "_new" + srt_file[dot:]
    # update
    which_pair = 0
    with open(srt_file_out, "w", encoding=encoding) as f:
        for sub in subs:
            for i, t in enumerate(sub[1]):
                while t > corrected_times[which_pair + 1][0]:
                    which_pair += 1
                t0_wrong, t0_right = corrected_times[which_pair]
                t1_wrong, t1_right = corrected_times[which_pair + 1]
                sub[1][i] = linear_function(t0_wrong, t0_right, t1_wrong, t1_right, t).strftime(SRT_TIME_FORMAT)
            sub[1] = "{} {} {}".format(sub[1][0], ARROW, sub[1][1])
            print("\n".join(sub), file=f)
    print("Updated subtitles written to", srt_file_out)


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
    srt_path = args.srt_path
    if not (os.path.exists(srt_path) and os.path.isfile(srt_path)):
        print("ERROR: The specified srt file", srt_path, "does not exist.")
        is_ok = False
    corrections_path = args.corrections_path
    offset_value = args.offset_value
    nb_none = (corrections_path is None) + (offset_value is None)
    if nb_none != 1:
        print("ERROR: Precisely one of the options -cor and -off must be specified.")
        is_ok = False
    if offset_value is not None:
        offset_value = timedelta(seconds=offset_value)

    if is_ok:
        update_times(srt_path, corrections_path, offset_value)
    else:
        print("Nothing will happen ... Here is some help:\n")
        parser.print_help()
