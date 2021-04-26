import requests
import string
import json
import os
import re
from bs4 import BeautifulSoup
from nltk import word_tokenize
from lxml import etree
import nltk

spec_chars = string.punctuation + '•©\’\n\xa0«»\t—…' 
tokens = []
terms = etree.Element("terms")
execution_stacks = []
raw_queries = []
query_stacks = []
operation_stacks = []
results = etree.Element("results")

def remove_chars_from_text(text, chars):
    answ =  ""
    for ch in text:
        if ch not in chars:
            answ+=ch
        else:
            answ+=' '
    return answ

def append_tokens(tokens,add):
    for token in add:
        if token not in tokens:
            tokens.append(token)
    return tokens

def clear_text( raw_words, temp_file_name):
    with open('stopwords-ru.json', 'r', encoding='utf-8') as stop_words_file:
        stop_words = set(json.load(stop_words_file))
    tokens = nltk.word_tokenize(raw_words)
    tokens = [t for t in tokens if t not in stop_words]
    tokens = [t for t in tokens if all([ch.isdigit() or ch.isalpha() or ch == '-' for ch in t])]
    unstemmed_file_name = 'unstemmed/{}.txt'.format(temp_file_name)
    stemmed_file_name = 'stemmed/{}.txt'.format(temp_file_name)
    with open(unstemmed_file_name, 'w', encoding='utf-8') as unstemmed_temp_file:
        unstemmed_temp_file.write(' '.join(tokens))
    os.system('./mystem -nld {} {}'.format(unstemmed_file_name, stemmed_file_name))
    with open(stemmed_file_name, 'r', encoding='utf-8') as stemmed_temp_file:
        stemmed_string = stemmed_temp_file.read()
        stemmed_string = stemmed_string.replace('\n', ' ')
        stemmed_string = stemmed_string.replace('?', '')
    return stemmed_string

def clear_or_pass(token, index, suffix):
    if not re.match(r'[-\|()&]|\d\d-\d\d', token):
        return clear_text(token, '{}_{}'.format(index, suffix))
    else:
        return token

def rewrite_xml(element, xml_file_name):
    pretty_file = etree.tostring(element, pretty_print=True, xml_declaration=True, encoding='utf-8').decode('utf-8')
    with open(xml_file_name, 'w', encoding='utf-8') as f:
        f.write(pretty_file)

def get_tokens(page, id):
    page = page.body    
    text = page.text.lower()
    text = remove_chars_from_text(text, spec_chars)
    text = remove_chars_from_text(text, string.digits)
    text_tokens = word_tokenize(text)
    text_tokens = [t for t in text_tokens if t not in stop_words]
    unstemmed_file_name = 'page_'+str(id)+'_unstemmed_tokens.txt'
    stemmed_file_name = 'page_'+str(id)+'_stemmed_tokens.txt'
    with open(unstemmed_file_name, 'a', encoding='utf-8') as f:
        for token in text_tokens:
            f.write(token+"\n") 
    os.system('./mystem -nld {} {}'.format(unstemmed_file_name, stemmed_file_name))
    with open(stemmed_file_name, 'r', encoding='utf-8') as stemmed_temp_file:
        stemmed_string = stemmed_temp_file.read()
        stemmed_string = stemmed_string.replace('?', '')
        stemmed_tokens = stemmed_string.split('\n')
        for i in range(min([len(text_tokens),len(stemmed_tokens)])):
            text_token = text_tokens[i]
            stemmed_token = stemmed_tokens[i]
            token = text_token+" "+stemmed_token
            if token not in tokens:
                tokens.append(token)
        return stemmed_tokens
    return text_tokens
    
def get_element_sort_key(elem):
    return int(elem.get('count')) 

def create_index(pages, index):
    words = set()
    tokens_and_indexes = []
    index = 0
    for page in pages:
        index+=1
        token_list = get_tokens(page, index)
        tokens_and_indexes.append([token_list, index])
        words = words.union(set(token_list))
    words=sorted(words)
    for word in words:
        term = etree.SubElement(terms, 'term', value=word)
        for tokens_and_index in tokens_and_indexes:
            count = tokens_and_index[0].count(word)
            if count > 0:
                etree.SubElement(term, 'doc', count=str(count), id=str(tokens_and_index[1]))   
        
        term[:] = sorted(term, key=get_element_sort_key, reverse=True)    
    rewrite_xml(terms, 'terms.xml')

def find_all_doc_indexes(word):
    return set(terms.xpath("//term[@value='{}']/doc/@id".format(word)))

