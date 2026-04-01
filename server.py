#!/usr/bin/env python3
"""Casa Limpa - Gerenciador de Atividades Domésticas"""

import os
import base64
import uuid
from datetime import datetime, date
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='public')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max upload

DATABASE_URL = os.environ.get('DATABASE_URL', '')

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
    """Executa query compatível com SQLite e PostgreSQL"""
    if DATABASE_URL:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Converter ? para %s (PostgreSQL)
        query = query.replace('?', '%s')
        cur.execute(query, params or ())
        return cur
    else:
        return conn.execute(query, params or ())


def db_fetchall(conn, query, params=None):
    cur = db_execute(conn, query, params)
    rows = cur.fetchall()
    if DATABASE_URL:
        return [dict(r) for r in rows]
    else:
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
                    observacao_empregada TEXT
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
    """Converte foto para base64 data URI"""
    if not file_obj or not file_obj.filename:
        return ''
    data = file_obj.read()
    ext = file_obj.filename.rsplit('.', 1)[-1].lower() if '.' in file_obj.filename else 'jpg'
    mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
            'gif': 'image/gif', 'webp': 'image/webp'}.get(ext, 'image/jpeg')
    b64 = base64.b64encode(data).decode('utf-8')
    return f"data:{mime};base64,{b64}"


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
def listar_comodos():
    conn = get_db()
    try:
        rows = db_fetchall(conn, "SELECT * FROM comodos ORDER BY nome")
        return jsonify(rows)
    finally:
        conn.close()


@app.route('/api/comodos', methods=['POST'])
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
def criar_atividade():
    data = request.json
    conn = get_db()
    try:
        cur = db_execute(conn, "INSERT INTO atividades (comodo_id, nome, descricao) VALUES (?, ?, ?)",
                         (data['comodo_id'], data['nome'], data.get('descricao', '')))
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
def listar_execucoes():
    data_filtro = request.args.get('data', date.today().isoformat())
    conn = get_db()
    try:
        rows = db_fetchall(conn, '''
            SELECT e.*, a.nome as atividade_nome, a.descricao as atividade_descricao,
                   c.nome as comodo_nome, c.icone as comodo_icone, a.comodo_id
            FROM execucoes e
            JOIN atividades a ON e.atividade_id = a.id
            JOIN comodos c ON a.comodo_id = c.id
            WHERE e.data = ?
            ORDER BY c.nome, a.nome
        ''', (data_filtro,))
        # Serializar datas para JSON
        for r in rows:
            for k, v in r.items():
                if isinstance(v, datetime):
                    r[k] = v.isoformat()
        return jsonify(rows)
    finally:
        conn.close()


@app.route('/api/execucoes/gerar', methods=['POST'])
def gerar_execucoes_dia():
    hoje = date.today().isoformat()
    conn = get_db()
    try:
        row = db_fetchone(conn, "SELECT COUNT(*) as total FROM execucoes WHERE data = ?", (hoje,))
        if row['total'] > 0:
            return jsonify({'ok': True, 'msg': 'Tarefas do dia já geradas'})

        atividades = db_fetchall(conn, "SELECT id FROM atividades WHERE ativa = 1")
        for atv in atividades:
            db_execute(conn, "INSERT INTO execucoes (atividade_id, data) VALUES (?, ?)", (atv['id'], hoje))
        conn.commit()
        return jsonify({'ok': True, 'geradas': len(atividades)})
    finally:
        conn.close()


@app.route('/api/execucoes/<int:id>/concluir', methods=['POST'])
def concluir_execucao(id):
    data = request.json or {}
    conn = get_db()
    try:
        if DATABASE_URL:
            db_execute(conn, '''
                UPDATE execucoes
                SET concluida = 1, hora_conclusao = NOW(),
                    observacao_empregada = ?
                WHERE id = ?
            ''', (data.get('observacao', ''), id))
        else:
            db_execute(conn, '''
                UPDATE execucoes
                SET concluida = 1, hora_conclusao = datetime('now', 'localtime'),
                    observacao_empregada = ?
                WHERE id = ?
            ''', (data.get('observacao', ''), id))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/api/execucoes/<int:id>/desfazer', methods=['POST'])
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
