/**
 * SQL Converter - Main JavaScript functionality
 */

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Common elements
    const loadingOverlay = document.getElementById('loading-overlay');
    
    // Initialize page: Hide loading overlay
    if (loadingOverlay) {
        loadingOverlay.classList.remove('active');
    }
    
    // Initialize the appropriate page functionality
    if (document.getElementById('defaultOpen')) {
        initializeIndexPage();
    } else if (document.getElementById('columnForm')) {
        initializeColumnSelectPage();
    } else if (document.querySelector('.error-container')) {
        // Nothing special for error page
    }
});

/**
 * Initialize functionality for the main index page
 */
function initializeIndexPage() {
    // Get the element with id="defaultOpen" and click on it
    document.getElementById('defaultOpen').click();
    
    // Handle form submissions on index page
    const forms = document.querySelectorAll('form:not(#directConvertForm)');
    const loadingOverlay = document.getElementById('loading-overlay');
    
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            // Make sure file is selected
            const fileInput = this.querySelector('input[type="file"]');
            if (fileInput && fileInput.files.length > 0) {
                loadingOverlay.classList.add('active');
                
                // Safety timeout - hide loading after 30 seconds if still showing
                setTimeout(function() {
                    loadingOverlay.classList.remove('active');
                }, 30000);
            }
        });
    });
    
    // Initialize drag and drop functionality
    initializeDragAndDrop();
    
    // Handle direct convert form with AJAX
    const directConvertForm = document.getElementById('directConvertForm');
    const directConvertBtn = document.getElementById('directConvertBtn');
    
    if (directConvertForm && directConvertBtn) {
        directConvertBtn.addEventListener('click', function(e) {
            e.preventDefault(); // Prevent default form submission
            
            // Make sure file is selected
            const fileInput = directConvertForm.querySelector('input[type="file"]');
            if (fileInput && fileInput.files.length > 0) {
                // Show loading
                loadingOverlay.classList.add('active');
                
                // Submit the form
                const formData = new FormData(directConvertForm);
                
                // Create an XHR request for the download
                const xhr = new XMLHttpRequest();
                xhr.open('POST', directConvertForm.action, true);
                xhr.responseType = 'blob'; // Important for file downloads
                
                // When the request completes
                xhr.onload = function() {
                    // Hide loading overlay
                    loadingOverlay.classList.remove('active');
                    
                    if (xhr.status === 200) {
                        // Create a download link
                        const blob = xhr.response;
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        
                        // Try to get filename from response headers
                        let filename = '';
                        const disposition = xhr.getResponseHeader('Content-Disposition');
                        
                        if (disposition && disposition.indexOf('attachment') !== -1) {
                            const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                            const matches = filenameRegex.exec(disposition);
                            if (matches != null && matches[1]) {
                                filename = matches[1].replace(/['"]/g, '');
                            }
                        }
                        
                        // Use a default filename if not found in headers
                        if (!filename) {
                            filename = "php_array.php";
                        }
                        
                        a.href = url;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(url);
                        document.body.removeChild(a);
                    } else {
                        // Handle error
                        alert('An error occurred while generating the file.');
                    }
                };
                
                // Handle network errors
                xhr.onerror = function() {
                    loadingOverlay.classList.remove('active');
                    alert('Network error occurred while trying to generate the file.');
                };
                
                // Send the form data
                xhr.send(formData);
            } else {
                // Show alert if no file selected
                alert('Please select a SQL file before converting.');
            }
        });
    }
    
    // Handle back button navigation
    window.addEventListener('pageshow', function(event) {
        // When navigating back, pageshow fires and persisted property 
        // indicates if page is from cache
        if (event.persisted && loadingOverlay) {
            loadingOverlay.classList.remove('active');
        }
    });
}

/**
 * Initialize drag and drop functionality for file uploads
 */
function initializeDragAndDrop() {
    // Find all file upload areas
    const fileUploads = document.querySelectorAll('.file-upload');
    
    fileUploads.forEach(upload => {
        const fileInput = upload.querySelector('input[type="file"]');
        if (!fileInput) return;
        
        // Create drop zone element
        const dropZone = document.createElement('div');
        dropZone.className = 'drop-zone';
        dropZone.innerHTML = `
            <div class="drop-zone-prompt">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="17 8 12 3 7 8"></polyline>
                    <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
                <span>Drag & drop your SQL file here or click to browse</span>
            </div>
            <div class="drop-zone-thumb" hidden></div>
        `;
        
        // Insert drop zone after the label
        const label = upload.querySelector('label');
        if (label && label.nextSibling) {
            upload.insertBefore(dropZone, label.nextSibling);
        } else {
            upload.appendChild(dropZone);
        }
        
        // Hide the original file input
        fileInput.style.display = 'none';
        
        // Click handler for the drop zone
        dropZone.addEventListener('click', function() {
            fileInput.click();
        });
        
        // Change handler for the file input
        fileInput.addEventListener('change', function() {
            updateThumbnail(dropZone, fileInput.files[0]);
        });
        
        // Drag and drop handlers
        dropZone.addEventListener('dragover', function(e) {
            e.preventDefault();
            dropZone.classList.add('drop-zone-over');
        });
        
        ['dragleave', 'dragend'].forEach(type => {
            dropZone.addEventListener(type, function() {
                dropZone.classList.remove('drop-zone-over');
            });
        });
        
        dropZone.addEventListener('drop', function(e) {
            e.preventDefault();
            
            if (e.dataTransfer.files.length) {
                // Set the file to the file input
                fileInput.files = e.dataTransfer.files;
                updateThumbnail(dropZone, e.dataTransfer.files[0]);
            }
            
            dropZone.classList.remove('drop-zone-over');
        });
    });
}

/**
 * Update the drop zone thumbnail with file information
 */
function updateThumbnail(dropZone, file) {
    // Remove any previous thumbnail
    let thumbnailElement = dropZone.querySelector('.drop-zone-thumb');
    
    // First time - remove prompt, show thumbnail
    if (thumbnailElement.hasAttribute('hidden')) {
        thumbnailElement.removeAttribute('hidden');
        dropZone.querySelector('.drop-zone-prompt').setAttribute('hidden', true);
    }
    
    // Check if it's a SQL file
    if (!file.name.toLowerCase().endsWith('.sql')) {
        thumbnailElement.innerHTML = `
            <div class="file-error">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <span>Invalid file type. Please select a .sql file.</span>
            </div>
        `;
        return;
    }
    
    // Set the filename as caption
    thumbnailElement.innerHTML = `
        <div class="file-info">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
                <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <span>${file.name}</span>
            <span class="file-size">${formatFileSize(file.size)}</span>
        </div>
    `;
    
    // Show file preview (if it's a small SQL file)
    if (file.size < 100000) { // Less than 100KB
        const reader = new FileReader();
        
        reader.onload = function() {
            const preview = document.createElement('div');
            preview.className = 'file-preview';
            preview.innerHTML = `
                <div class="preview-header">File Preview:</div>
                <pre>${reader.result.slice(0, 500)}${reader.result.length > 500 ? '...' : ''}</pre>
            `;
            
            thumbnailElement.appendChild(preview);
        };
        
        reader.readAsText(file);
    }
}

/**
 * Format file size in human-readable format
 */
function formatFileSize(bytes) {
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    
    return size.toFixed(1) + ' ' + units[unitIndex];
}

/**
 * Tab functionality for the index page
 */
function openTab(evt, tabName) {
    var i, tabcontent, tablinks;
    tabcontent = document.getElementsByClassName("tabcontent");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].style.display = "none";
    }
    tablinks = document.getElementsByClassName("tablinks");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].className = tablinks[i].className.replace(" active", "");
    }
    document.getElementById(tabName).style.display = "block";
    evt.currentTarget.className += " active";
    
    // Update ARIA attributes
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].setAttribute('aria-selected', 'false');
    }
    evt.currentTarget.setAttribute('aria-selected', 'true');
}

