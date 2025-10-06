let failedAttempts = 0;
const maxAttempts = 3;

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('authForm');
    const loginBtn = document.getElementById('loginBtn');
    const loading = document.getElementById('loading');
    const errorMessage = document.getElementById('errorMessage');
    const attemptCounter = document.getElementById('attemptCounter');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (failedAttempts >= maxAttempts) {
            showError('Maximum authentication attempts exceeded. Please contact your administrator.');
            return;
        }

        const credentials = {
            username: document.getElementById('username').value,
            password: document.getElementById('password').value,
            clearanceLevel: document.getElementById('clearanceLevel').value
        };

        // Basic validation
        if (!credentials.username || !credentials.password) {
            showError('Please enter both username and password.');
            return;
        }

        setLoading(true);
        hideError();

        try {
            const result = await window.electronAPI.authenticate(credentials);

            if (result.success) {
                // Success - window will be closed by main process
                document.getElementById('loading').textContent = 'Authentication successful. Loading application...';
            } else {
                failedAttempts++;
                updateAttemptCounter();
                showError(result.error || 'Authentication failed. Please check your credentials.');

                if (failedAttempts >= maxAttempts) {
                    loginBtn.disabled = true;
                    showError('Maximum authentication attempts exceeded. Application will close.');
                    setTimeout(() => {
                        window.close();
                    }, 3000);
                }
            }
        } catch (error) {
            showError('Authentication service is unavailable. Please try again later.');
        } finally {
            setLoading(false);
        }
    });

    // Auto-focus username field
    document.getElementById('username').focus();

    // Enter key handling
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !loginBtn.disabled) {
            form.dispatchEvent(new Event('submit'));
        }
    });
});

function setLoading(isLoading) {
    const loginBtn = document.getElementById('loginBtn');
    const loading = document.getElementById('loading');

    if (isLoading) {
        loginBtn.disabled = true;
        loginBtn.textContent = 'Authenticating...';
        loading.style.display = 'block';
    } else {
        loginBtn.disabled = false;
        loginBtn.textContent = 'Authenticate';
        loading.style.display = 'none';
    }
}

function showError(message) {
    const errorElement = document.getElementById('errorMessage');
    errorElement.textContent = message;
    errorElement.style.display = 'block';
}

function hideError() {
    const errorElement = document.getElementById('errorMessage');
    errorElement.style.display = 'none';
}

function updateAttemptCounter() {
    const counter = document.getElementById('attemptCounter');
    const remaining = maxAttempts - failedAttempts;

    if (failedAttempts > 0) {
        counter.textContent = `${remaining} attempt${remaining !== 1 ? 's' : ''} remaining`;
        counter.style.display = 'block';
    }
}