def not_operation( docIds):
    result = set()
    for docId in docIds:
        result = result | set(terms.xpath("//term/doc[@id!='{}']/@id".format(docId)))
    return result

def and_operation(docIdsA, docIdsB):
    return docIdsA & docIdsB

def or_operation(docIdsA, docIdsB):
    return docIdsA | docIdsB
    
def execute_query():
    result = and_operation(find_all_doc_indexes('видеть'),find_all_doc_indexes('выбирать'))
    return result


def read_queries(query_file_name):
    with open(query_file_name, 'r', encoding='utf-8') as query_to_proceed_file:
        raw = json.load(query_to_proceed_file)
    raw_queries.extend(raw)

def prepare_reverse_polish_notation():
    for raw_query, index in zip(raw_queries, range(len(raw_queries))):
        operation_stacks.insert(index, [])
        query_stacks.insert(index, [])
        raw_query = raw_query.replace(' ', '&')
        raw_query = re.sub(r'-(\D+)', r'- \1', raw_query)
        raw_query = re.sub(r'&([-|])&', r' \1 ', raw_query)
        tokens = nltk.word_tokenize(raw_query)
        for token in tokens:
            if token == '(':
                operation_stacks[index].append(token)
            elif token == ')':
                while True:
                    head = operation_stacks[index].pop()
                    if head != '(':
                        query_stacks[index].append(head)
                    else:
                        break
            elif re.match(r'[-\|&]', token):
                if len(operation_stacks[index]) == 0 or get_priority(operation_stacks[index][len(operation_stacks[index]) - 1]) < get_priority(token):
                    operation_stacks[index].append(token)
                    continue
                if get_priority(operation_stacks[index][len(operation_stacks[index]) - 1]) >= get_priority(token):
                    query_stacks[index].append(operation_stacks[index].pop())
                    operation_stacks[index].append(token)
                    continue
            else:
                query_stacks[index].append(token)
        if len(operation_stacks[index]) > 0:
            while len(operation_stacks[index]) != 0:
                query_stacks[index].append(operation_stacks[index].pop())

def execute_stack(stack, index):
    execution_stacks.insert(index, [])
    for statement in stack:
        if statement == '-':
            arg_one = execution_stacks[index].pop()
            execution_stacks[index].append(not_operation(arg_one))
        elif statement == '&':
            arg_one = execution_stacks[index].pop()
            arg_two = execution_stacks[index].pop()
            execution_stacks[index].append(and_operation(arg_one, arg_two))
        elif statement == '|':
            arg_one = execution_stacks[index].pop()
            arg_two = execution_stacks[index].pop()
            execution_stacks[index].append(or_operation(arg_one, arg_two))
        else:
            execution_stacks[index].append(find_all_doc_indexes(statement))

def binary_search_execute_queries():
    read_queries('binary_search_query_to_proceed.json')
   # print(raw_queries)
    prepare_reverse_polish_notation()
    for query_stack, index in zip(query_stacks, range(len(query_stacks))):
        execute_stack(query_stack, index)

def binary_search_generate_result():
    for result, query_index in zip([r[0] for r in execution_stacks], range(len(execution_stacks))):
        result_element = etree.SubElement(results, 'result', query=str(raw_queries[query_index]))
        for docId in result:
            page_element = etree.SubElement(result_element, 'page', id=str(docId))
        rewrite_xml(results, 'results.xml')

if __name__ == '__main__':
    rs = requests.get("https://dungeon.su/spells/")
    soup = BeautifulSoup(rs.text)
    uls = soup.findAll('ul','list-of-items')
    count = 0
    stop_words=""
    with open('stopwords-ru.json', 'r', encoding='utf-8') as stop_words_file:
        stop_words = set(json.load(stop_words_file))
    pages = []
    for ul in uls:
        if len(ul.contents)<100:
            continue
        topics = ul.contents
        for topic in topics:
            if count>=10:
                break
            if len(topic)<2:
                continue
            count+=1
            url = "https://dungeon.su"+list(topic)[2].attrs['href']
            print(url)
            rs1 = requests.get(url)
            page = BeautifulSoup(rs1.text)
            pages.append(page)
            with open('page_'+str(count)+'.html', 'w', encoding='utf-8') as f:
                f.write(str(page))
            with open('index.txt', 'a', encoding='utf-8') as f:
                f.write(str(count)+": "+url+"\n")
        break
    create_index(pages, count)
    binary_search_execute_queries()
    binary_search_generate_result()
    
    with open('all_tokens.txt', 'a', encoding='utf-8') as f:
        for token in tokens:
            f.write(token+" ")
