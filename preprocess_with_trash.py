import sys
import re
import argparse
from string import punctuation
import langid
import unicodedata
from tqdm import tqdm

parser = argparse.ArgumentParser()
parser.add_argument('src', help='source file')
parser.add_argument('tgt', help='target file')
parser.add_argument('--soft_html', action='store_true', default=False,
                    help='whether to use soft version only to remove html tag, not the sentence')
args = parser.parse_args()
f1 = args.src
f2 = args.tgt

# 句子长度区间
min_tok = 3
max_top = 100

# 符号数量和比例
punc_max_num = 10


# 预处理
def norm(x_in, y_in):
    x_out = []
    y_out = []

    for (x, y) in zip(x_in, y_in):
        x = unicodedata.normalize('NFKC', x.strip()).replace(" ", "")
        y = unicodedata.normalize('NFKC', y.strip()).replace(" ", "")
        x = re.sub('[\u200D\uFEFF\u200b\u00AD\u202C\u202D\u200C\u202A\u200E\uFDD3]', '', x.strip(), flags=re.MULTILINE)
        y = re.sub('[\u200D\uFEFF\u200b\u00AD\u202C\u202D\u200C\u202A\u200E\uFDD3]', '', y.strip(), flags=re.MULTILINE)
        x_out.append(x.strip())
        y_out.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After norm, remain %i pairs' % len(x_out))
    return x_out, y_out


# 去掉重复
def dup_remove(x_in, y_in):
    tok = 'wojiushicuihongyihaha'
    all_lines = []
    for x, y in zip(x_in, y_in):
        all_lines.append(x.strip() + tok + y.strip())  # [src+tok+tgt]
    all_lines = set(all_lines)  # make as set

    x_out = []
    y_out = []
    for sent in all_lines:
        segs = sent.split(tok)
        x_out.append(segs[0])
        y_out.append(segs[1])
    assert len(x_out) == len(y_out)
    print('After removing duplicated sentences, remain %i pairs' % len(x_out))
    return x_out, y_out


# 去掉soure和target一样的句子
def src_tgt_same_remove(x_in, y_in):
    x_out = []
    y_out = []
    for (x, y) in zip(x_in, y_in):
        if x.strip() == y.strip():
            continue
        x_out.append(x.strip())
        y_out.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After removing same source and target sentence, remain %i pairs' % len(x_out))
    return x_out, y_out


# 去掉太长或者太短的句子
def sentence_len_remove(x_in, y_in):
    def check_word_num(sent):
        segs = sent.strip()
        if len(segs) < min_tok or len(segs) > max_top:
            return False
        return True

    x_out = []
    y_out = []
    x_trash, y_trash = [], []

    for (x, y) in zip(x_in, y_in):
        if check_word_num(x) and check_word_num(y):
            x_out.append(x.strip())
            y_out.append(y.strip())
        else:
            x_trash.append(x.strip())
            y_trash.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After removing sentences with too less or too many words, reamin %i pairs' % len(x_out))
    return x_out, y_out, x_trash, y_trash


# 去掉特定符号太多的句子
def sp_punc_remove(x_in, y_in):
    def hot_fix_filter(sent):
        sent = sent.strip()
        if sent.count("/") > 5:
            return False
        if sent.count("|") > 5:
            return False
        if sent.count("-") > 5:
            return False
        if len(re.findall("[\d\-\|/]", sent)) / len(sent) > 0.5:
            return False
        return True

    x_out = []
    y_out = []

    for (x, y) in zip(x_in, y_in):
        if hot_fix_filter(x) and hot_fix_filter(y):
            x_out.append(x.strip())
            y_out.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After removing sentences with too many specific punctuations, reamin %i pairs' % len(x_out))
    return x_out, y_out


