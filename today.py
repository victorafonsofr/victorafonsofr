"""
Atualiza dark_mode.svg e light_mode.svg com as estatísticas do GitHub.

Baseado na ideia do repositório Andrew6rant/Andrew6rant (reescrito e adaptado).

Variáveis de ambiente:
  ACCESS_TOKEN  token (fine-grained) com acesso de leitura aos repositórios
  USER_NAME     usuário do GitHub (ex.: victorafonsofr)
"""
import datetime
import hashlib
import os
import time

import requests
from dateutil import relativedelta
from lxml import etree

HEADERS = {'Authorization': 'Bearer ' + os.environ['ACCESS_TOKEN']}
USER_NAME = os.environ['USER_NAME']
AFFILIATIONS = ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER']
CACHE_DIR = 'cache'
COMMENT_SIZE = 7  # linhas de comentário no topo do arquivo de cache
SVG_FILES = ['dark_mode.svg', 'light_mode.svg']
QUERY_COUNT = {}


# --------------------------------------------------------------------------- API
def graphql(name, query, variables):
    QUERY_COUNT[name] = QUERY_COUNT.get(name, 0) + 1
    r = requests.post('https://api.github.com/graphql',
                      json={'query': query, 'variables': variables},
                      headers=HEADERS, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f'{name} falhou: {r.status_code} {r.text}')
    body = r.json()
    if 'errors' in body:
        raise RuntimeError(f'{name} retornou erros: {body["errors"]}')
    return body['data']


def user_id(login):
    data = graphql('user_id', 'query($login: String!){ user(login: $login){ id } }',
                   {'login': login})
    return data['user']['id']


def follower_count(login):
    data = graphql('followers',
                   'query($login: String!){ user(login: $login){ followers{ totalCount } } }',
                   {'login': login})
    return data['user']['followers']['totalCount']


def repo_stats(affiliations):
    """Retorna (qtde de repositórios, total de stars) para as afiliações dadas."""
    query = '''
    query($aff: [RepositoryAffiliation], $login: String!, $cursor: String) {
      user(login: $login) {
        repositories(first: 100, after: $cursor, ownerAffiliations: $aff) {
          totalCount
          nodes { stargazers { totalCount } }
          pageInfo { endCursor hasNextPage }
        }
      }
    }'''
    cursor, stars, total = None, 0, 0
    while True:
        repos = graphql('repo_stats', query,
                        {'aff': affiliations, 'login': USER_NAME, 'cursor': cursor})['user']['repositories']
        total = repos['totalCount']
        stars += sum(n['stargazers']['totalCount'] for n in repos['nodes'])
        if not repos['pageInfo']['hasNextPage']:
            return total, stars
        cursor = repos['pageInfo']['endCursor']


def list_repos(affiliations):
    """Lista nameWithOwner + total de commits da branch padrão de cada repositório."""
    query = '''
    query($aff: [RepositoryAffiliation], $login: String!, $cursor: String) {
      user(login: $login) {
        repositories(first: 60, after: $cursor, ownerAffiliations: $aff) {
          nodes {
            nameWithOwner
            defaultBranchRef { target { ... on Commit { history { totalCount } } } }
          }
          pageInfo { endCursor hasNextPage }
        }
      }
    }'''
    cursor, nodes = None, []
    while True:
        repos = graphql('list_repos', query,
                        {'aff': affiliations, 'login': USER_NAME, 'cursor': cursor})['user']['repositories']
        nodes += repos['nodes']
        if not repos['pageInfo']['hasNextPage']:
            return nodes
        cursor = repos['pageInfo']['endCursor']


def my_loc_in_repo(owner, name, my_id):
    """Percorre o histórico (100 commits por vez) somando só os commits feitos por mim."""
    query = '''
    query($name: String!, $owner: String!, $cursor: String) {
      repository(name: $name, owner: $owner) {
        defaultBranchRef { target { ... on Commit {
          history(first: 100, after: $cursor) {
            nodes { additions deletions author { user { id } } }
            pageInfo { endCursor hasNextPage }
          }
        } } }
      }
    }'''
    cursor, add, dele, mine = None, 0, 0, 0
    while True:
        branch = graphql('loc_repo', query, {'name': name, 'owner': owner, 'cursor': cursor}
                         )['repository']['defaultBranchRef']
        if branch is None:  # repositório vazio
            return 0, 0, 0
        history = branch['target']['history']
        for c in history['nodes']:
            user = (c.get('author') or {}).get('user')
            if user and user['id'] == my_id:
                mine += 1
                add += c['additions']
                dele += c['deletions']
        if not history['pageInfo']['hasNextPage']:
            return add, dele, mine
        cursor = history['pageInfo']['endCursor']


