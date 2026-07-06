/**
 * API Wrapper for standardizing fetch requests, error handling, and toast notifications.
 */

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

window.api = {
    async fetch(url, options = {}) {
        const { 
            showErrorToast = true, 
            timeout = 10000, 
            loadingMessage = null,
            successMessage = null 
        } = options;

        const csrfToken = getCookie('csrftoken');
        const headers = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            ...options.headers
        };

        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        const fetchOptions = {
            ...options,
            headers,
            signal: controller.signal
        };

        let toastId = null;
        if (loadingMessage && window.toast) {
            toastId = window.toast.loading(loadingMessage);
        }

        try {
            const response = await fetch(url, fetchOptions);
            clearTimeout(timeoutId);

            // Handle non-2xx responses
            if (!response.ok) {
                let errorMessage = 'An unexpected error occurred.';
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorData.error || errorData.message || errorMessage;
                    
                    // Specific status code handling
                    if (response.status === 401) {
                        errorMessage = 'Your session has expired. Please log in again.';
                        setTimeout(() => window.location.href = '/accounts/login/?next=' + encodeURIComponent(window.location.pathname), 1500);
                    } else if (response.status === 403) {
                        errorMessage = 'You do not have permission to perform this action.';
                    } else if (response.status === 404) {
                        errorMessage = 'The requested resource was not found.';
                    } else if (response.status >= 500) {
                        errorMessage = 'Server error. Our team has been notified.';
                    }
                } catch (e) {
                    // Not JSON
                    if (response.status === 401) {
                        errorMessage = 'Your session has expired. Please log in again.';
                        setTimeout(() => window.location.href = '/accounts/login/?next=' + encodeURIComponent(window.location.pathname), 1500);
                    } else if (response.status >= 500) {
                        errorMessage = 'Server error. Our team has been notified.';
                    } else {
                        errorMessage = `Error: ${response.status} ${response.statusText}`;
                    }
                }

                throw new Error(errorMessage);
            }

            // Parse success response
            const data = await response.json();
            
            if (toastId && window.toast) window.toast.remove(toastId);
            if (successMessage && window.toast) window.toast.success(successMessage);

            return data;

        } catch (error) {
            clearTimeout(timeoutId);
            if (toastId && window.toast) window.toast.remove(toastId);

            let displayMessage = error.message;

            if (error.name === 'AbortError') {
                displayMessage = 'Request timed out. Please check your connection and try again.';
            } else if (!window.navigator.onLine) {
                displayMessage = 'You are currently offline. Please reconnect to the internet.';
            }

            if (showErrorToast && window.toast) {
                window.toast.error(displayMessage);
            }

            throw new Error(displayMessage);
        }
    },

    get(url, options = {}) {
        return this.fetch(url, { ...options, method: 'GET' });
    },

    post(url, data, options = {}) {
        return this.fetch(url, { ...options, method: 'POST', body: JSON.stringify(data) });
    },

    put(url, data, options = {}) {
        return this.fetch(url, { ...options, method: 'PUT', body: JSON.stringify(data) });
    },

    delete(url, options = {}) {
        return this.fetch(url, { ...options, method: 'DELETE' });
    }
};
