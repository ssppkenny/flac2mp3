#!/usr/bin/env python3

import re
import os
import argparse
from collections import namedtuple
import eyed3
import tempfile

CueTrack = namedtuple("CueTrack", ("number", "title"))
CueSheet = namedtuple("CueSheet", ("performer", "title"))


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


class Flac2Mp3Converter:
    def __init__(self):
        parser = argparse.ArgumentParser(description='convert file')
        parser.add_argument(
            '--conv',
            metavar='convert',
            type=str2bool,
            help='convert to wav')
        args = parser.parse_args()
        self.__convert = args.conv
        self.__existing_files = self.__protocol_files()

    def __split_cuefile(self, cuefile):
        with open(cuefile, "r") as f:
            lines = f.readlines()
            header_lines = []
            file_lines = dict()
            file_counter = 0
            for line in lines:
                if not re.match(
                    r'^FILE\s+\"(.*)\".*',
                        line) and file_counter == 0:
                    header_lines.append(line)
                elif re.match(r'^FILE\s+\"(.*)\".*', line):
                    file_counter += 1
                    file_lines[file_counter] = []
                    file_lines[file_counter].append(line)
                else:
                    file_lines[file_counter].append(line)

            new_cue_files = []
            for k, v in file_lines.items():
                temp_name = next(tempfile._get_candidate_names())
                new_cue_file = f"{temp_name}.cue"
                new_cue_files.append(new_cue_file)
                with open(new_cue_file, "w") as f:
                    for hl in header_lines:
                        f.write(hl)
                    for bl in v:
                        f.write(bl)

            return new_cue_files

    def __detect_cuefile(self):
        # split tracks
        with os.scandir(".") as entries:
            cuefile = None
            flacfile = None
            for entry in entries:
                m = re.match(r'.+\.cue', entry.name)
                if m:
                    cuefile = entry.name

        return cuefile

    def convert(self):
        try:
            self.__cuefile = self.__detect_cuefile()
            temp_cue_file = self.__convert_cuefile()
            new_cue_files = self.__split_cuefile(temp_cue_file)
            for new_cue_file in new_cue_files:
                self.__header, self.__tracks, flacfile = self.__parse(
                    new_cue_file)
                if self.__convert:
                    self.__convert_with_wav(flacfile)
                file_counter = min([int(x) for x in self.__tracks])
                self.__split_tracks(new_cue_file, flacfile, file_counter)
                self.__rename_files()
            os.remove(temp_cue_file)
            for new_cue_file in new_cue_files:
                os.remove(new_cue_file)
        except Exception as e:
            print(e)
            self.__cleanup()

    def __protocol_files(self):
        with os.scandir(".") as entries:
            existing_files = []
            for entry in entries:
                existing_files.append(entry.name)
            return existing_files
        return []

    def __parse(self, cuefile):
        header = {}
        tracks = {}

        with open(cuefile, "r") as f:
            lines = f.readlines()
            current_track = None
            current_file = None
            for line in lines:
                m = re.match(r'^FILE\s+\"+(.+)\"+', line)
                if m:
                    current_file = m.group(1)

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
            ret_val = CueSheet(
                header['PERFORMER'], header['TITLE']), tracks, current_file
            print(ret_val)
            return ret_val

    def __split_tracks(self, temp_cue_file, flacfile, file_counter):
        cmd = f'cuebreakpoints "{temp_cue_file}" | sed s/$/0/ | shnsplit -c {file_counter} -O always -o flac "{flacfile}"'
        print(cmd)
        os.system(cmd)

    def __convert_with_wav(self, flacfile):
        convert_cmd1 = f'ffmpeg -i "{flacfile}" "{flacfile}.wav"'
        convert_cmd2 = f'ffmpeg -y -i "{flacfile}.wav" "{flacfile}"'

        os.system(convert_cmd1)
        os.system(convert_cmd2)
        os.remove(f'{flacfile}.wav')

    def __update_audiofile(self, filename, header, tracks, m):
        audiofile = eyed3.load(filename)
        audiofile.tag.artist = header.performer
        audiofile.tag.album = header.title
        audiofile.tag.album_artist = header.performer
        audiofile.tag.title = tracks[m.group(1)].title
        audiofile.tag.track_num = int(m.group(1))
        audiofile.tag.save()

    def __convert_cuefile(self):
        coding2 = "utf-8"
        coding1 = "cp1251"

        temp_name = next(tempfile._get_candidate_names())

        conv_cmd = f'iconv -f CP1251 -t UTF-8 "{self.__cuefile}" > {temp_name}.cue'
        os.system(conv_cmd)

        return f"{temp_name}.cue"

    def __cleanup(self):
        with os.scandir(".") as entries:
            for entry in entries:
                if entry.name not in self.__existing_files:
                    print(f"deleting {entry.name}")
                    os.remove(entry.name)

    def __rename_files(self):
        header, tracks = self.__header, self.__tracks
        with os.scandir('.') as entries:
            for entry in entries:
                m = re.match(r'split-track(\d+)', entry.name)
                if m:
                    dst = f"{tracks[m.group(1)].title}.flac"
                    dst_mp3 = f"{tracks[m.group(1)].title}.mp3"
                    os.rename(entry.name, dst)
                    os.system(f'ffmpeg -i "{dst}" -ab 320k "{dst_mp3}"')
                    self.__update_audiofile(dst_mp3, header, tracks, m)
                    os.remove(dst)


if __name__ == '__main__':
    converter = Flac2Mp3Converter()
    converter.convert()
