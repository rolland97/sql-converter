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