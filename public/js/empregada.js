// ─── Verificar autenticação ────────────────────────────────
async function verificarAuth() {
    try {
        const res = await fetch('/api/auth/status');
        const data = await res.json();
        if (!data.logado || data.perfil !== 'empregada') {
            window.location.href = '/';
            return false;
        }
        if (data.trocar_senha) {
            window.location.href = '/';
            return false;
        }
        return true;
    } catch(e) {
        window.location.href = '/';
        return false;
    }
}

async function sair() {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/';
}

// ─── Interceptar erros 401 ────────────────────────────────
const _fetch = window.fetch;
window.fetch = async function(...args) {
    const res = await _fetch(...args);
    if (res.status === 401 && args[0] !== '/api/auth/status') {
        window.location.href = '/';
    }
    return res;
};

// ─── Inicialização ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    if (!await verificarAuth()) return;
    mostrarDataHoje();
    gerarTarefasDia();
});

// ─── Data ──────────────────────────────────────────────────
function mostrarDataHoje() {
    const hoje = new Date();
    const dias = ['Domingo', 'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado'];
    const meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
    document.getElementById('dateDisplay').textContent =
        `${dias[hoje.getDay()]}, ${hoje.getDate()} de ${meses[hoje.getMonth()]}`;
}

// ─── Carregar tarefas ──────────────────────────────────────
async function gerarTarefasDia() {
    await fetch('/api/execucoes/gerar', { method: 'POST' });
    carregarTarefas();
}

async function carregarTarefas() {
    const hoje = new Date().toISOString().split('T')[0];
    const res = await fetch(`/api/execucoes?data=${hoje}`);
    const tarefas = await res.json();

    const container = document.getElementById('listaTarefas');
    const emptyState = document.getElementById('emptyState');
    const resumoEl = document.getElementById('resumo');

    if (tarefas.length === 0) {
        container.innerHTML = '';
        emptyState.classList.remove('hidden');
        resumoEl.innerHTML = '';
        return;
    }

    emptyState.classList.add('hidden');

    const concluidas = tarefas.filter(t => t.concluida).length;
    const naoFeitas = tarefas.filter(t => !t.concluida && t.motivo_nao_feita).length;
    const total = tarefas.length;
    const pendentes = total - concluidas - naoFeitas;
    const pct = Math.round((concluidas / total) * 100);

    let msgProgresso = 'Continue assim!';
    if (pct === 100) msgProgresso = 'Tudo pronto! 🎉';
    else if (pendentes === 0 && naoFeitas > 0) msgProgresso = 'Tudo registrado!';

    resumoEl.innerHTML = `
        <div class="stat-card">
            <div class="stat-value">${concluidas}/${total}</div>
            <div class="stat-label">Feitas</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${pct}%</div>
            <div class="stat-label">${msgProgresso}</div>
        </div>
    `;

    // Agrupar por turno e cômodo
    const porTurno = { manha: {}, tarde: {}, qualquer: {} };
    for (const t of tarefas) {
        const turno = t.atividade_turno || 'qualquer';
        const key = t.comodo_nome;
        if (!porTurno[turno]) porTurno[turno] = {};
        if (!porTurno[turno][key]) porTurno[turno][key] = { icone: t.comodo_icone, tarefas: [] };
        porTurno[turno][key].tarefas.push(t);
    }

    // Pré-carregar lembretes
    const lembreteCache = {};
    for (const t of tarefas) {
        if (!lembreteCache[t.atividade_id]) {
            const lemRes = await fetch(`/api/lembretes/${t.atividade_id}`);
            lembreteCache[t.atividade_id] = await lemRes.json();
        }
    }

    const turnoLabels = { manha: '☀️ Manhã', tarde: '🌙 Tarde', qualquer: '' };
    let html = '';

    for (const [turno, comodos] of Object.entries(porTurno)) {
        if (Object.keys(comodos).length === 0) continue;
        if (turnoLabels[turno]) {
            html += `<div style="font-weight:700;font-size:1rem;margin:1rem 0 0.5rem;color:var(--gray-700)">${turnoLabels[turno]}</div>`;
        }
        for (const [comodo, info] of Object.entries(comodos)) {
            html += `<div class="comodo-section">
                <div class="comodo-header">${info.icone} ${comodo}</div>`;

            for (const t of info.tarefas) {
                const temLembrete = (lembreteCache[t.atividade_id] || []).length > 0;
                const doneClass = t.concluida ? 'done' : '';
                const check = t.concluida ? '✓' : '';
                const naoFeita = !t.concluida && t.motivo_nao_feita;

                html += `
                    <div class="task-item ${doneClass}" onclick="abrirTarefa(${t.id}, ${t.atividade_id}, '${escapar(t.atividade_nome)}', '${escapar(t.atividade_descricao || '')}', ${t.concluida ? 1 : 0}, '${escapar(t.atividade_turno || 'qualquer')}', '${escapar(t.observacao_empregada || '')}', '${escapar(t.motivo_nao_feita || '')}')">
                        <div class="task-checkbox" ${naoFeita ? 'style="background:var(--danger);border-color:var(--danger);color:white"' : ''}>${naoFeita ? '✕' : check}</div>
                        <div class="task-info">
                            <div class="task-name">${t.atividade_nome}</div>
                            <div class="task-room">${info.icone} ${comodo}</div>
                            ${temLembrete ? '<div class="task-room text-warning">⚠️ Tem recado dos moradores</div>' : ''}
                            ${t.observacao_empregada ? `<div class="task-room">💬 "${t.observacao_empregada}"</div>` : ''}
                            ${naoFeita ? `<div class="motivo-card">❌ ${t.motivo_nao_feita}</div>` : ''}
                        </div>
                    </div>`;
            }
            html += '</div>';
        }
    }

    container.innerHTML = html;
}

