#!/usr/bin/env python3
"""Casa Limpa - Gerenciador de Atividades Domésticas"""

import os
import base64
import hashlib
import secrets
import uuid
from datetime import datetime, date
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, session

app = Flask(__name__, static_folder='public')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max upload
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))

DATABASE_URL = os.environ.get('DATABASE_URL', '')

SENHA_INICIAL = '1234'


# ─── Segurança de senhas ───────────────────────────────────────

def hash_senha(senha):
    """Gera hash seguro da senha com salt"""
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', senha.encode(), salt.encode(), 100000)
    return f"{salt}:{h.hex()}"


def verificar_senha(senha, hash_armazenado):
    """Verifica se a senha confere com o hash"""
    try:
        salt, h = hash_armazenado.split(':')
        h_teste = hashlib.pbkdf2_hmac('sha256', senha.encode(), salt.encode(), 100000)
        return h_teste.hex() == h
    except Exception:
        return False


# ─── Banco de dados ────────────────────────────────────────────

def get_db():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'casa_limpa.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


def db_execute(conn, query, params=None):
    if DATABASE_URL:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query = query.replace('?', '%s')
        cur.execute(query, params or ())
        return cur
    else:
        return conn.execute(query, params or ())


def db_fetchall(conn, query, params=None):
    cur = db_execute(conn, query, params)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def db_fetchone(conn, query, params=None):
    cur = db_execute(conn, query, params)
    row = cur.fetchone()
    if row is None:
        return None
    return dict(row)