/**
 * Initialize functionality for the column selection page
 */
function initializeColumnSelectPage() {
    // Set up table-specific select/deselect
    document.querySelectorAll('.select-all-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const table = this.getAttribute('data-table');
            document.querySelectorAll(`.column-checkbox[data-table="${table}"]`).forEach(checkbox => {
                checkbox.checked = true;
            });
        });
    });
    
    document.querySelectorAll('.deselect-all-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const table = this.getAttribute('data-table');
            document.querySelectorAll(`.column-checkbox[data-table="${table}"]`).forEach(checkbox => {
                checkbox.checked = false;
            });
        });
    });
    
    // Global select/deselect
    const selectAllBtn = document.getElementById('select-all');
    const deselectAllBtn = document.getElementById('deselect-all');
    
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', function() {
            document.querySelectorAll('.column-checkbox').forEach(checkbox => {
                checkbox.checked = true;
            });
        });
    }
    
    if (deselectAllBtn) {
        deselectAllBtn.addEventListener('click', function() {
            document.querySelectorAll('.column-checkbox').forEach(checkbox => {
                checkbox.checked = false;
            });
        });
    }
    
    // Set up form submission with Ajax
    const form = document.getElementById('columnForm');
    const submitBtn = document.getElementById('submitBtn');
    const loadingOverlay = document.getElementById('loading-overlay');
    
    if (form && submitBtn) {
        submitBtn.addEventListener('click', function(e) {
            e.preventDefault(); // Prevent default form submission
            
            // Show loading
            loadingOverlay.classList.add('active');
            
            // Submit the form
            const formData = new FormData(form);
            
            // Create an XHR request for the download
            const xhr = new XMLHttpRequest();
            xhr.open('POST', form.action, true);
            xhr.responseType = 'blob'; // Important for file downloads
            
            // When the request completes
            xhr.onload = function() {
                // Hide loading overlay
                loadingOverlay.classList.remove('active');
                
                if (xhr.status === 200) {
                    // Create a download link
                    const blob = xhr.response;
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    
                    // Try to get filename from response headers
                    let filename = '';
                    const disposition = xhr.getResponseHeader('Content-Disposition');
                    
                    if (disposition && disposition.indexOf('attachment') !== -1) {
                        const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
                        const matches = filenameRegex.exec(disposition);
                        if (matches != null && matches[1]) {
                            filename = matches[1].replace(/['"]/g, '');
                        }
                    }
                    
                    // Use a default filename if not found in headers
                    if (!filename) {
                        filename = "php_array.php";
                    }
                    
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                } else {
                    // Handle error
                    alert('An error occurred while generating the file.');
                }
            };
            
            // Handle network errors
            xhr.onerror = function() {
                loadingOverlay.classList.remove('active');
                alert('Network error occurred while trying to generate the file.');
            };
            
            // Send the form data
            xhr.send(formData);
        });
    }
}