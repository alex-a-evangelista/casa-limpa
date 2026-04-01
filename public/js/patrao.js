// ─── Estado ────────────────────────────────────────────────
let dataAtual = new Date();
let notaSelecionada = 0;

// ─── Inicialização ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupStars();
    atualizarData();
    carregarTarefasDia();
    carregarAtividades();
    carregarHistorico();
    // Gerar tarefas do dia automaticamente
    fetch('/api/execucoes/gerar', { method: 'POST' });
});

// ─── Tabs ──────────────────────────────────────────────────
function setupTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(tab.dataset.tab).classList.add('active');

            // Mostrar/esconder navegação de data
            const dateNav = document.getElementById('dateNav');
            if (tab.dataset.tab === 'tarefas-dia') {
                dateNav.style.display = 'flex';
            } else {
                dateNav.style.display = 'none';
            }
        });
    });
}

// ─── Data ──────────────────────────────────────────────────
function formatarData(d) {
    const dias = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
    const meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
    return `${dias[d.getDay()]}, ${d.getDate()} ${meses[d.getMonth()]}`;
}

function dataISO(d) {
    return d.toISOString().split('T')[0];
}

function atualizarData() {
    document.getElementById('dateDisplay').textContent = formatarData(dataAtual);
}

function mudarDia(delta) {
    dataAtual.setDate(dataAtual.getDate() + delta);
    atualizarData();
    carregarTarefasDia();
}

