/* ============================================
   Profile Page JavaScript
   ============================================ */

// Tab Switching
function switchTab(btn, tabId) {
    // Remove active class from all tabs and contents
    document.querySelectorAll('.profile-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    // Add active class to clicked tab and corresponding content
    btn.classList.add('active');
    document.getElementById(tabId).classList.add('active');
}

// Edit Profile Modal
function openEditModal() {
    // Create or show edit form modal
    const modal = document.createElement('div');
    modal.className = 'edit-modal';
    modal.innerHTML = `
        <div class="edit-modal-content">
            <div class="edit-modal-header">
                <h2>Edit Profile</h2>
                <button onclick="this.closest('.edit-modal').remove()" class="close-btn">
                    <i class="bi bi-x-lg"></i>
                </button>
            </div>
            <form method="POST" enctype="multipart/form-data" class="edit-form">
                {% csrf_token %}
                
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">First Name</label>
                        <input type="text" name="first_name" class="form-control" value="{{ user.first_nameee }}" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Last Name</label>
                        <input type="text" name="last_name" class="form-control" value="{{ user.last_name }}" required>
                    </div>
                </div>

                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Email</label>
                        <input type="email" class="form-control" value="{{ user.email }}" disabled>
                        <small style="color: var(--text-muted); margin-top: 4px;">Email cannot be changed</small>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Phone Number</label>
                        <input type="tel" name="phone" class="form-control" value="{{ user.phone|default:'' }}">
                    </div>
                </div>

                <div class="form-group">
                    <label class="form-label">Address</label>
                    <input type="text" name="address" class="form-control" value="{{ employee.address|default:'' }}">
                </div>

                <div class="form-group">
                    <label class="form-label">Emergency Contact</label>
                    <input type="text" name="emergency_contact" class="form-control" value="{{ employee.emergency_contact|default:'' }}" placeholder="Name and phone number">
                </div>

                <div class="form-group">
                    <label class="form-label">Profile Avatar</label>
                    <input type="file" name="avatar" class="form-control" accept="image/*">
                    <small style="color: var(--text-muted); margin-top: 4px;">Supported formats: JPG, PNG, GIF (Max 5MB)</small>
                </div>

                <div class="modal-footer">
                    <button type="button" onclick="this.closest('.edit-modal').remove()" class="btn-secondary">Cancel</button>
                    <button type="submit" class="btn-primary">Save Changes</button>
                </div>
            </form>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    modal.querySelectorAll('.edit-form')[0].addEventListener('submit', function(e) {
        // Form will submit normally to Django view
    });
}

// Avatar Upload
function uploadAvatar(input) {
    if (input.files && input.files[0]) {
        const file = input.files[0];

        // Size validation
        if (file.size > 5 * 1024 * 1024) {
            alert('File size exceeds 5MB limit');
            return;
        }

        // Type validation
        if (!['image/jpeg', 'image/png', 'image/gif'].includes(file.type)) {
            alert('Only JPG, PNG, and GIF files are supported');
            return;
        }

        // Preview
        const reader = new FileReader();
        reader.onload = function(e) {
            const img = document.querySelector('.profile-avatar');
            if (img) img.src = e.target.result;
        };
        reader.readAsDataURL(file);

        // Create form
        const form = document.createElement('form');
        form.method = 'POST';
        form.enctype = 'multipart/form-data';

        // Inject CSRF token
        const csrf = document.getElementById('csrfToken').value;
        const csrfField = document.createElement('input');
        csrfField.type = 'hidden';
        csrfField.name = 'csrfmiddlewaretoken';
        csrfField.value = csrf;
        form.appendChild(csrfField);

        // action field
        const actionField = document.createElement('input');
        actionField.type = 'hidden';
        actionField.name = 'action';
        actionField.value = 'upload_avatar';
        form.appendChild(actionField);

        // File input
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.name = 'avatar';
        fileInput.files = input.files;
        form.appendChild(fileInput);

        document.body.appendChild(form);
        form.submit();
        form.remove();
    }
}

  