# 去掉有特殊字符的句子
def sp_char_remove(x_in, y_in):
    x_out = []
    y_out = []

    for (x, y) in zip(x_in, y_in):
        if r"\x" in x or r"\x" in y \
                or u'\xa0' in x or u'\xa0' in y \
                or u'\u3000' in x or u'\u3000' in y \
                or '▅' in x or '▅' in y:
            continue
        x_out.append(x.strip())
        y_out.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After removing sentences with special characters, remain %i pairs' % len(x_out))
    return x_out, y_out


# 去掉符号不符合比例的句子
def punc_ratio_remove(x_in, y_in):
    x_out = []
    y_out = []
    x_trash, y_trash = [], []

    count_func = lambda l1, l2: sum([1 for x in l1 if x in l2])

    punctuation_set = set(punctuation)
    for (x, y) in zip(x_in, y_in):
        m_punc_x = count_func(x.strip(), set(punctuation_set))
        m_punc_y = count_func(y.strip(), set(punctuation_set))
        if m_punc_x / (len(x.strip()) + 1e-9) > 0.5 or m_punc_y / (
                len(y.strip()) + 1e-9) > 0.5 or m_punc_x > punc_max_num or m_punc_y > punc_max_num:
            x_trash.append(x.strip())
            y_trash.append(y.strip())
            continue
        x_out.append(x.strip())
        y_out.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After removing sentences with too much punctuations, remain %i pairs' % len(x_out))
    return x_out, y_out, x_trash, y_trash


# 去掉太多字母 太多数字的句子
def numalp_ratio_remove(x_in, y_in):
    x_out = []
    y_out = []
    x_trash, y_trash = [], []

    for (x, y) in zip(x_in, y_in):
        x = x.strip()
        y = y.strip()
        if re.findall(r"\d{8}", x) or re.findall(r"\d{8}", y) \
                or re.findall(r"[A-Za-z0-9]{15}", x) or re.findall(r"[A-Za-z0-9]{15}", y) \
                or len(re.findall(r"[A-Za-z0-9]{1}", x)) / len(x) > 0.5 or len(re.findall(r"[A-Za-z0-9]{1}", y)) / len(
            y) > 0.5:
            x_trash.append(x.strip())
            y_trash.append(y.strip())
            continue
        x_out.append(x.strip())
        y_out.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After removing sentences with much numbers or alp, remain %i pairs' % len(x_out))
    return x_out, y_out, x_trash, y_trash


def st_numalp_ratio_remove(x_in, y_in):
    x_out = []
    y_out = []
    x_trash, y_trash = [], []

    for (x, y) in zip(x_in, y_in):
        pm_x = len(re.findall(r"[A-Za-z0-9]", x.strip()))
        pm_y = len(re.findall(r"[A-Za-z0-9]", y.strip()))
        if pm_x / (pm_y + 1e-9) > 2 or pm_y / (pm_x + 1e-9) > 2:
            x_trash.append(x.strip())
            y_trash.append(y.strip())
            continue
        x_out.append(x.strip())
        y_out.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After removing unbalance source-target number&alp ratio, reamin %i pairs' % len(x_out))
    return x_out, y_out, x_trash, y_trash


# 去掉有网址的句子
def html_remove(x_in, y_in):
    x_out = []
    y_out = []

    def filter_by_html(sentence):
        sen = sentence.strip()
        detector = re.compile('<.*?>')
        html_tag = re.findall(detector, sen)
        if html_tag or 'https://' in sen or 'http://' in sen:
            return False
        return True

    def soft_filter_by_html(sent):
        sent = sent.strip()
        detector = re.compile('<.*?>')
        sent = re.sub(detector, '', sent)
        sent = re.sub('https?:\/\/.*[ \r\n]', '', x, flags=re.MULTILINE)
        return sent

    for (x, y) in zip(x_in, y_in):
        if args.soft_html:
            x_out.append(soft_filter_by_html(x))
            y_out.append(soft_filter_by_html(y))
        else:
            if filter_by_html(x) or filter_by_html(y):
                x_out.append(x.strip())
                y_out.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After removing sentences with html address or tags, remain %i pairs' % len(x_out))
    return x_out, y_out


