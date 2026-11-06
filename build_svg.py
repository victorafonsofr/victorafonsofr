"""
Gera dark_mode.svg e light_mode.svg a partir de ascii_art.txt.

Rode apenas quando quiser mudar o layout/textos (python build_svg.py).
As estatísticas são atualizadas depois pelo today.py (via GitHub Actions).

Cada trecho de pontinhos de alinhamento (<id>_dots) carrega um atributo data-len
com a largura da "célula" — o today.py lê esse valor para realinhar os números.
"""
from xml.sax.saxutils import escape

W = 60            # largura (em caracteres) da coluna de texto
WIDTH = 1100
X_ART, Y_ART, ART_PITCH, ART_FONT = 15, 30, 15, 13
X_TXT, Y_TXT, PITCH, TXT_FONT = 478, 34, 22, 16

THEMES = {
    'dark_mode.svg': dict(bg='#161b22', text='#c9d1d9', key='#ffa657', value='#a5d6ff',
                          cc='#616e7f', add='#3fb950', dele='#f85149'),
    'light_mode.svg': dict(bg='#f6f8fa', text='#24292f', key='#953800', value='#0a3069',
                           cc='#c2cfde', add='#1a7f37', dele='#cf222e'),
}


def dots(text, length):
    """Mesma regra usada pelo today.py: ' ....' + ' ' preenchendo até `length`."""
    fill = length - len(text)
    return ' ' + '.' * fill + ' ' if fill > 0 else ' '


class Line:
    def __init__(self, y):
        self.y, self.parts = y, []

    def add(self, text, cls=None, id=None, data_len=None):
        attrs = ''
        if cls:
            attrs += f' class="{cls}"'
        if id:
            attrs += f' id="{id}"'
        if data_len is not None:
            attrs += f' data-len="{data_len}"'
        self.parts.append((attrs, escape(text)))
        return self

    def kv(self, key, value, id=None):
        """Linha estática: chave ..... valor (alinhada em W colunas)."""
        length = W - len(key) - 3
        self.add(key, 'key').add(':').add(dots(value, length), 'cc').add(value, 'value', id)
        return self

    def dyn(self, key, value, id, length):
        """Valor dinâmico: guarda data-len nos pontinhos para o today.py."""
        self.add(key, 'key').add(':')
        self.add(dots(value, length), 'cc', f'{id}_dots', length).add(value, 'value', id)
        return self

    def svg(self):
        out = []
        for i, (attrs, text) in enumerate(self.parts):
            pos = f' x="{X_TXT}" y="{self.y}"' if i == 0 else ''
            out.append(f'<tspan{pos}{attrs}>{text}</tspan>')
        return ''.join(out)


def section(title):
    return Line(0).add(f'- {title}', 'key').add(' ' + '-' * (W - len(title) - 3))


def build_lines(initial):
    rows = []  # lista de Line (ou None para linha em branco)
    rows.append(Line(0).add('victor@afonso', 'key').add(' ' + '-' * (W - 14)))
    rows.append(Line(0).kv('OS', 'Debian 13, Windows 11'))
    rows.append(Line(0).dyn('Uptime', initial['age'], 'age_data', W - 6 - 3))
    rows.append(Line(0).kv('IDE', 'NetBeans 31', 'vscode 1.145'))
    rows.append(Line(0).kv('Kernel', 'role:Student'))
    rows.append(None)
    rows.append(Line(0).kv('Languages.dev', 'C, Java, Python, JavaScript, SQL'))
    rows.append(Line(0).kv('Languages.web', 'HTML, CSS, JavaScript'))
    rows.append(Line(0).kv('Languages.human', 'English, Portuguese, French (currently learning)'))   
    rows.append(None)
    rows.append(Line(0).kv('Interests.infra', 'Network security, infrastructure, DevOps'))
    rows.append(Line(0).kv('Interests.dev', 'back-end, databases, AI, cybersecurity'))
    rows.append(None)
    rows.append(section('.contact'))
    rows.append(Line(0).kv('email', 'victorafernandes28@gmail.com'))
    rows.append(Line(0).kv('linkedIn', 'victorafonsofr'))
    rows.append(None)
    rows.append(section('github.stats'))

    l = Line(0).dyn('Repos', initial['repo'], 'repo_data', 6)
    l.add(' {').add('Contributed', 'key').add(': ').add(initial['contrib'], 'value', 'contrib_data')
    l.add('} | ').dyn('Stars', initial['star'], 'star_data', 16)
    rows.append(l)

    l = Line(0).dyn('Commits', initial['commit'], 'commit_data', 23)
    l.add(' | ').dyn('Followers', initial['follower'], 'follower_data', 11)
    rows.append(l)

    l = Line(0).dyn('Lines of code in here', initial['loc'], 'loc_data', 9)
    l.add(' ( ').add(initial['add'], 'addColor', 'loc_add').add('++', 'addColor')
    l.add(', ').add(initial['del'], 'delColor', 'loc_del').add('--', 'delColor').add(' )')
    rows.append(l)

    # posiciona verticalmente
    placed = []
    for i, row in enumerate(rows):
        if row is not None:
            row.y = Y_TXT + i * PITCH
            placed.append(row)
    return placed


def render(theme, art, lines):
    height = max(Y_ART + len(art) * ART_PITCH, Y_TXT + len(lines) * PITCH + 90) + 10
    css = (
        f"text, tspan {{ white-space: pre; }}\n"
        f".mono {{ font-family: Consolas, 'DejaVu Sans Mono', Menlo, "
        f"'Liberation Mono', monospace; }}\n"
        f".key {{ fill: {theme['key']}; }} .value {{ fill: {theme['value']}; }}\n"
        f".cc {{ fill: {theme['cc']}; }} .addColor {{ fill: {theme['add']}; }} "
        f".delColor {{ fill: {theme['dele']}; }}"
    )
    art_tspans = ''.join(
        f'<tspan x="{X_ART}" y="{Y_ART + i * ART_PITCH}">{escape(row)}</tspan>'
        for i, row in enumerate(art)
    )
    text_tspans = ''.join(l.svg() for l in lines)
    return f'''<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="Consolas, 'DejaVu Sans Mono', Menlo, 'Liberation Mono', monospace" width="{WIDTH}px" height="{height}px" font-size="{TXT_FONT}px">
<style>
{css}
</style>
<rect width="{WIDTH}px" height="{height}px" fill="{theme['bg']}" rx="15"/>
<text x="{X_ART}" y="{Y_ART}" fill="{theme['text']}" font-size="{ART_FONT}px" xml:space="preserve">{art_tspans}</text>
<text x="{X_TXT}" y="{Y_TXT}" fill="{theme['text']}" xml:space="preserve">{text_tspans}</text>
</svg>
'''


if __name__ == '__main__':
    with open('ascii_art.txt', encoding='utf-8') as f:
        art = [line.rstrip() for line in f.read().splitlines()]
    # valores iniciais (o today.py substitui tudo na primeira execução da Action)
    initial = dict(age='X years, X months, X days', repo='23', contrib='23', star='1',
                   commit='0', follower='9', loc='0', add='0', **{'del': '0'})
    lines = build_lines(initial)
    for name, theme in THEMES.items():
        with open(name, 'w', encoding='utf-8') as f:
            f.write(render(theme, art, lines))
        print('gerado', name)
