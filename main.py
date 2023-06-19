import telebot
import onnxruntime
import sentencepiece as spm
import numpy as np
import pickle
import re

import psycopg2

from navec import Navec
from slovnet import NER
from ipymarkup import show_span_ascii_markup as show_markup
from natasha import (
    Segmenter,
    MorphVocab,

    NewsEmbedding,
    NewsMorphTagger,
    NewsSyntaxParser,
    NewsNERTagger,

    PER,
    NamesExtractor,

    Doc
)
# Мой токен - 6096478845:AAEXDFeNsqKc7W3PA2p6SEvMskW196w3W34
flag = 0
#bot = telebot.TeleBot('5803770980:AAFZEfCiFoZd3BVTKlqNftNDql7zQuQbWlM')

bot = telebot.TeleBot('6096478845:AAEXDFeNsqKc7W3PA2p6SEvMskW196w3W34')
navec = Navec.load(r"models/navec_news_v1_1B_250K_300d_100q.tar")
#navec = Navec.load(r"models/navec_hudlit_v1_12B_500K_300d_100q.tar")
ner = NER.load(r"models/slovnet_ner_news_v1.tar")
ner.navec(navec)

conn = psycopg2.connect(dbname='test1', user='postgres',
                        password='3993', host='localhost')
cursor = conn.cursor()

def get_myner(message, ner):
    response = " "
    text = message.text

    cursor.execute(f"INSERT INTO public.texts (article) VALUES ('{text}')")
    conn.commit()

    cursor.execute(f"SELECT id FROM public.texts WHERE article = '{text}'")
    text_id = cursor.fetchone()[0]

    markup = ner(text)
    show_markup(markup.text, markup.spans)
    #print(markup.spans)
    for span in markup.spans:
        word = text[span.start:span.stop]
        cursor.execute(f"INSERT INTO public.span_text (span_word, id_text) VALUES ('{word}', {text_id})")
        conn.commit()
        response = response + text[span.start:span.stop] + "\n"
    bot.send_message(message.from_user.id, response)

def get_normal_myner(message):
    response = ""
    text = message.text
    segmenter = Segmenter()
    morph_vocab = MorphVocab()

    emb = NewsEmbedding()
    morph_tagger = NewsMorphTagger(emb)
    syntax_parser = NewsSyntaxParser(emb)
    ner_tagger = NewsNERTagger(emb)

    names_extractor = NamesExtractor(morph_vocab)

    doc = Doc(text)

    doc.segment(segmenter)
    doc.tag_morph(morph_tagger)
    doc.sents[0].morph.print()
    for token in doc.tokens:
        token.lemmatize(morph_vocab)

    doc.parse_syntax(syntax_parser)
    doc.sents[0].syntax.print()

    doc.tag_ner(ner_tagger)
    doc.ner.print()

    for span in doc.spans:
        span.normalize(morph_vocab)

    for span in doc.spans:
        if span.type == PER:
            span.extract_fact(names_extractor)
            response = response + "Origin text: %s, normalized: %s, first name: %s, last name: %s.\n" % (
                        span.text,
                        span.normal,
                        span.fact.as_dict['first'],
                        span.fact.as_dict['last']
            )
        else:
            response = response + "Origin text: %s.\n" % (
                span.text,
            )

    bot.send_message(message.from_user.id, response)


def find_text(message):
    word = message.text
    cursor.execute(f"SELECT DISTINCT id_text from public.span_text WHERE span_word LIKE '{word}%'")
    articles_ids = cursor.fetchall()
    articles = []
    for id in articles_ids:
        cursor.execute(f"SELECT article FROM public.texts WHERE id = {id[0]}")
        articles.append(cursor.fetchone())

    if not articles:
        bot.send_message(message.from_user.id, 'Я ничего не нашел в своей БД. Возможно вы ввели поиск не с начала фразы(')
    for article in articles:
        bot.send_message(message.from_user.id, article)


@bot.message_handler(content_types=['text'])
def get_telegram_ner(message):
    global flag
    if flag == 0:
        if message.text == "/start":
            bot.send_message(message.from_user.id,
                             "Приветствую! Данный бот предназначен для распознаванию имен людей, названий "
                             "организаций, топонимов. Для справки введи команду: /help")
        elif message.text == "/help":
            bot.send_message(message.from_user.id,
                             "Для перехода в режим генерации текста введи следующую команду: /ner\n"
                             "Для добавления текста в БД введи следующую команду: /ner_insert\n"
                             "Для поиска в БД по слову введи следующую команду: /ner_find")
        elif message.text == "/ner":
            bot.send_message(message.from_user.id, "Напиши текст, в котором нужно произвести поиск")
            flag = 1
        elif message.text == "/ner_insert":
            bot.send_message(message.from_user.id, "Напиши текст, который нужно записать в БД")
            # тут надо дописать запись в БД
            flag = 1
        elif message.text == "/ner_find":
            bot.send_message(message.from_user.id, "Напиши слово, по которому нужно произвести поиск статей")
            flag = 2
        else:
            bot.send_message(message.from_user.id, "Не понимаю, что тебе нужно. Для справки введи команду: /help")
    elif flag == 1:
        get_myner(message, ner)
        flag = 0

    elif flag == 2:
        #get_normal_myner(message)
        find_text(message)
        flag = 0


bot.polling(none_stop=True, interval=0)