#!/usr/local/bin/python3

import re
import os
import subprocess
import argparse
from collections import namedtuple
import eyed3
import tempfile


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


parser = argparse.ArgumentParser(description='convert file')

parser.add_argument(
    '--conv',
    metavar='convert',
    type=str2bool,
    help='convert to wav')

args = parser.parse_args()
print(args)


CueTrack = namedtuple("CueTrack", ("number", "title"))
CueSheet = namedtuple("CueSheet", ("performer", "title"))


def protocol_files():
    with os.scandir(".") as entries:
        existing_files = []
        for entry in entries:
            existing_files.append(entry.name)
        return existing_files
    return []


def parse(cuefile):
    header = dict()
    tracks = dict()

    with open(cuefile, "r") as f:
        lines = f.readlines()
        current_track = None
        for line in lines:
            m = re.match(r'^TITLE\s+\"+(.+)\"+', line)
            if m:
                header["TITLE"] = m.group(1)
            m = re.match(r'^PERFORMER\s+\"+(.+)\"+', line)
            if m:
                header["PERFORMER"] = m.group(1)

            m = re.match(r'^\s+TRACK\s+(\d+)\s+.*', line)
            if m:
                current_track = m.group(1)

            m = re.match(r'^\s+TITLE\s+\"+(.+)\"+', line)
            if m and current_track:
                track = CueTrack(current_track, m.group(1))
                tracks[current_track] = track
                current_track = None

    os.remove(cuefile)
    return CueSheet(header['PERFORMER'], header['TITLE']), tracks


def split_tracks(cuefile, flacfile):
    cmd = f'cuebreakpoints "{cuefile}" | sed s/$/0/ | shnsplit -O always -o flac "{flacfile}"'
    os.system(cmd)


def detect_files():
    # split tracks
    with os.scandir(".") as entries:
        cuefile = None
        flacfile = None
        for entry in entries:
            m = re.match(r'.+\.cue', entry.name)
            if m:
                cuefile = entry.name
            m = re.match(r'.+\.flac', entry.name)
            if m:
                flacfile = entry.name

    return cuefile, flacfile


def convert_with_wav(flacfile):
    if args.conv:
        convert_cmd1 = f'ffmpeg -i "{flacfile}" "{flacfile}.wav"'
        convert_cmd2 = f'ffmpeg -y -i "{flacfile}.wav" "{flacfile}"'

        os.system(convert_cmd1)
        os.system(convert_cmd2)
        os.remove(f'{flacfile}.wav')

def update_audiofile(filename, header, tracks, m):
    audiofile = eyed3.load(filename)
    audiofile.tag.artist = header.performer
    audiofile.tag.album = header.title
    audiofile.tag.album_artist = header.performer
    audiofile.tag.title = tracks[m.group(1)].title
    audiofile.tag.track_num = int(m.group(1))
    audiofile.tag.save()



def convert_cuefile():
    coding2 = "utf-8"
    coding1 = "cp1251"

    temp_name = next(tempfile._get_candidate_names())

    conv_cmd = f'iconv -f CP1251 -t UTF-8 "{cuefile}" > {temp_name}'
    os.system(conv_cmd)
    return temp_name


def cleanup(existing_files):
    with os.scandir(".") as entries:
        for entry in entries:
            if entry.name not in existing_files:
                print(f"deleting {entry.name}")
                os.remove(entry.name)


def rename_files():
    with os.scandir('.') as entries:
        for entry in entries:
            m = re.match(r'split-track(\d+)', entry.name)
            if m:
                dst = f"{tracks[m.group(1)].title}.flac"
                dst_mp3 = f"{tracks[m.group(1)].title}.mp3"
                os.rename(entry.name, dst)
                os.system(f'ffmpeg -i "{dst}" -ab 320k "{dst_mp3}"')

                update_audiofile(dst_mp3, header, tracks, m)

                os.remove(dst)


existing_files = protocol_files()

try:
    cuefile, flacfile = detect_files()
    convert_with_wav(flacfile)
    split_tracks(cuefile, flacfile)
    temp_cue_file = convert_cuefile()
    header, tracks = parse(temp_cue_file)
    rename_files()
except:
    cleanup(existing_files)
