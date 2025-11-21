


let currentSources = [];
let filteredSources = [];
let currentPage = 1;
const itemsPerPage = 10;
let searchDebounceTimer = null;


const API_BASE = '/knowledge';





function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncate(text, maxLength) {
    if (!text) return '-';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
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
    } catch (error) {
        return '-';
    }
}

function showLoading() {
    document.getElementById('loading').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading').classList.add('hidden');
}

function showMessage(message, type = 'info') {
    const container = document.getElementById('message-container');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.textContent = message;
    
    container.appendChild(messageDiv);
    
    
    setTimeout(() => {
        messageDiv.style.opacity = '0';
        messageDiv.style.transform = 'translateX(100%)';
        setTimeout(() => messageDiv.remove(), 300);
    }, 5000);
}

function showError(message) {
    showMessage(message, 'error');
}

function showSuccess(message) {
    showMessage(message, 'success');
}





async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        if (!response.ok) {
            let errorMessage = `API Error: ${response.status}`;
            try {
                const error = await response.json();
                errorMessage = error.detail || errorMessage;
            } catch (e) {
                
            }
            throw new Error(errorMessage);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}





function calculateStatistics(sources) {
    const stats = {
        totalSources: sources.length,
        totalChunks: 0,
        byCategory: {},
        byType: {},
        byContentSource: { internal: 0, external: 0 },
        lastSync: null
    };
    
    sources.forEach(source => {
        
        stats.totalChunks += source.total_chunks || 0;
        
        
        const category = source.category || 'Uncategorized';
        if (!stats.byCategory[category]) {
            stats.byCategory[category] = { count: 0, chunks: 0 };
        }
        stats.byCategory[category].count++;
        stats.byCategory[category].chunks += source.total_chunks || 0;
        
        
        const type = source.type || 'Unknown';
        stats.byType[type] = (stats.byType[type] || 0) + 1;
        
        
        if (source.content_source === 'internal') {
            stats.byContentSource.internal++;
        } else {
            stats.byContentSource.external++;
        }
        
        
        if (source.last_sync) {
            const syncDate = new Date(source.last_sync);
            if (!stats.lastSync || syncDate > stats.lastSync) {
                stats.lastSync = syncDate;
            }
        }
    });
    
    return stats;
}

function renderStatistics(stats) {
    
    document.getElementById('stat-total-sources').textContent = stats.totalSources;
    document.getElementById('stat-total-chunks').textContent = stats.totalChunks.toLocaleString();
    document.getElementById('stat-internal-sources').textContent = stats.byContentSource.internal;
    document.getElementById('stat-external-sources').textContent = stats.byContentSource.external;
    
    
    const categoryContainer = document.getElementById('category-breakdown');
    if (Object.keys(stats.byCategory).length === 0) {
        categoryContainer.innerHTML = '<p class="empty-state">No categories found</p>';
    } else {
        categoryContainer.innerHTML = Object.entries(stats.byCategory)
            .sort(([, a], [, b]) => b.chunks - a.chunks)
            .map(([category, data]) => `
                <div class="breakdown-item">
                    <span class="label">${escapeHtml(category)}</span>
                    <span class="value">${data.count} sources, ${data.chunks.toLocaleString()} chunks</span>
                </div>
            `).join('');
    }
    
    
    const typeContainer = document.getElementById('type-breakdown');
    if (Object.keys(stats.byType).length === 0) {
        typeContainer.innerHTML = '<p class="empty-state">No types found</p>';
    } else {
        typeContainer.innerHTML = Object.entries(stats.byType)
            .sort(([, a], [, b]) => b - a)
            .map(([type, count]) => `
                <div class="breakdown-item">
                    <span class="label">${escapeHtml(type)}</span>
                    <span class="value">${count} sources</span>
                </div>
            `).join('');
    }
    
    
    const lastSyncContainer = document.getElementById('last-sync-info');
    if (stats.lastSync) {
        lastSyncContainer.innerHTML = `
            <div class="breakdown-item">
                <span class="label">Most Recent Sync</span>
                <span class="value">${formatDate(stats.lastSync)}</span>
            </div>
        `;
    } else {
        lastSyncContainer.innerHTML = '<p class="empty-state">No sync activity recorded</p>';
    }
}

