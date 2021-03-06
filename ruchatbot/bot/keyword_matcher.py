# -*- coding: utf-8 -*-
"""
Классы для реализации актора keyword в правилах.
"""

class KeywordMatcherLemma(object):
    def __init__(self, lemma):
        self.lemma = lemma

    def match(self, input_phrase):
        for input_token in input_phrase.tags:
            if input_token[2] == self.lemma:
                return True

        for input_token in input_phrase.raw_tokens:
            if input_token == self.lemma:
                return True

        return False


class KeywordMatcherLemmaList(object):
    @staticmethod
    def from_string(s):
        items = [KeywordMatcherLemma(lemma.strip()) for lemma in s.split('|')]
        return KeywordMatcherLemmaList(items)

    def __init__(self, items):
        self.items = items

    def match(self, phrase):
        for matcher in self.items:
            if matcher.match(phrase):
                return True
        return False


class KeywordMatcher(object):
    def __init__(self, items):
        self.items = items

    @staticmethod
    def from_string(s):
        # Пока самая примитивная реализация, потом надо будет
        # учесть более сложные конструкции с OR/AND и регулярками...
        items = [KeywordMatcherLemmaList.from_string(z.strip()) for z in s.split(',')]
        return KeywordMatcher(items)

    def match(self, input_phrase):
        for item in self.items:
            if not item.match(input_phrase):
                return False

        return True