// ─── Tarefas do Dia ────────────────────────────────────────
async function carregarTarefasDia() {
    const data = dataISO(dataAtual);
    const res = await fetch(`/api/execucoes?data=${data}`);
    const tarefas = await res.json();

    const container = document.getElementById('listaTarefasDia');
    const statsEl = document.getElementById('statsHoje');

    if (tarefas.length === 0) {
        statsEl.innerHTML = '';
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📋</div>
                <p>Nenhuma tarefa para este dia.</p>
            </div>`;
        return;
    }

    const concluidas = tarefas.filter(t => t.concluida).length;
    const total = tarefas.length;
    const pct = total > 0 ? Math.round((concluidas / total) * 100) : 0;

    statsEl.innerHTML = `
        <div class="stat-card">
            <div class="stat-value">${concluidas}/${total}</div>
            <div class="stat-label">Concluídas</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${pct}%</div>
            <div class="stat-label">Progresso</div>
        </div>
    `;

    // Agrupar por cômodo
    const porComodo = {};
    tarefas.forEach(t => {
        const key = t.comodo_nome;
        if (!porComodo[key]) porComodo[key] = { icone: t.comodo_icone, tarefas: [] };
        porComodo[key].tarefas.push(t);
    });

    let html = '';
    for (const [comodo, info] of Object.entries(porComodo)) {
        html += `<div class="comodo-section">
            <div class="comodo-header">${info.icone} ${comodo}</div>`;
        info.tarefas.forEach(t => {
            const doneClass = t.concluida ? 'done' : '';
            const check = t.concluida ? '✓' : '';
            html += `
                <div class="task-item ${doneClass}">
                    <div class="task-checkbox">${check}</div>
                    <div class="task-info">
                        <div class="task-name">${t.atividade_nome}</div>
                        ${t.hora_conclusao ? `<div class="task-room">Feita às ${t.hora_conclusao.split(' ')[1]}</div>` : ''}
                        ${t.observacao_empregada ? `<div class="task-room">💬 "${t.observacao_empregada}"</div>` : ''}
                    </div>
                    <div class="task-actions">
                        ${t.concluida ? `
                            <button class="btn btn-sm btn-primary" onclick="abrirAvaliar(${t.id}, ${t.atividade_id || 0}, '${escapar(t.atividade_nome)}', '${escapar(t.comodo_nome)}')">⭐ Avaliar</button>
                        ` : ''}
                    </div>
                </div>`;
        });
        html += '</div>';
    }

    container.innerHTML = html;
}

function escapar(str) {
    return (str || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ─── Avaliar ───────────────────────────────────────────────
function setupStars() {
    document.querySelectorAll('#avalStars .star').forEach(star => {
        star.addEventListener('click', () => {
            notaSelecionada = parseInt(star.dataset.val);
            document.getElementById('avalNota').value = notaSelecionada;
            document.querySelectorAll('#avalStars .star').forEach(s => {
                s.classList.toggle('active', parseInt(s.dataset.val) <= notaSelecionada);
            });
        });
    });
}

function abrirAvaliar(execucaoId, atividadeId, nome, comodo) {
    document.getElementById('avalExecucaoId').value = execucaoId;
    document.getElementById('avalAtividadeId').value = atividadeId;
    document.getElementById('avaliarInfo').innerHTML = `
        <div class="card mb-2">
            <div class="card-title">${nome}</div>
            <div class="card-subtitle">${comodo}</div>
        </div>`;

    // Reset
    notaSelecionada = 0;
    document.getElementById('avalNota').value = 0;
    document.getElementById('avalComentario').value = '';
    document.getElementById('avalFoto').value = '';
    document.getElementById('avalFotoPreview').classList.remove('visible');
    document.querySelectorAll('#avalStars .star').forEach(s => s.classList.remove('active'));

    // Carregar avaliações anteriores
    carregarAvaliacoes(execucaoId);

    abrirModal('modalAvaliar');
}

async function carregarAvaliacoes(execucaoId) {
    const res = await fetch(`/api/avaliacoes/${execucaoId}`);
    const avaliacoes = await res.json();

    if (avaliacoes.length > 0) {
        let html = '<div class="mb-2"><strong>Avaliações anteriores:</strong></div>';
        avaliacoes.forEach(a => {
            html += `<div class="card mb-1">
                <div class="stars-display">${gerarEstrelas(a.nota)}</div>
                ${a.comentario ? `<p class="mt-1" style="font-size:0.85rem">${a.comentario}</p>` : ''}
                ${a.foto ? `<img src="${a.foto}" style="max-width:100%;border-radius:8px;margin-top:0.5rem">` : ''}
                <div class="card-subtitle mt-1">${a.criado_em}</div>
            </div>`;
        });
        document.getElementById('avaliarInfo').innerHTML += html;
    }
}

function gerarEstrelas(nota) {
    let html = '';
    for (let i = 1; i <= 5; i++) {
        html += `<span class="star ${i <= nota ? 'active' : ''}">★</span>`;
    }
    return html;
}

async function salvarAvaliacao(e) {
    e.preventDefault();
    const nota = parseInt(document.getElementById('avalNota').value);
    if (nota === 0) {
        alert('Selecione uma nota de 1 a 5 estrelas');
        return;
    }

    const formData = new FormData();
    formData.append('execucao_id', document.getElementById('avalExecucaoId').value);
    formData.append('nota', nota);
    formData.append('comentario', document.getElementById('avalComentario').value);

    const fotoInput = document.getElementById('avalFoto');
    if (fotoInput.files[0]) {
        formData.append('foto', fotoInput.files[0]);
    }

    await fetch('/api/avaliacoes', { method: 'POST', body: formData });
    fecharModal('modalAvaliar');
    carregarTarefasDia();
    alert('Avaliação salva!');
}

// ─── Lembretes ─────────────────────────────────────────────
function abrirLembrete() {
    const atividadeId = document.getElementById('avalAtividadeId').value;
    document.getElementById('lembreteAtividadeId').value = atividadeId;
    document.getElementById('lembreteMensagem').value = '';
    document.getElementById('lembreteFoto').value = '';
    document.getElementById('lembreteFotoPreview').classList.remove('visible');
    fecharModal('modalAvaliar');
    abrirModal('modalLembrete');
}

async function salvarLembrete(e) {
    e.preventDefault();
    const formData = new FormData();
    formData.append('atividade_id', document.getElementById('lembreteAtividadeId').value);
    formData.append('mensagem', document.getElementById('lembreteMensagem').value);

    const fotoInput = document.getElementById('lembreteFoto');
    if (fotoInput.files[0]) {
        formData.append('foto', fotoInput.files[0]);
    }

    await fetch('/api/lembretes', { method: 'POST', body: formData });
    fecharModal('modalLembrete');
    alert('Recado enviado! Ela verá na próxima vez.');
}

// ─── Gerenciar Atividades ──────────────────────────────────
async function carregarAtividades() {
    const res = await fetch('/api/atividades');
    const atividades = await res.json();

    const container = document.getElementById('listaAtividades');

    if (atividades.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📝</div>
                <p>Nenhuma atividade cadastrada.<br>Clique no botão acima para criar.</p>
            </div>`;
        return;
    }

    // Agrupar por cômodo
    const porComodo = {};
    atividades.forEach(a => {
        const key = a.comodo_nome;
        if (!porComodo[key]) porComodo[key] = { icone: a.comodo_icone, atividades: [] };
        porComodo[key].atividades.push(a);
    });

    let html = '';
    for (const [comodo, info] of Object.entries(porComodo)) {
        html += `<div class="comodo-section">
            <div class="comodo-header">${info.icone} ${comodo}</div>`;
        info.atividades.forEach(a => {
            html += `
                <div class="card" style="display:flex;align-items:center;justify-content:space-between">
                    <div>
                        <div class="card-title">${a.nome}</div>
                        ${a.descricao ? `<div class="card-subtitle">${a.descricao}</div>` : ''}
                    </div>
                    <button class="btn btn-sm btn-danger" onclick="removerAtividade(${a.id}, '${escapar(a.nome)}')">🗑️</button>
                </div>`;
        });
        html += '</div>';
    }

    container.innerHTML = html;
}

