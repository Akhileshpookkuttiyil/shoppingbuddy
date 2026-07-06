document.addEventListener('alpine:init', () => {
    Alpine.store('toasts', {
        list: [],
        counter: 0,
        
        add(message, type = 'info', options = {}) {
            const id = this.counter++;
            const toast = {
                id,
                message,
                type,
                duration: options.duration !== undefined ? options.duration : 5000,
            };
            
            // Prevent duplicates if same message exists
            if (this.list.some(t => t.message === message && t.type === type)) {
                return id;
            }
            
            this.list.push(toast);
            
            if (toast.duration > 0) {
                setTimeout(() => {
                    this.remove(id);
                }, toast.duration);
            }
            return id;
        },
        
        remove(id) {
            this.list = this.list.filter(toast => toast.id !== id);
        }
    });
});

window.toast = {
    success: (msg, opts) => Alpine.store('toasts').add(msg, 'success', opts),
    error: (msg, opts) => Alpine.store('toasts').add(msg, 'error', opts),
    warning: (msg, opts) => Alpine.store('toasts').add(msg, 'warning', opts),
    info: (msg, opts) => Alpine.store('toasts').add(msg, 'info', opts),
    loading: (msg, opts) => Alpine.store('toasts').add(msg, 'loading', { ...opts, duration: 0 }),
    remove: (id) => Alpine.store('toasts').remove(id),
    promise: async (promise, msgs) => {
        const id = window.toast.loading(msgs.loading || 'Loading...');
        try {
            const res = await promise;
            window.toast.remove(id);
            if (msgs.success) window.toast.success(msgs.success);
            return res;
        } catch (err) {
            window.toast.remove(id);
            if (msgs.error) window.toast.error(msgs.error);
            throw err;
        }
    }
};
