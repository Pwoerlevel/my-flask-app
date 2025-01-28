// Email validation function
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// Password strength validation
function checkPasswordStrength(password) {
    let strength = 0;
    
    // Length check
    if (password.length >= 8) strength += 1;
    
    // Contains number
    if (/\d/.test(password)) strength += 1;
    
    // Contains lowercase
    if (/[a-z]/.test(password)) strength += 1;
    
    // Contains uppercase
    if (/[A-Z]/.test(password)) strength += 1;
    
    // Contains special character
    if (/[^A-Za-z0-9]/.test(password)) strength += 1;
    
    return {
        score: strength,
        message: getStrengthMessage(strength)
    };
}

function getStrengthMessage(strength) {
    switch(strength) {
        case 0:
        case 1:
            return 'ضعيف جداً';
        case 2:
            return 'ضعيف';
        case 3:
            return 'متوسط';
        case 4:
            return 'قوي';
        case 5:
            return 'قوي جداً';
        default:
            return '';
    }
}

// Initialize all tooltips
function initTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(tooltip => {
        tooltip.addEventListener('mouseover', showTooltip);
        tooltip.addEventListener('mouseout', hideTooltip);
    });
}

function showTooltip(e) {
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = this.dataset.tooltip;
    document.body.appendChild(tooltip);
    
    const rect = this.getBoundingClientRect();
    tooltip.style.top = rect.bottom + 5 + 'px';
    tooltip.style.left = rect.left + (rect.width - tooltip.offsetWidth) / 2 + 'px';
}

function hideTooltip() {
    const tooltips = document.querySelectorAll('.tooltip');
    tooltips.forEach(tooltip => tooltip.remove());
}

// Form validation
document.addEventListener('DOMContentLoaded', function() {
    const registerForm = document.getElementById('registerForm');
    const loginForm = document.getElementById('loginForm');

    if (registerForm) {
        registerForm.addEventListener('submit', function(e) {
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirm_password').value;
            const email = document.getElementById('email').value;
            
            if (!validateEmail(email)) {
                e.preventDefault();
                alert('الرجاء إدخال بريد إلكتروني صحيح');
                return;
            }
            
            if (password !== confirmPassword) {
                e.preventDefault();
                alert('كلمات المرور غير متطابقة');
                return;
            }
            
            const passwordStrength = checkPasswordStrength(password);
            if (passwordStrength.score < 3) {
                if (!confirm('كلمة المرور ضعيفة. هل تريد المتابعة؟')) {
                    e.preventDefault();
                    return;
                }
            }
        });

        // Real-time password strength indicator
        const passwordInput = document.getElementById('password');
        if (passwordInput) {
            const strengthIndicator = document.createElement('div');
            strengthIndicator.className = 'password-strength';
            passwordInput.parentNode.appendChild(strengthIndicator);

            passwordInput.addEventListener('input', function() {
                const strength = checkPasswordStrength(this.value);
                strengthIndicator.textContent = 'قوة كلمة المرور: ' + strength.message;
                strengthIndicator.className = 'password-strength strength-' + strength.score;
            });
        }
    }

    // Initialize tooltips
    initTooltips();
});

// Skills management
document.addEventListener('DOMContentLoaded', function() {
    const skillsContainer = document.getElementById('skills-container');
    
    if (skillsContainer) {
        // Add new skill field
        document.querySelector('.add-skill').addEventListener('click', function() {
            const skillInput = document.createElement('div');
            skillInput.className = 'skill-input';
            skillInput.innerHTML = `
                <input type="text" name="skill" class="skill-field">
                <button type="button" class="remove-skill">-</button>
            `;
            skillsContainer.appendChild(skillInput);
        });

        // Remove skill field
        skillsContainer.addEventListener('click', function(e) {
            if (e.target.classList.contains('remove-skill')) {
                e.target.parentElement.remove();
            }
        });
    }
});