async function loadStatistics() {
    try {
        if (currentSources.length === 0) {
            const data = await apiCall(`${API_BASE}/sources`);
            currentSources = data.sources || [];
        }
        
        const stats = calculateStatistics(currentSources);
        renderStatistics(stats);
    } catch (error) {
        showError(`Failed to load statistics: ${error.message}`);
        console.error('Statistics error:', error);
    }
}





function renderComparison(data) {
    
    document.getElementById('comp-kb-total').textContent = data.kb_sources.total;
    document.getElementById('comp-kb-internal').textContent = data.kb_sources.internal;
    document.getElementById('comp-kb-external').textContent = data.kb_sources.external;
    document.getElementById('comp-kb-chunks').textContent = data.kb_sources.total_chunks.toLocaleString();
    
    
    document.getElementById('comp-db-total').textContent = data.db_sources.total;
    document.getElementById('comp-db-enabled').textContent = data.db_sources.enabled;
    document.getElementById('comp-db-disabled').textContent = data.db_sources.disabled;
    
    
    document.getElementById('comp-in-both').textContent = data.comparison.in_both;
    document.getElementById('comp-only-kb').textContent = data.comparison.only_in_kb;
    document.getElementById('comp-only-db').textContent = data.comparison.only_in_db;
    document.getElementById('comp-missing').textContent = data.comparison.missing_from_kb_but_enabled;
    
    
    const missingDetails = document.getElementById('missing-sources-details');
    const missingList = document.getElementById('missing-sources-list');
    if (data.details.missing_from_kb_but_enabled.length > 0) {
        missingDetails.style.display = 'block';
        missingList.innerHTML = data.details.missing_from_kb_but_enabled.map(item => `
            <li>
                <strong>${escapeHtml(item.name || 'Unnamed')}</strong><br>
                <a href="${escapeHtml(item.url)}" target="_blank">${escapeHtml(item.url)}</a>
            </li>
        `).join('');
    } else {
        missingDetails.style.display = 'none';
    }
    
    
    const onlyKbDetails = document.getElementById('only-kb-details');
    const onlyKbList = document.getElementById('only-kb-list');
    if (data.details.only_in_kb.length > 0) {
        onlyKbDetails.style.display = 'block';
        onlyKbList.innerHTML = data.details.only_in_kb.map(item => `
            <li>
                <strong>${escapeHtml(item.name || 'Unnamed')}</strong><br>
                <a href="${escapeHtml(item.url)}" target="_blank">${escapeHtml(item.url)}</a>
            </li>
        `).join('');
    } else {
        onlyKbDetails.style.display = 'none';
    }
    
    
    const onlyDbDetails = document.getElementById('only-db-details');
    const onlyDbList = document.getElementById('only-db-list');
    if (data.details.only_in_db.length > 0) {
        onlyDbDetails.style.display = 'block';
        onlyDbList.innerHTML = data.details.only_in_db.map(item => `
            <li>
                <strong>${escapeHtml(item.name || 'Unnamed')}</strong><br>
                <a href="${escapeHtml(item.url)}" target="_blank">${escapeHtml(item.url)}</a>
            </li>
        `).join('');
    } else {
        onlyDbDetails.style.display = 'none';
    }
}

async function loadComparison() {
    try {
        const data = await apiCall(`${API_BASE}/sources/comparison`);
        renderComparison(data);
    } catch (error) {
        console.error('Failed to load comparison:', error);
        
    }
}