# 去掉1111x1111
def x_remove(x_in, y_in):
    x_out = []
    y_out = []

    for (x, y) in zip(x_in, y_in):
        x = x.strip()
        y = y.strip()
        if re.findall(r"[0-9]{3,4}x[0-9]{3,4}", x) or re.findall(r"[0-9]{3,4}x[0-9]{3,4}", y):
            continue
        x_out.append(x.strip())
        y_out.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After removing sentences with 1111x1111, remain %i pairs' % len(x_out))
    return x_out, y_out


# 去掉中文太少的句子
def nonzhja_ratio_remove(x_in, y_in):
    x_out = []
    y_out = []
    x_trash, y_trash = [], []

    for (x, y) in zip(x_in, y_in):
        x = x.strip()
        y = y.strip()
        if len(re.findall("[\u4e00-\u9fa5]", x)) / len(x) < 0.5 or len(re.findall(u"[ぁ-んァ-ン一-龥]", y)) / len(y) < 0.5:
            x_trash.append(x.strip())
            y_trash.append(y.strip())
            continue
        x_out.append(x.strip())
        y_out.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After removing sentences with less chinese or japanese character, remain %i pairs' % len(x_out))
    return x_out, y_out, x_trash, y_trash


# emoji
def emoji_remove(x_in, y_in):
    x_out = []
    y_out = []
    x_trash, y_trash = [], []
    emoj = re.compile("["
                      u"\U0001F600-\U0001F64F"  # emoticons
                      u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                      u"\U0001F680-\U0001F6FF"  # transport & map symbols
                      u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                      "]+", flags=re.UNICODE)

    for (x, y) in zip(x_in, y_in):
        x = x.strip()
        y = y.strip()
        if re.findall(emoj, x) or re.findall(emoj, y):
            x_trash.append(x)
            y_trash.append(y)
            continue
        x_out.append(x.strip())
        y_out.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After removing sentences with emoji, remain %i pairs' % len(x_out))
    return x_out, y_out, x_trash, y_trash


# 去掉语言不对的句子
def langid_remove(x_in, y_in):
    x_out = []
    y_out = []

    for (x, y) in tqdm(zip(x_in, y_in), mininterval=1.0, ncols=50):
        x = x.strip()
        y = y.strip()
        if langid.classify(x)[0] != 'zh' or langid.classify(y)[0] != 'ja':
            continue
        x_out.append(x.strip())
        y_out.append(y.strip())

    assert len(x_out) == len(y_out)
    print('After removing sentences with other language, remain %i pairs' % len(x_out))
    return x_out, y_out


filter_1 = []
filter_2 = []
filter_out_1, filter_out_2 = [], []

fr_1 = open(f1, "r", encoding="utf8")
fr_2 = open(f2, "r", encoding="utf8")

f1_all_lines = fr_1.readlines()
f2_all_lines = fr_2.readlines()

filter_1, filter_2 = norm(f1_all_lines, f2_all_lines)
filter_1, filter_2 = dup_remove(filter_1, filter_2)
filter_1, filter_2 = src_tgt_same_remove(filter_1, filter_2)
filter_1, filter_2, x_trash, y_trash = sentence_len_remove(filter_1, filter_2)
# filter_out_1.extend(x_trash), filter_out_2.extend(y_trash)
filter_1, filter_2 = sp_punc_remove(filter_1, filter_2)
filter_1, filter_2 = sp_char_remove(filter_1, filter_2)
filter_1, filter_2, x_trash, y_trash = punc_ratio_remove(filter_1, filter_2)
filter_out_1.extend(x_trash), filter_out_2.extend(y_trash)
filter_1, filter_2, x_trash, y_trash = numalp_ratio_remove(filter_1, filter_2)
filter_out_1.extend(x_trash), filter_out_2.extend(y_trash)
filter_1, filter_2, x_trash, y_trash = st_numalp_ratio_remove(filter_1, filter_2)
filter_out_1.extend(x_trash), filter_out_2.extend(y_trash)
filter_1, filter_2 = html_remove(filter_1, filter_2)
filter_1, filter_2 = x_remove(filter_1, filter_2)
filter_1, filter_2, x_trash, y_trash = nonzhja_ratio_remove(filter_1, filter_2)
filter_out_1.extend(x_trash), filter_out_2.extend(y_trash)
filter_1, filter_2, x_trash, y_trash = emoji_remove(filter_1, filter_2)
filter_out_1.extend(x_trash), filter_out_2.extend(y_trash)
filter_1, filter_2 = langid_remove(filter_1, filter_2)