def init_db():
    conn = get_db()
    try:
        if DATABASE_URL:
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    perfil TEXT NOT NULL UNIQUE,
                    senha_hash TEXT NOT NULL,
                    senha_temporaria INTEGER DEFAULT 1,
                    criado_em TIMESTAMP DEFAULT NOW()
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS comodos (
                    id SERIAL PRIMARY KEY,
                    nome TEXT NOT NULL UNIQUE,
                    icone TEXT DEFAULT '🏠',
                    criado_em TIMESTAMP DEFAULT NOW()
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS atividades (
                    id SERIAL PRIMARY KEY,
                    comodo_id INTEGER NOT NULL REFERENCES comodos(id),
                    nome TEXT NOT NULL,
                    descricao TEXT,
                    ativa INTEGER DEFAULT 1,
                    recorrente INTEGER DEFAULT 0,
                    dias_semana TEXT DEFAULT '',
                    turno TEXT DEFAULT 'qualquer',
                    criado_em TIMESTAMP DEFAULT NOW()
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS execucoes (
                    id SERIAL PRIMARY KEY,
                    atividade_id INTEGER NOT NULL REFERENCES atividades(id),
                    data TEXT NOT NULL,
                    concluida INTEGER DEFAULT 0,
                    hora_conclusao TIMESTAMP,
                    observacao_empregada TEXT,
                    motivo_nao_feita TEXT
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS avaliacoes (
                    id SERIAL PRIMARY KEY,
                    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
                    nota INTEGER NOT NULL CHECK(nota >= 1 AND nota <= 5),
                    comentario TEXT,
                    foto TEXT,
                    criado_em TIMESTAMP DEFAULT NOW()
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS lembretes (
                    id SERIAL PRIMARY KEY,
                    atividade_id INTEGER NOT NULL REFERENCES atividades(id),
                    mensagem TEXT NOT NULL,
                    foto TEXT,
                    ativo INTEGER DEFAULT 1,
                    criado_em TIMESTAMP DEFAULT NOW()
                )
            ''')
            conn.commit()
        else:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    perfil TEXT NOT NULL UNIQUE,
                    senha_hash TEXT NOT NULL,
                    senha_temporaria INTEGER DEFAULT 1,
                    criado_em TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE TABLE IF NOT EXISTS comodos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL UNIQUE,
                    icone TEXT DEFAULT '🏠',
                    criado_em TEXT DEFAULT (datetime('now', 'localtime'))
                );
                CREATE TABLE IF NOT EXISTS atividades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comodo_id INTEGER NOT NULL,
                    nome TEXT NOT NULL,
                    descricao TEXT,
                    ativa INTEGER DEFAULT 1,
                    recorrente INTEGER DEFAULT 0,
                    dias_semana TEXT DEFAULT '',
                    turno TEXT DEFAULT 'qualquer',
                    criado_em TEXT DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (comodo_id) REFERENCES comodos(id)
                );
                CREATE TABLE IF NOT EXISTS execucoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    atividade_id INTEGER NOT NULL,
                    data TEXT NOT NULL,
                    concluida INTEGER DEFAULT 0,
                    hora_conclusao TEXT,
                    observacao_empregada TEXT,
                    motivo_nao_feita TEXT,
                    FOREIGN KEY (atividade_id) REFERENCES atividades(id)
                );
                CREATE TABLE IF NOT EXISTS avaliacoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execucao_id INTEGER NOT NULL,
                    nota INTEGER NOT NULL CHECK(nota >= 1 AND nota <= 5),
                    comentario TEXT,
                    foto TEXT,
                    criado_em TEXT DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (execucao_id) REFERENCES execucoes(id)
                );
                CREATE TABLE IF NOT EXISTS lembretes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    atividade_id INTEGER NOT NULL,
                    mensagem TEXT NOT NULL,
                    foto TEXT,
                    ativo INTEGER DEFAULT 1,
                    criado_em TEXT DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (atividade_id) REFERENCES atividades(id)
                );
            ''')

        # Criar usuários padrão com senha 1234 se não existirem
        row = db_fetchone(conn, "SELECT COUNT(*) as total FROM usuarios")
        if row['total'] == 0:
            hash_inicial = hash_senha(SENHA_INICIAL)
            db_execute(conn, "INSERT INTO usuarios (perfil, senha_hash, senha_temporaria) VALUES (?, ?, 1)",
                       ('patrao', hash_inicial))
            db_execute(conn, "INSERT INTO usuarios (perfil, senha_hash, senha_temporaria) VALUES (?, ?, 1)",
                       ('empregada', hash_inicial))
            conn.commit()

        # Inserir cômodos padrão se tabela vazia
        row = db_fetchone(conn, "SELECT COUNT(*) as total FROM comodos")
        if row['total'] == 0:
            comodos_padrao = [
                ('Sala', '🛋️'), ('Cozinha', '🍳'), ('Banheiro', '🚿'),
                ('Quarto', '🛏️'), ('Lavanderia', '👕'), ('Escritório', '💻'),
                ('Varanda', '🌿'), ('Área de Serviço', '🧹')
            ]
            for nome, icone in comodos_padrao:
                db_execute(conn, "INSERT INTO comodos (nome, icone) VALUES (?, ?)", (nome, icone))
            conn.commit()
    finally:
        conn.close()


def salvar_foto_base64(file_obj):
    if not file_obj or not file_obj.filename:
        return ''
    data = file_obj.read()
    ext = file_obj.filename.rsplit('.', 1)[-1].lower() if '.' in file_obj.filename else 'jpg'
    mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
            'gif': 'image/gif', 'webp': 'image/webp'}.get(ext, 'image/jpeg')
    b64 = base64.b64encode(data).decode('utf-8')
    return f"data:{mime};base64,{b64}"


# ─── Autenticação ──────────────────────────────────────────────

def login_requerido(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'perfil' not in session:
            return jsonify({'erro': 'Não autorizado', 'codigo': 'NAO_AUTENTICADO'}), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    perfil = data.get('perfil', '').lower().strip()
    senha = data.get('senha', '')

    if perfil not in ('patrao', 'empregada'):
        return jsonify({'erro': 'Perfil inválido'}), 400

    conn = get_db()
    try:
        usuario = db_fetchone(conn, "SELECT * FROM usuarios WHERE perfil = ?", (perfil,))
        if not usuario or not verificar_senha(senha, usuario['senha_hash']):
            return jsonify({'erro': 'Senha incorreta'}), 401

        session['perfil'] = perfil
        session['usuario_id'] = usuario['id']
        session.permanent = True

        return jsonify({
            'ok': True,
            'perfil': perfil,
            'trocar_senha': usuario['senha_temporaria'] == 1
        })
    finally:
        conn.close()


@app.route('/api/auth/trocar-senha', methods=['POST'])
@login_requerido
def trocar_senha():
    data = request.json
    senha_atual = data.get('senha_atual', '')
    senha_nova = data.get('senha_nova', '')

    if len(senha_nova) < 4:
        return jsonify({'erro': 'A nova senha deve ter pelo menos 4 caracteres'}), 400

    if senha_nova == SENHA_INICIAL:
        return jsonify({'erro': 'Escolha uma senha diferente da inicial'}), 400

    conn = get_db()
    try:
        usuario = db_fetchone(conn, "SELECT * FROM usuarios WHERE perfil = ?", (session['perfil'],))
        if not verificar_senha(senha_atual, usuario['senha_hash']):
            return jsonify({'erro': 'Senha atual incorreta'}), 401

        novo_hash = hash_senha(senha_nova)
        db_execute(conn, "UPDATE usuarios SET senha_hash = ?, senha_temporaria = 0 WHERE perfil = ?",
                   (novo_hash, session['perfil']))
        conn.commit()
        return jsonify({'ok': True, 'msg': 'Senha alterada com sucesso!'})
    finally:
        conn.close()


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    if 'perfil' in session:
        conn = get_db()
        try:
            usuario = db_fetchone(conn, "SELECT senha_temporaria FROM usuarios WHERE perfil = ?",
                                  (session['perfil'],))
            return jsonify({
                'logado': True,
                'perfil': session['perfil'],
                'trocar_senha': usuario['senha_temporaria'] == 1 if usuario else False
            })
        finally:
            conn.close()
    return jsonify({'logado': False})


# ─── Rotas de páginas ───────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    if filename.startswith('api/'):
        return jsonify({'erro': 'Rota não encontrada'}), 404
    return send_from_directory('public', filename)


# ─── API: Cômodos ──────────────────────────────────────────────

@app.route('/api/comodos', methods=['GET'])
@login_requerido
def listar_comodos():
    conn = get_db()
    try:
        rows = db_fetchall(conn, "SELECT * FROM comodos ORDER BY nome")
        return jsonify(rows)
    finally:
        conn.close()


@app.route('/api/comodos', methods=['POST'])
@login_requerido
def criar_comodo():
    data = request.json
    conn = get_db()
    try:
        db_execute(conn, "INSERT INTO comodos (nome, icone) VALUES (?, ?)",
                   (data['nome'], data.get('icone', '🏠')))
        conn.commit()
        return jsonify({'ok': True}), 201
    except Exception:
        conn.rollback()
        return jsonify({'erro': 'Cômodo já existe'}), 400
    finally:
        conn.close()


# ─── API: Atividades ───────────────────────────────────────────

@app.route('/api/atividades', methods=['GET'])
@login_requerido
def listar_atividades():
    conn = get_db()
    try:
        rows = db_fetchall(conn, '''
            SELECT a.*, c.nome as comodo_nome, c.icone as comodo_icone
            FROM atividades a
            JOIN comodos c ON a.comodo_id = c.id
            WHERE a.ativa = 1
            ORDER BY c.nome, a.nome
        ''')
        return jsonify(rows)
    finally:
        conn.close()


@app.route('/api/atividades', methods=['POST'])
@login_requerido
def criar_atividade():
    data = request.json
    conn = get_db()
    try:
        recorrente = 1 if data.get('recorrente') else 0
        dias_semana = ','.join(data.get('dias_semana', [])) if data.get('dias_semana') else ''
        turno = data.get('turno', 'qualquer')
        cur = db_execute(conn,
            "INSERT INTO atividades (comodo_id, nome, descricao, recorrente, dias_semana, turno) VALUES (?, ?, ?, ?, ?, ?)",
            (data['comodo_id'], data['nome'], data.get('descricao', ''), recorrente, dias_semana, turno))
        conn.commit()
        if DATABASE_URL:
            cur.execute("SELECT lastval()")
            atividade_id = cur.fetchone()['lastval']
        else:
            atividade_id = cur.lastrowid
        return jsonify({'ok': True, 'id': atividade_id}), 201
    finally:
        conn.close()


@app.route('/api/atividades/<int:id>', methods=['DELETE'])
@login_requerido
def remover_atividade(id):
    conn = get_db()
    try:
        db_execute(conn, "UPDATE atividades SET ativa = 0 WHERE id = ?", (id,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ─── API: Execuções (tarefas do dia) ───────────────────────────

@app.route('/api/execucoes', methods=['GET'])
@login_requerido
def listar_execucoes():
    data_filtro = request.args.get('data', date.today().isoformat())
    conn = get_db()
    try:
        rows = db_fetchall(conn, '''
            SELECT e.*, a.nome as atividade_nome, a.descricao as atividade_descricao,
                   c.nome as comodo_nome, c.icone as comodo_icone, a.comodo_id,
                   a.turno as atividade_turno, a.recorrente, a.dias_semana
            FROM execucoes e
            JOIN atividades a ON e.atividade_id = a.id
            JOIN comodos c ON a.comodo_id = c.id
            WHERE e.data = ?
            ORDER BY a.turno, c.nome, a.nome
        ''', (data_filtro,))
        for r in rows:
            for k, v in r.items():
                if isinstance(v, datetime):
                    r[k] = v.isoformat()
        return jsonify(rows)
    finally:
        conn.close()


@app.route('/api/execucoes/gerar', methods=['POST'])
@login_requerido
def gerar_execucoes_dia():
    hoje = date.today().isoformat()
    dia_semana = str(date.today().weekday())  # 0=segunda, 6=domingo
    conn = get_db()
    try:
        row = db_fetchone(conn, "SELECT COUNT(*) as total FROM execucoes WHERE data = ?", (hoje,))
        if row['total'] > 0:
            return jsonify({'ok': True, 'msg': 'Tarefas do dia já geradas'})

        atividades = db_fetchall(conn, "SELECT id, recorrente, dias_semana FROM atividades WHERE ativa = 1")
        geradas = 0
        for atv in atividades:
            # Se não é recorrente, gera sempre
            if not atv['recorrente']:
                db_execute(conn, "INSERT INTO execucoes (atividade_id, data) VALUES (?, ?)", (atv['id'], hoje))
                geradas += 1
            else:
                # Se é recorrente, só gera no dia correto
                dias = atv['dias_semana'].split(',') if atv['dias_semana'] else []
                if dia_semana in dias:
                    db_execute(conn, "INSERT INTO execucoes (atividade_id, data) VALUES (?, ?)", (atv['id'], hoje))
                    geradas += 1
        conn.commit()
        return jsonify({'ok': True, 'geradas': geradas})
    finally:
        conn.close()


@app.route('/api/execucoes/<int:id>/concluir', methods=['POST'])
@login_requerido
def concluir_execucao(id):
    data = request.json or {}
    conn = get_db()
    try:
        if DATABASE_URL:
            db_execute(conn, '''
                UPDATE execucoes
                SET concluida = 1, hora_conclusao = NOW(),
                    observacao_empregada = ?, motivo_nao_feita = NULL
                WHERE id = ?
            ''', (data.get('observacao', ''), id))
        else:
            db_execute(conn, '''
                UPDATE execucoes
                SET concluida = 1, hora_conclusao = datetime('now', 'localtime'),
                    observacao_empregada = ?, motivo_nao_feita = NULL
                WHERE id = ?
            ''', (data.get('observacao', ''), id))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/api/execucoes/<int:id>/nao-feita', methods=['POST'])
@login_requerido
def nao_feita_execucao(id):
    """Registra que a tarefa não foi feita com um motivo"""
    data = request.json or {}
    conn = get_db()
    try:
        db_execute(conn, '''
            UPDATE execucoes
            SET concluida = 0, motivo_nao_feita = ?
            WHERE id = ?
        ''', (data.get('motivo', ''), id))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/api/execucoes/<int:id>/desfazer', methods=['POST'])
@login_requerido
def desfazer_execucao(id):
    conn = get_db()
    try:
        db_execute(conn, "UPDATE execucoes SET concluida = 0, hora_conclusao = NULL WHERE id = ?", (id,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ─── API: Avaliações ───────────────────────────────────────────

@app.route('/api/avaliacoes', methods=['POST'])
@login_requerido
def criar_avaliacao():
    nota = request.form.get('nota', type=int)
    execucao_id = request.form.get('execucao_id', type=int)
    comentario = request.form.get('comentario', '')
    foto_b64 = ''

    if 'foto' in request.files:
        foto_b64 = salvar_foto_base64(request.files['foto'])

    conn = get_db()
    try:
        db_execute(conn, "INSERT INTO avaliacoes (execucao_id, nota, comentario, foto) VALUES (?, ?, ?, ?)",
                   (execucao_id, nota, comentario, foto_b64))
        conn.commit()
        return jsonify({'ok': True}), 201
    finally:
        conn.close()


@app.route('/api/avaliacoes/<int:execucao_id>', methods=['GET'])
@login_requerido
def ver_avaliacao(execucao_id):
    conn = get_db()
    try:
        rows = db_fetchall(conn, "SELECT * FROM avaliacoes WHERE execucao_id = ? ORDER BY criado_em DESC",
                           (execucao_id,))
        for r in rows:
            for k, v in r.items():
                if isinstance(v, datetime):
                    r[k] = v.isoformat()
        return jsonify(rows)
    finally:
        conn.close()


# ─── API: Lembretes ────────────────────────────────────────────

@app.route('/api/lembretes', methods=['POST'])
@login_requerido
def criar_lembrete():
    foto_b64 = ''

    if request.content_type and 'multipart/form-data' in request.content_type:
        atividade_id = request.form.get('atividade_id', type=int)
        mensagem = request.form.get('mensagem', '')
        if 'foto' in request.files:
            foto_b64 = salvar_foto_base64(request.files['foto'])
    else:
        data = request.json
        atividade_id = data['atividade_id']
        mensagem = data['mensagem']

    conn = get_db()
    try:
        db_execute(conn, "INSERT INTO lembretes (atividade_id, mensagem, foto) VALUES (?, ?, ?)",
                   (atividade_id, mensagem, foto_b64))
        conn.commit()
        return jsonify({'ok': True}), 201
    finally:
        conn.close()


@app.route('/api/lembretes/<int:atividade_id>', methods=['GET'])
@login_requerido
def listar_lembretes(atividade_id):
    conn = get_db()
    try:
        rows = db_fetchall(conn, '''
            SELECT * FROM lembretes
            WHERE atividade_id = ? AND ativo = 1
            ORDER BY criado_em DESC
        ''', (atividade_id,))
        for r in rows:
            for k, v in r.items():
                if isinstance(v, datetime):
                    r[k] = v.isoformat()
        return jsonify(rows)
    finally:
        conn.close()


@app.route('/api/lembretes/<int:id>/desativar', methods=['POST'])
@login_requerido
def desativar_lembrete(id):
    conn = get_db()
    try:
        db_execute(conn, "UPDATE lembretes SET ativo = 0 WHERE id = ?", (id,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


# ─── API: Histórico ────────────────────────────────────────────

@app.route('/api/historico', methods=['GET'])
@login_requerido
def historico():
    dias = request.args.get('dias', 30, type=int)
    conn = get_db()
    try:
        rows = db_fetchall(conn, '''
            SELECT e.data, COUNT(*) as total,
                   SUM(CASE WHEN e.concluida = 1 THEN 1 ELSE 0 END) as concluidas,
                   ROUND(AVG(CASE WHEN av.nota IS NOT NULL THEN av.nota END)::numeric, 1) as media_nota
            FROM execucoes e
            LEFT JOIN avaliacoes av ON av.execucao_id = e.id
            GROUP BY e.data
            ORDER BY e.data DESC
            LIMIT ?
        ''' if DATABASE_URL else '''
            SELECT e.data, COUNT(*) as total,
                   SUM(CASE WHEN e.concluida = 1 THEN 1 ELSE 0 END) as concluidas,
                   ROUND(AVG(CASE WHEN av.nota IS NOT NULL THEN av.nota END), 1) as media_nota
            FROM execucoes e
            LEFT JOIN avaliacoes av ON av.execucao_id = e.id
            GROUP BY e.data
            ORDER BY e.data DESC
            LIMIT ?
        ''', (dias,))
        return jsonify(rows)
    finally:
        conn.close()


# ─── Inicialização ─────────────────────────────────────────────

init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"\n🏠 Casa Limpa rodando em http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=True)
