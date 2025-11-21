


const API_BASE = '/knowledge';


let sourceData = null;
let allChunks = [];
let filteredChunks = [];
let searchDebounceTimer = null;





function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return '-';
    try {
        const date = new Date(dateString);
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return dateString;
    }
}

function getUrlParams() {
    const params = new URLSearchParams(window.location.search);
    return {
        sourceId: params.get('id'),
        sourceName: params.get('name')
    };
}

function showLoading() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('content').style.display = 'none';
    document.getElementById('error-message').style.display = 'none';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

function showError(message) {
    const errorEl = document.getElementById('error-message');
    errorEl.textContent = message;
    errorEl.style.display = 'block';
    document.getElementById('content').style.display = 'none';
}

function showContent() {
    document.getElementById('content').style.display = 'block';
    document.getElementById('error-message').style.display = 'none';
}





async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, options);
        
        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.detail || errorData.message || errorMessage;
            } catch (e) {
                errorMessage = await response.text() || errorMessage;
            }
            throw new Error(errorMessage);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

async function loadSourceData(sourceId) {
    try {
        showLoading();
        const data = await apiCall(`${API_BASE}/sources/${sourceId}`);
        return data;
    } catch (error) {
        throw new Error(`Failed to load source data: ${error.message}`);
    } finally {
        hideLoading();
    }
}

async function deleteSource(sourceId, sourceName) {
    if (!confirm(`Are you sure you want to delete all vectors for "${sourceName}"? This action cannot be undone.`)) {
        return;
    }

    try {
        showLoading();
        await apiCall(`${API_BASE}/sources/${sourceId}`, { method: 'DELETE' });
        alert('Vectors deleted successfully. Redirecting to main page...');
        window.location.href = './index.html';
    } catch (error) {
        hideLoading();
        alert(`Failed to delete vectors: ${error.message}`);
    }
}

async function resyncSource(sourceId, sourceUrl, sourceName, sourceType, sourceCategory, sourceDescription) {
    if (!confirm(`Re-sync source "${sourceName}"? This will re-crawl and update all chunks.`)) {
        return;
    }

    try {
        showLoading();
        const payload = {
            url: sourceUrl,
            name: sourceName,
            type: sourceType || '',
            category: sourceCategory || '',
            description: sourceDescription || ''
        };

        const result = await apiCall(`${API_BASE}/sync-source`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (result.success) {
            alert('Re-sync completed successfully!');
            window.location.reload();
        } else {
            throw new Error(result.error || result.message || 'Unknown error');
        }
    } catch (error) {
        hideLoading();
        alert(`Failed to re-sync source: ${error.message}`);
    }
}





function renderSourceMetadata(source) {
    document.getElementById('source-name').textContent = source.name || '-';
    
    const urlEl = document.getElementById('source-url');
    urlEl.textContent = source.url || '-';
    urlEl.href = source.url || '#';
    
    document.getElementById('source-type').textContent = source.type || '-';
    document.getElementById('source-category').textContent = source.category || '-';
    document.getElementById('source-content-source').textContent = source.content_source || '-';
    document.getElementById('source-total-chunks').textContent = source.total_chunks || 0;
    document.getElementById('source-last-sync').textContent = formatDate(source.last_sync);
    document.getElementById('source-description').textContent = source.description || 'No description available.';

    
    document.title = `${source.name} - Source Details`;
}

function renderChunks(chunks) {
    const container = document.getElementById('chunks-container');
    const noChunks = document.getElementById('no-chunks');
    const countEl = document.getElementById('chunks-count');

    countEl.textContent = chunks.length;

    if (chunks.length === 0) {
        container.style.display = 'none';
        noChunks.style.display = 'block';
        return;
    }

    container.style.display = 'flex';
    noChunks.style.display = 'none';

    container.innerHTML = chunks.map((chunk, index) => {
        const metadata = chunk.metadata || {};
        const metadataEntries = Object.entries(metadata).filter(([key]) => 
            !['source_id', 'chunk_index'].includes(key)
        );

        return `
            <div class="chunk-card">
                <div class="chunk-header">
                    <div class="chunk-title">
                        Chunk #${chunk.chunk_index ?? index + 1}
                    </div>
                    <div class="chunk-meta">
                        <span class="chunk-meta-item">
                            <span class="icon">📄</span>
                            ${chunk.content?.length || 0} characters
                        </span>
                        ${chunk.chunk_index !== undefined ? `
                            <span class="chunk-meta-item">
                                <span class="icon">#</span>
                                Index: ${chunk.chunk_index}
                            </span>
                        ` : ''}
                    </div>
                </div>
                
                <div class="chunk-content">
                    <div class="chunk-text">${escapeHtml(chunk.content || 'No content')}</div>
                </div>

                ${metadataEntries.length > 0 ? `
                    <div class="chunk-metadata-section">
                        <div class="chunk-metadata-title">Additional Metadata</div>
                        <div class="chunk-metadata-grid">
                            ${metadataEntries.map(([key, value]) => `
                                <div class="chunk-metadata-item">
                                    <span class="key">${escapeHtml(key)}:</span>
                                    <span class="value">${escapeHtml(String(value))}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}





function applyFiltersAndSort() {
    const searchTerm = document.getElementById('chunk-search').value.toLowerCase().trim();
    const sortOption = document.getElementById('chunk-sort').value;

    
    filteredChunks = searchTerm === '' 
        ? [...allChunks]
        : allChunks.filter(chunk => 
            chunk.content?.toLowerCase().includes(searchTerm)
        );

    
    switch (sortOption) {
        case 'index-asc':
            filteredChunks.sort((a, b) => (a.chunk_index ?? 0) - (b.chunk_index ?? 0));
            break;
        case 'index-desc':
            filteredChunks.sort((a, b) => (b.chunk_index ?? 0) - (a.chunk_index ?? 0));
            break;
        case 'length-desc':
            filteredChunks.sort((a, b) => (b.content?.length ?? 0) - (a.content?.length ?? 0));
            break;
        case 'length-asc':
            filteredChunks.sort((a, b) => (a.content?.length ?? 0) - (b.content?.length ?? 0));
            break;
    }

    renderChunks(filteredChunks);
}

function handleSearchInput() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(applyFiltersAndSort, 300);
}





document.addEventListener('DOMContentLoaded', async () => {
    const { sourceId, sourceName } = getUrlParams();

    if (!sourceId) {
        showError('No source ID provided. Please navigate from the main sources page.');
        return;
    }

    
    document.getElementById('back-btn').addEventListener('click', () => {
        window.location.href = './index.html';
    });

    
    document.getElementById('delete-btn').addEventListener('click', async () => {
        await deleteSource(sourceId, sourceName || 'this source');
    });

    document.getElementById('resync-btn').addEventListener('click', async () => {
        if (sourceData) {
            await resyncSource(
                sourceId,
                sourceData.url,
                sourceData.name,
                sourceData.type,
                sourceData.category,
                sourceData.description
            );
        }
    });

    
    document.getElementById('chunk-search').addEventListener('input', handleSearchInput);
    document.getElementById('chunk-sort').addEventListener('change', applyFiltersAndSort);

    
    try {
        const response = await loadSourceData(sourceId);
        
        
        sourceData = response.source;
        allChunks = response.chunks || [];
        filteredChunks = [...allChunks];

        renderSourceMetadata(sourceData);
        applyFiltersAndSort();
        showContent();
    } catch (error) {
        showError(error.message);
        console.error('Failed to load source:', error);
    }
});