fr_1.close()
fr_2.close()

fw_1 = open(f1 + ".clean", "w", encoding="utf8")
fw_2 = open(f2 + ".clean", "w", encoding="utf8")

assert len(filter_1) == len(filter_2)
print('After all filtering rules, remain %i pairs' % len(filter_1))

for x in filter_1:
    print(x, file=fw_1)

for y in filter_2:
    print(y, file=fw_2)

fw_1.close()
fw_2.close()

fw_1 = open(f'{f1}.trash', 'w', encoding='utf-8')
fw_2 = open(f'{f2}.trash', 'w', encoding='utf-8')

assert len(filter_out_1) == len(filter_out_2)
print(f'{len(filter_out_1)} pairs are put into trash bin, waiting for recycle.')

for l1,l2 in zip(filter_out_1, filter_out_2):
    fw_1.write(l1.strip() + '\n')
    fw_2.write(l2.strip() + '\n')

fw_1.close(), fw_2.close()

# def sbcdbc(x_in, y_in):
#   x_out = []
#   y_out = []
#   dbc2sbc_dict = {
#         "０" : "0", "１" : "1", "２" : "2", "３" : "3", "４" : "4",
#         "５" : "5", "６" : "6", "７" : "7", "８" : "8", "９" : "9"}
#   sbc2dbc_dict = {
#         "0":"０", "1":"１", "2":"２", "3":"３", "4":"４",
#         "5":"５", "6":"６", "7":"７", "8":"８", "9":"９"}


#   for (x, y) in zip(x_in, y_in):  
#     x = x.strip()
#     y = y.strip()
#     for d, s in dbc2sbc_dict:
#       x = x.replace(d, s)
#     for s, d in sbc2dbc_dict:
#       y = x.replace(s, d)

#     x_out.append(x.strip())
#     y_out.append(y.strip())

#   assert len(x_out) == len(y_out)
#   print('After sbc dbc change, remain %i pairs' % len(x_out))
#   return x_out, y_out


# def sentencepiece_remove(x_in, y_in):
#   x_out = []
#   y_out = []

#   for (x, y) in zip(x_in, y_in):
#     x = x.split(' ')
#     y = y.split(' ')
#     x = ''.join(x).replace('▁', ' ')
#     y = ''.join(y).replace('▁', ' ')
#     x_out.append(x.strip())
#     y_out.append(y.strip())

#   assert len(x_out) == len(y_out)
#   print('After removing sentencepiece, remain %i pairs' % len(x_out))
#   return x_out, y_out


# # 去掉source-target句子长度比例不合适的句子
# def sentence_words_ratio_remove(x_in, y_in):
#   x_out = []
#   y_out = []

#   for (x, y) in zip(x_in, y_in):
#     m_x = len(x.strip())
#     m_y = len(y.strip())

#     if m_x / m_y > src_tgt_words_ratio or m_y / m_x > src_tgt_words_ratio:
#       continue
#     x_out.append(x.strip())
#     y_out.append(y.strip())

#   assert len(x_out) == len(y_out)
#   print('After removing sentence pair exceeds length ratio, reamin %i pairs' % len(x_out))
#   return x_out, y_out
