import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

import requests
import yaml

data_dir = f'{str(Path(__file__).resolve().parent)}/data'


# TODO automate this process
def prepare_base_keywords():
    base_file = f'{data_dir}/base.json'
    with open(base_file, 'r') as f:
        data = json.load(f)
    return data


def parse_tf_docs(tf_doc_url=None, prefix='tf'):
    data = {}
    session = requests.Session()
    resp = session.get(tf_doc_url)
    final_url = resp.url
    base_url = final_url.split('?')[0]
    content = resp.text
    pattern = f"({base_url}/{prefix}/[a-zA-Z0-9_./#]+)"
    matches = re.findall(pattern, content, re.DOTALL)
    for link in matches:
        keyword_i = len(base_url) + 1
        kw = link[keyword_i:]
        kw = kw.replace('/', '.')
        kw_metadata = {'url': link}
        data[kw] = kw_metadata
    return data


def load_seed_file(file_name):
    with open(file_name, 'r') as stream:
        seed = yaml.safe_load(stream)
    return seed


def parse_generated_docs(link, pattern=None):
    data = {}
    base_url = link[: link.rfind('/')]
    print(base_url)

    # Use playwright to render JavaScript content
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(link, wait_until='networkidle')
        content = page.content()
        browser.close()

    print(f'Fetching content from: {link}')

    if pattern is None:
        pattern = 'href="([a-zA-Z0-9_./#]+)"'
    matches = re.findall(pattern, content, re.DOTALL)
    for href in matches:
        # generated urls tend to have package name and '#' mark included.
        # intentionally excluded __ functions
        if '.' in href and '#' in href and '__' not in href:
            _, k = href.split('#')
            if '.' in k:  # keyword is a package name
                doc_url = f'{base_url}/{href}'
                metadata = {'url': doc_url}
                data[k] = metadata

    return data


def parse_transformers_docs(url):
    """Parse Hugging Face Transformers documentation"""
    data = {}
    base_url = 'https://huggingface.co/docs/transformers/main/en'

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until='networkidle')
        content = page.content()
        browser.close()

    # Pattern to match API sections and links
    api_pattern = r'href="(/docs/transformers/main/en/[a-zA-Z0-9_./\-#]+)"'
    matches = re.findall(api_pattern, content, re.DOTALL)

    for href in matches:
        # Clean up the href
        if '#' in href:
            path, anchor = href.split('#')
            if '.' in anchor:  # It's likely an API reference
                full_url = f'https://huggingface.co{path}#{anchor}'
                key = anchor
                metadata = {'url': full_url}
                data[key] = metadata
        else:
            # Handle full page API references
            if '/api/' in href or any(x in href.lower() for x in ['model', 'tokenizer', 'pipeline', 'configuration']):
                full_url = f'https://huggingface.co{href}'
                key = href.split('/')[-1].replace('-', '_')
                metadata = {'url': full_url}
                data[key] = metadata

    return data


if __name__ == '__main__':
    data = prepare_base_keywords()
    seed_file = f'{data_dir}/seed.yaml'
    seed = load_seed_file(seed_file)

    # Process TensorFlow docs
    for tensorflow_doc in seed['tensorflow']:
        print(f'processing: {tensorflow_doc["name"]}')
        crawled = parse_tf_docs(tensorflow_doc['url'], tensorflow_doc['prefix'])
        data.update(crawled)

    # Process generated docs
    for api_doc in seed['generated']:
        print(f'processing: {api_doc["name"]}')
        doc_url = api_doc['url']
        data.update(parse_generated_docs(doc_url))

    # Process Transformers docs
    transformers_url = 'https://huggingface.co/docs/transformers/main/en/agents'
    print('Processing: Hugging Face Transformers docs')
    transformers_data = parse_transformers_docs(transformers_url)
    data.update(transformers_data)

    doc_file = f'{data_dir}/ml.json'
    with open(doc_file, 'w') as f:
        json.dump(data, f)