function applySearchFilter() {
    const searchInput = document.getElementById('search-input');
    const clearBtn = document.getElementById('clear-search-btn');
    const searchTerm = searchInput.value.trim().toLowerCase();
    
    if (searchTerm === '') {
        filteredSources = [...currentSources];
        clearBtn.style.display = 'none';
    } else {
        filteredSources = currentSources.filter(source => 
            source.url.toLowerCase().includes(searchTerm)
        );
        clearBtn.style.display = 'inline-block';
    }
    
    currentPage = 1;
    renderCurrentPage();
}

function clearSearch() {
    const searchInput = document.getElementById('search-input');
    const clearBtn = document.getElementById('clear-search-btn');
    
    searchInput.value = '';
    clearBtn.style.display = 'none';
    filteredSources = [...currentSources];
    currentPage = 1;
    renderCurrentPage();
}

function renderSourcesTable(sources) {
    const tbody = document.getElementById('sources-tbody');
    
    if (sources.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No sources found</td></tr>';
        return;
    }
    
    tbody.innerHTML = sources.map(source => `
        <tr>
            <td>${escapeHtml(source.name)}</td>
            <td>
                <a href="${escapeHtml(source.url)}" target="_blank" title="${escapeHtml(source.url)}">
                    ${truncate(source.url, 40)}
                </a>
            </td>
            <td>${escapeHtml(source.type || '-')}</td>
            <td>${escapeHtml(source.category || '-')}</td>
            <td>
                <span class="truncate" title="${escapeHtml(source.description || '')}">
                    ${truncate(source.description, 50)}
                </span>
            </td>
            <td>
                <span class="badge">${source.total_chunks || 0}</span>
            </td>
            <td>${formatDate(source.last_sync)}</td>
            <td class="actions">
                <button class="btn btn-view" onclick="viewChunks('${escapeHtml(source.id)}', '${escapeHtml(source.name)}')">
                    🔍 View
                </button>
                <button class="btn btn-delete" onclick="deleteSourceVectors('${escapeHtml(source.id)}', '${escapeHtml(source.name)}')">
                    🗑️ Delete
                </button>
                <button class="btn btn-resync" onclick="resyncSource('${escapeHtml(source.id)}', '${escapeHtml(source.url)}', '${escapeHtml(source.name)}', '${escapeHtml(source.type || '')}', '${escapeHtml(source.category || '')}', '${escapeHtml(source.description || '')}')">
                    🔄 Resync
                </button>
            </td>
        </tr>
    `).join('');
}

function renderCurrentPage() {
    const totalPages = Math.ceil(filteredSources.length / itemsPerPage);
    
    if (currentPage < 1) currentPage = 1;
    if (currentPage > totalPages && totalPages > 0) currentPage = totalPages;
    
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = Math.min(startIndex + itemsPerPage, filteredSources.length);
    const pageItems = filteredSources.slice(startIndex, endIndex);
    
    renderSourcesTable(pageItems);
    updatePaginationInfo();
}

function updatePaginationInfo() {
    const totalPages = Math.ceil(filteredSources.length / itemsPerPage);
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = Math.min(startIndex + itemsPerPage, filteredSources.length);
    
    document.getElementById('showing-start').textContent = filteredSources.length > 0 ? startIndex + 1 : 0;
    document.getElementById('showing-end').textContent = endIndex;
    document.getElementById('total-filtered').textContent = filteredSources.length;
    document.getElementById('current-page').textContent = totalPages > 0 ? currentPage : 0;
    document.getElementById('total-pages').textContent = totalPages;
    
    const prevBtn = document.getElementById('prev-page-btn');
    const nextBtn = document.getElementById('next-page-btn');
    
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
}

function goToPreviousPage() {
    if (currentPage > 1) {
        currentPage--;
        renderCurrentPage();
    }
}

function goToNextPage() {
    const totalPages = Math.ceil(filteredSources.length / itemsPerPage);
    if (currentPage < totalPages) {
        currentPage++;
        renderCurrentPage();
    }
}

