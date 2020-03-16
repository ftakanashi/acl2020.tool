#!/usr/bin/env python
# -*- coding:utf-8 -*-

import argparse
import sys
import string

HALF_MIN = 0x0020
HALF_MAX = 0x7e
FULL_MIN = HALF_MIN + 0xfee0
FULL_MAX = HALF_MAX + 0xfee0

PERIODS = ['。']


def is_full(char):
    code = ord(char)
    return code > FULL_MIN and code <= FULL_MAX


def is_half(char):
    code = ord(char)
    return code > HALF_MIN and code <= HALF_MAX


def check_char(char, char_set):
    if is_full(char):
        dummy = chr(ord(char) - 0xfee0)
    elif is_half(char):
        dummy = char
    else:
        return False
    return dummy in char_set


def process(opt, lines):
    for line in lines:
        if line.strip() == '' or line.strip() == 'X':
            print(line)
            continue

        chars = [c for c in list(line) if c.strip()]
        if opt.input_mode == 'ref':
            pass
            # if opt.remove_period and chars[-1] in PERIODS:
            #     chars = chars[:-1]
            # print(' '.join(chars))

        elif opt.input_mode == 'ja':
            for i, ch in enumerate(chars):
                if ch == 'X':
                    if (i == 0 and not check_char(chars[1], string.ascii_letters)) or (
                                    i > 0 and not check_char(chars[i - 1], string.ascii_letters)):
                        continue
                if is_half(ch):
                    full_ch = chr(ord(ch) + 0xfee0)
                    chars[i] = full_ch

        elif opt.input_mode == 'zh':
            for i, ch in enumerate(chars):
                if ch == 'X':
                    if (i == 0 and not check_char(chars[1], string.ascii_letters)) or (
                                    i > 0 and not check_char(chars[i - 1], string.ascii_letters)):
                        continue
                if is_half(ch) and check_char(ch, string.punctuation):
                    full_ch = chr(ord(ch) + 0xfee0)
                    chars[i] = full_ch

        else:
            raise Exception('Invalid input mode {}'.format(opt.input_mode))

        if opt.remove_period:
            if chars[-1] in PERIODS:
                chars = chars[:-1]
            if chars[0] in PERIODS:
                chars = chars[1:]

        print(' '.join(chars))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-mode', required=True,
                        help='Specify the type of the input file.')

    parser.add_argument('--remove-period', default=False, action='store_true',
                        help='Remove all periods in file if specified.')

    opt = parser.parse_args()
    lines = sys.stdin.read().split('\n')

    process(opt, lines)


if __name__ == '__main__':
    main()
