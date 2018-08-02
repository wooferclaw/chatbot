# -*- coding: utf-8 -*-
"""
Базовый класс для реализации вариантов детектора релевантности, 
использующих градиентный бустинг и разреженные матрицы шинглов.
См. реализацию класса XGB_RelevancyDetector
"""

from scipy.sparse import lil_matrix
import json
import os
import logging

from relevancy_detector import RelevancyDetector


class GB_RelevancyDetector(RelevancyDetector):
    def __init__(self):
        super(GB_RelevancyDetector, self).__init__()
        self.logger = logging.getLogger('GB_RelevancyDetector')

        # параметры генерации матрицы признаков из пар предложений должны
        # быть загружены в методе load из конфига модели, сохраненного тренером.
        self.xgb_relevancy_shingle2id = None
        self.xgb_relevancy_shingle_len = None
        self.xgb_relevancy_nb_features = None
        self.xgb_relevancy_lemmatize = None

        # для XGBoost тип элементов входной матрицы может быть bool,
        # для LightGBM должен быть 'float32'
        self.x_matrix_type = '<<unknown>>'

    def predict_by_model(self, X_data):
        """
        Метод должен быть переопределен в классе-потомке и реализовывать вызом расчета релевантностей
        для матрицы X_Data, содержащей фичи для пар вопрос-предпосылка.
        """
        raise NotImplemented()


    def init_model_params(self, model_config):
        self.xgb_relevancy_shingle2id = model_config['shingle2id']
        self.xgb_relevancy_shingle_len = model_config['shingle_len']
        self.xgb_relevancy_nb_features = model_config['nb_features']
        self.xgb_relevancy_lemmatize = model_config['lemmatize']

    def get_most_relevant(self, probe_phrase, phrases, text_utils, word_embeddings, nb_results=1):
        """
        Поиск наиболее релевантной предпосыл(ки|ок) с помощью одной из моделей,
        использующей градиентный бустинг (XGBoost, LightGBM).

        :param probe_phrase - юникодная строка-вопрос
        :param phrases - список проверяемых предпосылок из базы знаний
        :param text_utils - экземпляр класса TextUtils с кодом для токенизации, лемматизации etc
        :param word_embeddings - экземпляр класса WordEmbeddings для доступа к моделям встраивания слов
        :param nb_results - кол-во возвращаемых результатов, по умолчанию возвращается одна
         наиболее релевантная запись

        :return если nb_results=1, то вернется кортеж с двумя полями ('текст лучшей предпосылки', оценка_релевантности),
        в противном случае возвращается кортеж с двумя полями - список предпосылок, отсортированный по убыванию
        релевантности и список соответствующих релевантностей.
        """

        nb_answers = len(phrases)
        X_data = lil_matrix((nb_answers, self.xgb_relevancy_nb_features), dtype=self.x_matrix_type)

        # все предпосылки из текущей базы фактов векторизуем в один тензор, чтобы
        # прогнать его через классификатор разом.
        best_premise = ''
        best_sim = 0.0
        for ipremise, (premise, premise_person, phrase_code) in enumerate(phrases):
            if self.xgb_relevancy_lemmatize:
                premise_words = text_utils.tokenize(premise)
                question_words = text_utils.tokenize(probe_phrase)
            else:
                premise_words = text_utils.lemmatize(premise)
                question_words = text_utils.lemmatize(probe_phrase)

            premise_wx = text_utils.words2str(premise_words)
            question_wx = text_utils.words2str(question_words)

            premise_shingles = set(text_utils.ngrams(premise_wx, self.xgb_relevancy_shingle_len))
            question_shingles = set(text_utils.ngrams(question_wx, self.xgb_relevancy_shingle_len))

            self.xgb_relevancy_vectorize_sample_x(X_data, ipremise, premise_shingles, question_shingles,
                                                  self.xgb_relevancy_shingle2id)

        y_probe = self.predict_by_model(X_data)

        reslist = []
        for ipremise, (premise, premise_person, phrase_code) in enumerate(phrases):
            sim = y_probe[ipremise]
            reslist.append((premise, sim))

        # сортируем результаты в порядке убывания релевантности.
        reslist = sorted(reslist, key=lambda z: -z[1])

        if nb_results == 1:
            # возвращаем единственную запись с максимальной релевантностью.
            best_premise = reslist[0][0]
            best_rel = reslist[0][1]
            return best_premise, best_rel
        else:
            # возвращаем заданное кол-во наиболее релевантных записей.
            n = min(nb_results, nb_answers)
            best_premises = [reslist[i][0] for i in range(n)]
            best_rels = [reslist[i][1] for i in range(n)]
            return best_premises, best_rels

    def unknown_shingle(self, shingle):
        #self.logger.error(u'Shingle "{}" is unknown'.format(shingle))
        pass

    def xgb_relevancy_vectorize_sample_x(self, X_data, idata,
                                         premise_shingles, question_shingles,
                                         shingle2id):
        # для внутреннего использования - векторизация предпосылки и вопроса.
        ps = set(premise_shingles)
        qs = set(question_shingles)
        common_shingles = ps & qs
        notmatched_ps = ps - qs
        notmatched_qs = qs - ps

        nb_shingles = len(shingle2id)

        icol = 0
        for shingle in common_shingles:
            if shingle not in shingle2id:
                self.unknown_shingle(shingle)
            else:
                X_data[idata, icol + shingle2id[shingle]] = True

        icol += nb_shingles
        for shingle in notmatched_ps:
            if shingle not in shingle2id:
                self.unknown_shingle(shingle)
            else:
                X_data[idata, icol + shingle2id[shingle]] = True

        icol += nb_shingles
        for shingle in notmatched_qs:
            if shingle not in shingle2id:
                self.unknown_shingle(shingle)
            else:
                X_data[idata, icol + shingle2id[shingle]] = True