async function loadSources() {
    try {
        showLoading();
        const data = await apiCall(`${API_BASE}/sources`);
        currentSources = data.sources || [];
        filteredSources = [...currentSources];
        currentPage = 1;
        renderCurrentPage();
    } catch (error) {
        showError(`Failed to load sources: ${error.message}`);
        console.error('Load sources error:', error);
    } finally {
        hideLoading();
    }
}





function viewChunks(sourceId, sourceName) {
    
    const encodedName = encodeURIComponent(sourceName);
    window.location.href = `./source-detail.html?id=${sourceId}&name=${encodedName}`;
}





async function deleteSourceVectors(sourceId, sourceName) {
    const confirmed = confirm(
        `Are you sure you want to delete all vectors for "${sourceName}"?\n\n` +
        `This will remove all ${currentSources.find(s => s.id === sourceId)?.total_chunks || 0} chunks.\n\n` +
        `This action cannot be undone.`
    );
    
    if (!confirmed) return;
    
    try {
        showLoading();
        const result = await apiCall(`${API_BASE}/sources/${sourceId}`, {
            method: 'DELETE'
        });
        
        if (result.success) {
            showSuccess(`Successfully deleted ${result.vectors_deleted} vectors for "${sourceName}"`);
            
            
            const chunkSection = document.getElementById('chunk-details-section');
            if (!chunkSection.classList.contains('hidden')) {
                closeChunkDetails();
            }
            
            
            await loadSources();
            await loadStatistics();
        } else {
            showError(`Delete failed: ${result.error || result.message}`);
        }
    } catch (error) {
        showError(`Failed to delete vectors: ${error.message}`);
        console.error('Delete error:', error);
    } finally {
        hideLoading();
    }
}





async function resyncSource(sourceId, sourceUrl, sourceName, sourceType, sourceCategory, sourceDescription) {
    const confirmed = confirm(
        `Re-sync source "${sourceName}"?\n\n` +
        `URL: ${sourceUrl}\n\n` +
        `This will crawl the source and update all chunks.`
    );
    
    if (!confirmed) return;
    
    try {
        showLoading();
        showMessage(`Re-syncing "${sourceName}"... This may take a while.`, 'info');
        
        const requestBody = {
            url: sourceUrl,
            name: sourceName
        };
        
        
        if (sourceType) requestBody.type = sourceType;
        if (sourceCategory) requestBody.category = sourceCategory;
        if (sourceDescription) requestBody.description = sourceDescription;
        
        const result = await apiCall(`${API_BASE}/sync-source`, {
            method: 'POST',
            body: JSON.stringify(requestBody)
        });
        
        if (result.success) {
            const message = result.content_changed 
                ? `Successfully re-synced "${sourceName}": ${result.documents_added} chunks added in ${result.processing_time_seconds}s`
                : `Re-sync completed for "${sourceName}": No changes detected`;
            showSuccess(message);
            
            
            await loadSources();
            await loadStatistics();
        } else {
            showError(`Re-sync failed: ${result.error || result.message}`);
        }
    } catch (error) {
        showError(`Failed to re-sync source: ${error.message}`);
        console.error('Resync error:', error);
    } finally {
        hideLoading();
    }
}





document.addEventListener('DOMContentLoaded', async () => {
    console.log('Knowledge Base Admin initialized');
    
    
    const searchInput = document.getElementById('search-input');
    searchInput.addEventListener('input', () => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(applySearchFilter, 300);
    });
    
    
    document.getElementById('clear-search-btn').addEventListener('click', clearSearch);
    
    
    document.getElementById('prev-page-btn').addEventListener('click', goToPreviousPage);
    document.getElementById('next-page-btn').addEventListener('click', goToNextPage);
    
    
    await loadSources();
    await loadStatistics();
    await loadComparison();
});