# ------------------------------------------------------------------------- cache
def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def loc_totals(my_id):
    """
    Cache em cache/<sha256(usuario)>.txt, uma linha por repositório:
        <hash do repo> <commits totais> <meus commits> <linhas add> <linhas del>
    Só recalcula os repositórios cujo total de commits mudou.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, sha(USER_NAME) + '.txt')
    try:
        with open(path, encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []
    comment = lines[:COMMENT_SIZE] or ['Este bloco é só comentário. Escreva o que quiser aqui.\n'] * COMMENT_SIZE
    known = {l.split()[0]: l for l in lines[COMMENT_SIZE:] if l.strip()}

    repos = list_repos(AFFILIATIONS)
    hashes = [sha(r['nameWithOwner']) for r in repos]
    data = [known.get(h, f'{h} 0 0 0 0\n') for h in hashes]  # descarta repos que sumiram

    try:
        for i, repo in enumerate(repos):
            branch = repo['defaultBranchRef']
            if branch is None:
                data[i] = f'{hashes[i]} 0 0 0 0\n'
                continue
            total = branch['target']['history']['totalCount']
            if int(data[i].split()[1]) != total:
                owner, name = repo['nameWithOwner'].split('/')
                add, dele, mine = my_loc_in_repo(owner, name, my_id)
                data[i] = f'{hashes[i]} {total} {mine} {add} {dele}\n'
    finally:  # salva o que foi calculado mesmo se der erro no meio
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(comment)
            f.writelines(data)

    rows = [l.split() for l in data]
    commits = sum(int(r[2]) for r in rows)
    add = sum(int(r[3]) for r in rows)
    dele = sum(int(r[4]) for r in rows)
    return add, dele, add - dele, commits


# --------------------------------------------------------------------------- SVG
def fmt(n):
    """12345 -> '12.345' (padrão brasileiro)."""
    return f'{n:,}'.replace(',', '.')


def plural(n, singular, plural_):
    return singular if n == 1 else plural_


def set_value(root, element_id, value):
    """Troca o texto do elemento e realinha os pontinhos (<id>_dots) usando data-len."""
    text = fmt(value) if isinstance(value, int) else str(value)
    el = root.find(f".//*[@id='{element_id}']")
    if el is not None:
        el.text = text
    dots = root.find(f".//*[@id='{element_id}_dots']")
    if dots is not None:
        fill = int(dots.get('data-len', 0)) - len(text)
        dots.text = ' ' + '.' * fill + ' ' if fill > 0 else ' '


def svg_overwrite(filename, values):
    tree = etree.parse(filename)
    root = tree.getroot()
    for element_id, value in values.items():
        set_value(root, element_id, value)
    tree.write(filename, encoding='utf-8', xml_declaration=True)


def timed(label, fn, *args):
    start = time.perf_counter()
    result = fn(*args)
    print(f'{label:<22}{(time.perf_counter() - start) * 1000:>10.0f} ms')
    return result


if __name__ == '__main__':
    my_id = timed('conta', user_id, USER_NAME)
    add, dele, loc, commits = timed('linhas de código', loc_totals, my_id)
    repos_owned, stars = timed('repos/stars', repo_stats, ['OWNER'])
    repos_contrib, _ = timed('repos contribuídos', repo_stats, AFFILIATIONS)
    followers = timed('seguidores', follower_count, USER_NAME)

    values = {
        'repo_data': repos_owned,
        'contrib_data': repos_contrib,
        'star_data': stars,
        'commit_data': commits,
        'follower_data': followers,
        'loc_data': fmt(loc),
        'loc_add': fmt(add),
        'loc_del': fmt(dele),
    }

    for svg in SVG_FILES:
        svg_overwrite(svg, values)
    print('Chamadas à API GraphQL:', sum(QUERY_COUNT.values()), QUERY_COUNT)