function escapar(str) {
    return (str || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ─── Abrir tarefa ──────────────────────────────────────────
async function abrirTarefa(execucaoId, atividadeId, nome, descricao, concluida, turno, obsExistente, motivoExistente) {
    document.getElementById('modalTarefaTitulo').textContent = nome;
    document.getElementById('modalExecucaoId').value = execucaoId;
    document.getElementById('modalAtividadeId').value = atividadeId;
    document.getElementById('modalObservacao').value = obsExistente || '';
    document.getElementById('motivoNaoFeita').value = motivoExistente || '';
    document.getElementById('motivoNaoFeitaGroup').classList.add('hidden');

    // Turno
    const turnoEl = document.getElementById('modalTurno');
    if (turno && turno !== 'qualquer') {
        const turnoLabel = turno === 'manha' ? '☀️ Manhã' : '🌙 Tarde';
        const turnoClass = turno === 'manha' ? 'turno-manha' : 'turno-tarde';
        turnoEl.innerHTML = `<span class="turno-badge ${turnoClass}">${turnoLabel}</span>`;
    } else {
        turnoEl.innerHTML = '';
    }

    // Descrição
    const descEl = document.getElementById('modalDescricao');
    if (descricao) {
        descEl.innerHTML = `<div class="card"><div class="card-subtitle">📝 ${descricao}</div></div>`;
    } else {
        descEl.innerHTML = '';
    }

    // Botões
    const btnConcluir = document.getElementById('btnConcluir');
    const btnNaoFeita = document.getElementById('btnNaoFeita');
    const btnDesfazer = document.getElementById('btnDesfazer');

    if (concluida || motivoExistente) {
        btnConcluir.classList.add('hidden');
        btnNaoFeita.classList.add('hidden');
        btnDesfazer.classList.remove('hidden');
    } else {
        btnConcluir.classList.remove('hidden');
        btnNaoFeita.classList.remove('hidden');
        btnDesfazer.classList.add('hidden');
    }

    // Carregar lembretes
    const lemRes = await fetch(`/api/lembretes/${atividadeId}`);
    const lembretes = await lemRes.json();
    const lemEl = document.getElementById('modalLembretes');

    if (lembretes.length > 0) {
        let html = '<div class="mb-2" style="font-weight:600;color:var(--warning)">⚠️ Recados dos Moradores:</div>';
        lembretes.forEach(l => {
            html += `
                <div class="lembrete-card">
                    <div class="lembrete-msg">${l.mensagem}</div>
                    ${l.foto ? `<img src="${l.foto}" alt="Foto do recado">` : ''}
                    <div class="lembrete-data">${l.criado_em}</div>
                </div>`;
        });
        lemEl.innerHTML = html;
    } else {
        lemEl.innerHTML = '';
    }

    abrirModal('modalTarefa');
}

// ─── Concluir tarefa ───────────────────────────────────────
async function concluirTarefa() {
    const id = document.getElementById('modalExecucaoId').value;
    const observacao = document.getElementById('modalObservacao').value;

    await fetch(`/api/execucoes/${id}/concluir`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ observacao })
    });

    fecharModal('modalTarefa');
    carregarTarefas();
}

// ─── Não conseguiu fazer ───────────────────────────────────
function mostrarMotivoNaoFeita() {
    document.getElementById('motivoNaoFeitaGroup').classList.remove('hidden');
    document.getElementById('motivoNaoFeita').focus();
}

async function registrarNaoFeita() {
    const id = document.getElementById('modalExecucaoId').value;
    const motivo = document.getElementById('motivoNaoFeita').value;

    if (!motivo.trim()) {
        alert('Por favor, explique o motivo');
        return;
    }

    // Também salva a observação geral se tiver
    const observacao = document.getElementById('modalObservacao').value;
    if (observacao) {
        await fetch(`/api/execucoes/${id}/concluir`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ observacao })
        });
        // Depois marca como não feita
        await fetch(`/api/execucoes/${id}/desfazer`, { method: 'POST' });
    }

    await fetch(`/api/execucoes/${id}/nao-feita`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ motivo })
    });

    fecharModal('modalTarefa');
    carregarTarefas();
}

// ─── Desfazer ──────────────────────────────────────────────
async function desfazerTarefa() {
    const id = document.getElementById('modalExecucaoId').value;
    await fetch(`/api/execucoes/${id}/desfazer`, { method: 'POST' });
    fecharModal('modalTarefa');
    carregarTarefas();
}

// ─── Modal helpers ─────────────────────────────────────────
function abrirModal(id) {
    document.getElementById(id).classList.add('active');
}

function fecharModal(id) {
    document.getElementById(id).classList.remove('active');
}

document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.classList.remove('active');
    });
});
