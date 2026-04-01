// ─── Inicialização ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
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
    // Gera as tarefas do dia (caso ainda não existam)
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

    // Resumo
    const concluidas = tarefas.filter(t => t.concluida).length;
    const total = tarefas.length;
    const pct = Math.round((concluidas / total) * 100);

    resumoEl.innerHTML = `
        <div class="stat-card">
            <div class="stat-value">${concluidas}/${total}</div>
            <div class="stat-label">Feitas</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">${pct}%</div>
            <div class="stat-label">${pct === 100 ? 'Tudo pronto! 🎉' : 'Continue assim!'}</div>
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

        for (const t of info.tarefas) {
            const doneClass = t.concluida ? 'done' : '';
            const check = t.concluida ? '✓' : '';

            // Verificar se tem lembretes
            const lemRes = await fetch(`/api/lembretes/${t.atividade_id}`);
            const lembretes = await lemRes.json();
            const temLembrete = lembretes.length > 0;

            html += `
                <div class="task-item ${doneClass}" onclick="abrirTarefa(${t.id}, ${t.atividade_id}, '${escapar(t.atividade_nome)}', '${escapar(t.atividade_descricao || '')}', ${t.concluida ? 1 : 0})">
                    <div class="task-checkbox">${check}</div>
                    <div class="task-info">
                        <div class="task-name">${t.atividade_nome}</div>
                        <div class="task-room">${info.icone} ${comodo}</div>
                        ${temLembrete ? '<div class="task-room text-warning">⚠️ Tem recado do patrão</div>' : ''}
                    </div>
                </div>`;
        }
        html += '</div>';
    }

    container.innerHTML = html;
}

function escapar(str) {
    return (str || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ─── Abrir tarefa ──────────────────────────────────────────
async function abrirTarefa(execucaoId, atividadeId, nome, descricao, concluida) {
    document.getElementById('modalTarefaTitulo').textContent = nome;
    document.getElementById('modalExecucaoId').value = execucaoId;
    document.getElementById('modalObservacao').value = '';

    // Descrição
    const descEl = document.getElementById('modalDescricao');
    if (descricao) {
        descEl.innerHTML = `<div class="card"><div class="card-subtitle">📝 ${descricao}</div></div>`;
    } else {
        descEl.innerHTML = '';
    }

    // Botões
    const btnConcluir = document.getElementById('btnConcluir');
    const btnDesfazer = document.getElementById('btnDesfazer');
    if (concluida) {
        btnConcluir.classList.add('hidden');
        btnDesfazer.classList.remove('hidden');
    } else {
        btnConcluir.classList.remove('hidden');
        btnDesfazer.classList.add('hidden');
    }

    // Carregar lembretes
    const lemRes = await fetch(`/api/lembretes/${atividadeId}`);
    const lembretes = await lemRes.json();
    const lemEl = document.getElementById('modalLembretes');

    if (lembretes.length > 0) {
        let html = '<div class="mb-2" style="font-weight:600;color:var(--warning)">⚠️ Recados do Patrão:</div>';
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

// ─── Concluir / Desfazer tarefa ────────────────────────────
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

// Fechar modal ao clicar fora
document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.classList.remove('active');
    });
});
