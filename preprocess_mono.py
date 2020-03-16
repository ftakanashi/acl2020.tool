import sys
import re
import argparse
from string import punctuation
import langid
import unicodedata

parser = argparse.ArgumentParser()
parser.add_argument('src', help='source file')
parser.add_argument('lang', help='language')
parser.add_argument('--soft_html', action='store_true', default=False, help='whether to use soft version only to remove html tag, not the sentence')
args = parser.parse_args()

f1 = args.src
lang = args.lang

min_tok = 3
max_top = 100
punc_max_num = 10

# 预处理
def norm(x_in):
  x_out = []

  for x in x_in:
    x = unicodedata.normalize('NFKC',x.strip()).replace(" ", "")
    x = re.sub('[\u200D\uFEFF\u200b\u00AD\u202C\u202D\u200C\u202A\u200E\uFDD3]', '', x.strip(), flags=re.MULTILINE)
    x_out.append(x.strip())

  print('After norm, remain %i pairs' % len(x_out))
  return x_out


def dup_remove(x_in):
  all_lines = [x.strip() for x in x_in]
  x_out = set(all_lines)  # make as set

  print('After removing duplicated sentences, remain %i pairs' % len(x_out))
  return x_out

def sentence_len_remove(x_in):

  def check_word_num(sent):
    segs = sent.strip()
    if len(segs) < min_tok or len(segs) > max_top:
      return False
    return True

  x_out = []

  for x in x_in:
    if check_word_num(x):
      x_out.append(x.strip())

  print('After removing sentences with too less or too many words, reamin %i pairs' % len(x_out))
  return x_out

def sp_punc_remove(x_in):

  def hot_fix_filter(sent):
    sent = sent.strip()
    if sent.count("/")  > 5:
      return False
    if sent.count("|") > 5:
      return False 
    if sent.count("-") > 5:
      return False
    if len(re.findall("[\d\-\|/]", sent)) / len(sent) > 0.5:
      return False
    return True

  x_out = []

  for x in x_in:
    if hot_fix_filter(x):
      x_out.append(x.strip())

  print('After removing sentences with too many specific punctuations, reamin %i pairs' % len(x_out))
  return x_out

# 去掉有特殊字符的句子
def sp_char_remove(x_in):
  x_out = []

  for x in x_in:
    if r"\x" in x or u'\xa0' in x or u'\u3000' in x or '▅' in x :
      continue
    x_out.append(x.strip())

  print('After removing sentences with special characters, remain %i pairs' % len(x_out))
  return x_out

def punc_ratio_remove(x_in):
  x_out = []

  count_func = lambda l1,l2: sum([1 for x in l1 if x in l2])

  punctuation_set = set(punctuation)
  for x in x_in:
    m_punc_x = count_func(x.strip(), set(punctuation_set))
    if m_punc_x / (len(x.strip()) + 1e-9) > 0.5 or m_punc_x > punc_max_num:
      continue
    x_out.append(x.strip()) 

  print('After removing sentences with too much punctuations, remain %i pairs' % len(x_out))
  return x_out

# 去掉太多字母 太多数字的句子
def numalp_ratio_remove(x_in):
  x_out = []

  for x in x_in:
    x = x.strip()
    if re.findall(r"\d{8}", x) or re.findall(r"[A-Za-z0-9]{15}", x) or len(re.findall(r"[A-Za-z0-9]{1}", x))/len(x) > 0.5 :
      continue
    x_out.append(x.strip())

  print('After removing sentences with much numbers or alp, remain %i pairs' % len(x_out))
  return x_out

def html_remove(x_in):
  x_out = []

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

  for x in x_in:
    if args.soft_html:
      x_out.append(soft_filter_by_html(x))
    else:
      if filter_by_html(x):
        x_out.append(x.strip())

  print('After removing sentences with html address or tags, remain %i pairs' % len(x_out))
  return x_out

#去掉1111x1111
def x_remove(x_in):
  x_out = []

  for x in x_in:
    x = x.strip()
    if re.findall(r"[0-9]{3,4}x[0-9]{3,4}", x)  :
      continue
    x_out.append(x.strip())

  print('After removing sentences with 1111x1111, remain %i pairs' % len(x_out))
  return x_out


def nonchinese_ratio_remove(x_in):
  x_out = []

  for x in x_in:
    x = x.strip()
    if len(re.findall("[\u4e00-\u9fa5]", x))/len(x) < 0.5  :
      continue
    x_out.append(x.strip())

  print('After removing sentences with less chinese character, remain %i pairs' % len(x_out))
  return x_out

def nonjapanese_ratio_remove(x_in):
  x_out = []

  for x in x_in:
    x = x.strip()
    if len(re.findall(u"[ぁ-んァ-ン一-龥]", x))/len(x) < 0.5  :
      continue
    x_out.append(x.strip())

  print('After removing sentences with less japanese character, remain %i pairs' % len(x_out))
  return x_out


#emoji
def emoji_remove(x_in):
  x_out = []
  emoj = re.compile("["
                       u"\U0001F600-\U0001F64F"  # emoticons
                       u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                       u"\U0001F680-\U0001F6FF"  # transport & map symbols
                       u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                       "]+", flags=re.UNICODE )
  
  for x in x_in:
    x = x.strip()
    if re.findall(emoj,x) :
      continue
    x_out.append(x.strip())
    
  print('After removing sentences with emoji, remain %i pairs' % len(x_out))
  return x_out

def langid_remove(x_in):
  x_out = []

  for x in x_in:
    x = x.strip()
    if langid.classify(x)[0] != lang :
      continue
    x_out.append(x.strip())

  print('After removing sentences with other language, remain %i pairs' % len(x_out))
  return x_out

filter_1 = []

fr_1 = open(f1, "r", encoding="utf8") 

f1_all_lines = fr_1.readlines()

filter_1 = norm(f1_all_lines)
filter_1 = dup_remove(filter_1)
filter_1 = sentence_len_remove(filter_1)
filter_1 = sp_punc_remove(filter_1)
filter_1 = sp_char_remove(filter_1)
filter_1 = punc_ratio_remove(filter_1)
filter_1 = numalp_ratio_remove(filter_1)
filter_1 = html_remove(filter_1)
filter_1 = x_remove(filter_1)

if lang == "zh":
  filter_1 = nonchinese_ratio_remove(filter_1)
if lang=="ja":
  filter_1 = nonjapanese_ratio_remove(filter_1)

filter_1 = emoji_remove(filter_1)
filter_1 = langid_remove(filter_1)


fr_1.close()


fw_1 = open(f1 + ".clean", "w", encoding="utf8")

print('After all filtering rules, remain %i pairs' % len(filter_1))

for x in filter_1:
  print(x, file=fw_1)

fw_1.close()