async function abrirModalAtividade() {
    // Carregar cômodos
    const res = await fetch('/api/comodos');
    const comodos = await res.json();
    const select = document.getElementById('ativComodo');
    select.innerHTML = comodos.map(c => `<option value="${c.id}">${c.icone} ${c.nome}</option>`).join('');

    document.getElementById('ativNome').value = '';
    document.getElementById('ativDescricao').value = '';
    abrirModal('modalAtividade');
}

async function salvarAtividade(e) {
    e.preventDefault();
    await fetch('/api/atividades', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            comodo_id: parseInt(document.getElementById('ativComodo').value),
            nome: document.getElementById('ativNome').value,
            descricao: document.getElementById('ativDescricao').value
        })
    });
    fecharModal('modalAtividade');
    carregarAtividades();
    alert('Atividade criada! Ela aparecerá nas tarefas de amanhã.');
}

async function removerAtividade(id, nome) {
    if (!confirm(`Remover a atividade "${nome}"?`)) return;
    await fetch(`/api/atividades/${id}`, { method: 'DELETE' });
    carregarAtividades();
}

// ─── Histórico ─────────────────────────────────────────────
async function carregarHistorico() {
    const res = await fetch('/api/historico?dias=30');
    const historico = await res.json();

    const container = document.getElementById('listaHistorico');

    if (historico.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📊</div>
                <p>Nenhum histórico ainda.</p>
            </div>`;
        return;
    }

    let html = '';
    historico.forEach(h => {
        const d = new Date(h.data + 'T12:00:00');
        const dataFormatada = `${d.getDate().toString().padStart(2, '0')}/${(d.getMonth() + 1).toString().padStart(2, '0')}`;
        const pct = h.total > 0 ? Math.round((h.concluidas / h.total) * 100) : 0;
        const notaHtml = h.media_nota ? `⭐ ${h.media_nota}` : '';

        html += `
            <div class="historico-item">
                <div>
                    <div class="historico-data">${dataFormatada}</div>
                </div>
                <div class="historico-stats">
                    <span class="badge ${pct === 100 ? 'badge-success' : pct > 50 ? 'badge-warning' : 'badge-danger'}">
                        ${h.concluidas}/${h.total} (${pct}%)
                    </span>
                    ${notaHtml ? `<span class="badge badge-primary">${notaHtml}</span>` : ''}
                </div>
            </div>`;
    });

    container.innerHTML = html;
}

// ─── Modal helpers ─────────────────────────────────────────
function abrirModal(id) {
    document.getElementById(id).classList.add('active');
}

function fecharModal(id) {
    document.getElementById(id).classList.remove('active');
}

// Fechar modal ao clicar fora
document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.classList.remove('active');
    });
});

// ─── Foto preview ──────────────────────────────────────────
function previewFoto(input, previewId) {
    const preview = document.getElementById(previewId);
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = (e) => {
            preview.src = e.target.result;
            preview.classList.add('visible');
        };
        reader.readAsDataURL(input.files[0]);
    }
}
