/**
 * FinBot Vendor Portal - FinDrive File Management
 */

const FileState = {
    files: [],
    editingFileId: null,
};

ready(function () {
    initializeFiles();
});

async function initializeFiles() {
    initializeFileModal();
    initializeFileViewModal();

    const createBtn = document.getElementById('create-file-btn');
    if (createBtn) createBtn.addEventListener('click', () => openFileModal());

    await loadFiles();
}

async function loadFiles() {
    const container = document.getElementById('files-list');
    const emptyState = document.getElementById('files-empty-state');

    try {
        const response = await api.get('/vendor/api/v1/findrive');
        const data = response.data || response;
        const files = data.files || [];
        FileState.files = files;

        document.getElementById('stat-file-count').textContent = files.length;

        if (files.length === 0) {
            container.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }

        emptyState.classList.add('hidden');
        container.innerHTML = files.map(f => renderFileRow(f)).join('');

        container.querySelectorAll('.view-file-btn').forEach(btn => {
            btn.addEventListener('click', () => viewFile(parseInt(btn.dataset.fileId)));
        });
        container.querySelectorAll('.edit-file-btn').forEach(btn => {
            btn.addEventListener('click', () => editFile(parseInt(btn.dataset.fileId)));
        });
        container.querySelectorAll('.delete-file-btn').forEach(btn => {
            btn.addEventListener('click', () => deleteFile(parseInt(btn.dataset.fileId)));
        });
    } catch (error) {
        console.error('Error loading files:', error);
        container.innerHTML = '<p class="text-center py-8 text-red-400">Failed to load files.</p>';
    }
}

function renderFileRow(file) {
    const date = new Date(file.created_at).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric'
    });
    const size = file.file_size < 1024
        ? `${file.file_size} B`
        : `${(file.file_size / 1024).toFixed(1)} KB`;
    const fileType = (file.file_type || 'pdf').toUpperCase();

    return `
        <div class="file-row">
            <div class="flex items-center gap-3 flex-1 min-w-0">
                <div class="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center flex-shrink-0">
                    <span class="text-xs font-bold text-red-400">${fileType}</span>
                </div>
                <div class="min-w-0">
                    <div class="text-sm font-medium text-text-bright truncate">${escFileHtml(file.filename)}</div>
                    <div class="text-xs text-text-secondary">${size} &middot; ${date} &middot; ${escFileHtml(file.folder_path)}</div>
                </div>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
                <button class="view-file-btn p-2 text-text-secondary hover:text-vendor-primary transition-colors rounded-lg hover:bg-vendor-primary/10" data-file-id="${file.id}" title="View">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                    </svg>
                </button>
                <button class="edit-file-btn p-2 text-text-secondary hover:text-vendor-accent transition-colors rounded-lg hover:bg-vendor-accent/10" data-file-id="${file.id}" title="Edit">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                    </svg>
                </button>
                <button class="delete-file-btn p-2 text-text-secondary hover:text-vendor-danger transition-colors rounded-lg hover:bg-red-500/10" data-file-id="${file.id}" title="Delete">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                </button>
            </div>
        </div>
    `;
}

function initializeFileModal() {
    const modal = document.getElementById('file-modal');
    const closeBtn = document.getElementById('close-file-modal-btn');
    const cancelBtn = document.getElementById('cancel-file-btn');
    const form = document.getElementById('file-form');

    if (!modal) return;

    [closeBtn, cancelBtn].forEach(btn => {
        if (btn) btn.addEventListener('click', closeFileModal);
    });
    modal.addEventListener('click', (e) => { if (e.target === modal) closeFileModal(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.classList.contains('hidden')) closeFileModal(); });
    form.addEventListener('submit', handleFileSubmit);
}

function openFileModal(file = null) {
    const modal = document.getElementById('file-modal');
    const title = document.getElementById('file-modal-title');
    const submitText = document.getElementById('submit-file-text');
    const form = document.getElementById('file-form');

    form.reset();

    if (file) {
        FileState.editingFileId = file.id;
        title.textContent = 'Edit Document';
        submitText.textContent = 'Save Changes';
        document.getElementById('file-edit-id').value = file.id;
        document.getElementById('file-name').value = file.filename;
        document.getElementById('file-content').value = file.content_text || '';
    } else {
        FileState.editingFileId = null;
        title.textContent = 'New Document';
        submitText.textContent = 'Upload PDF';
        document.getElementById('file-edit-id').value = '';
    }

    modal.classList.remove('hidden');
    setTimeout(() => document.getElementById('file-name').focus(), 100);
}

function closeFileModal() {
    document.getElementById('file-modal').classList.add('hidden');
    FileState.editingFileId = null;
}

async function handleFileSubmit(e) {
    e.preventDefault();

    const filename = document.getElementById('file-name').value.trim();
    const content = document.getElementById('file-content').value;
    const isEdit = FileState.editingFileId !== null;

    if (!filename || !content) {
        showNotification('Filename and content are required', 'error');
        return;
    }

    try {
        if (isEdit) {
            await api.put(`/vendor/api/v1/findrive/${FileState.editingFileId}`, {
                filename, content,
            });
            showNotification('File updated', 'success');
        } else {
            await api.post('/vendor/api/v1/findrive', {
                filename, content, folder: '/invoices',
            });
            showNotification('File created', 'success');
        }

        closeFileModal();
        await loadFiles();
    } catch (error) {
        console.error('Error saving file:', error);
        handleAPIError(error, { showAlert: true });
    }
}

function initializeFileViewModal() {
    const modal = document.getElementById('file-view-modal');
    const closeBtn = document.getElementById('close-file-view-btn');

    if (!modal) return;
    if (closeBtn) closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.add('hidden'); });
}

async function viewFile(fileId) {
    try {
        const response = await api.get(`/vendor/api/v1/findrive/${fileId}`);
        const data = response.data || response;
        const file = data.file;

        document.getElementById('file-view-title').textContent = file.filename;
        document.getElementById('file-view-content').textContent = file.content_text;
        document.getElementById('file-view-modal').classList.remove('hidden');
    } catch (error) {
        console.error('Error viewing file:', error);
        showNotification('Failed to load file', 'error');
    }
}

async function editFile(fileId) {
    try {
        const response = await api.get(`/vendor/api/v1/findrive/${fileId}`);
        const data = response.data || response;
        openFileModal(data.file);
    } catch (error) {
        console.error('Error loading file for edit:', error);
        showNotification('Failed to load file', 'error');
    }
}

async function deleteFile(fileId) {
    const confirmed = await showConfirmModal({
        title: 'Delete Document',
        message: 'This document will be permanently removed. This action cannot be undone.',
        confirmText: 'Delete',
        danger: true,
    });
    if (!confirmed) return;

    try {
        await api.delete(`/vendor/api/v1/findrive/${fileId}`);
        showNotification('File deleted', 'success');
        await loadFiles();
    } catch (error) {
        console.error('Error deleting file:', error);
        handleAPIError(error, { showAlert: true });
    }
}

function escFileHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
